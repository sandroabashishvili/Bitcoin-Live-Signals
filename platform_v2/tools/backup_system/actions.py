from __future__ import annotations

import errno
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from tqdm import tqdm

from platform_v2.shared.backend.persistence import ACTIVE_DATABASE_PATHS, LEGACY_RUNTIME_DATABASE_PATH

from .config import MANIFEST_NAME, ZIP_SUFFIX
from .helpers import (
    backup_name,
    backup_sqlite_database,
    build_manifest_records,
    build_sync_base_path,
    disk_has_space,
    ensure_base_dir,
    iter_project_files,
    safe_copy,
    sha256_file,
    write_manifest,
    zip_dir,
)


RUNTIME_DATABASE_RELATIVES = tuple(
    path.relative_to(path.parents[3]) for path in ACTIVE_DATABASE_PATHS
)
LEGACY_DATABASE_RELATIVE = LEGACY_RUNTIME_DATABASE_PATH.relative_to(LEGACY_RUNTIME_DATABASE_PATH.parents[3])
FORBIDDEN_BACKUP_DIRECTORY_NAMES = {
    ".codex",
    ".git",
    ".ssh",
    ".venv",
    "__pycache__",
    "lighthouse-profile",
    "node_modules",
    "venv",
}
FORBIDDEN_BACKUP_FILE_NAMES = {".env", ".git-credentials"}


def _backup_runtime_databases(project_root: Path, dest_root: Path, logger: logging.Logger) -> None:
    relatives = list(RUNTIME_DATABASE_RELATIVES)
    if (project_root / LEGACY_DATABASE_RELATIVE).exists():
        relatives.append(LEGACY_DATABASE_RELATIVE)
    for relative in relatives:
        backup_sqlite_database(project_root / relative, dest_root / relative, logger)


@dataclass(frozen=True)
class SyncResult:
    dest_root: Path
    zip_path: Path
    copied: int = 0
    skipped: int = 0
    hashed: int = 0
    performed: bool = False
    reason: str | None = None


def full_backup(
    project_root: Path,
    backup_root: Path,
    project_name: str,
    excludes: list[str],
    logger: logging.Logger,
    dry_run: bool = False,
    includes: list[str] | None = None,
) -> tuple[Path, Path]:
    dest_dir = backup_root / backup_name(project_name)
    logger.info(f"{'Simulating' if dry_run else 'Creating'} full backup → {dest_dir}")
    files = iter_project_files(project_root, excludes, includes)
    if dry_run:
        return dest_dir, dest_dir.with_suffix(ZIP_SUFFIX)
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    for src in tqdm(files, desc="==> Copying", colour="green"):
        rel = src.relative_to(project_root)
        dst = dest_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        safe_copy(src, dst, logger)
    _backup_runtime_databases(project_root, dest_dir, logger)
    records = build_manifest_records(dest_dir, logger, "Failed manifest entry for")
    write_manifest(dest_dir, records, logger)
    zip_path = dest_dir.with_suffix(ZIP_SUFFIX)
    zip_dir(dest_dir, zip_path, logger)
    return dest_dir, zip_path


def usb_sync(
    project_root: Path,
    usb_path: Path,
    project_name: str,
    excludes: list[str],
    dry_run: bool,
    verify_hash: bool,
    logger: logging.Logger,
    includes: list[str] | None = None,
) -> SyncResult:
    sync_base = build_sync_base_path(usb_path, project_name)
    dest_root = sync_base / backup_name(project_name)
    zip_path = dest_root.with_suffix(ZIP_SUFFIX)
    if not dry_run and not ensure_base_dir(sync_base, logger):
        return SyncResult(dest_root=dest_root, zip_path=zip_path, reason="target_unavailable")

    logger.info(f"USB sync target: {dest_root}")
    files = iter_project_files(project_root, excludes, includes)
    estimate = 300 * 1024 * 1024
    available_files: list[Path] = []
    for path in files:
        try:
            estimate += path.stat().st_size
            available_files.append(path)
        except OSError as exc:
            logger.warning(f"Skipped unavailable source during size estimate: {path} ({exc})")
    files = available_files
    if not dry_run and not disk_has_space(sync_base, estimate, logger):
        return SyncResult(dest_root=dest_root, zip_path=zip_path, reason="insufficient_space")

    if not dry_run:
        try:
            dest_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            reason = "read_only" if exc.errno == errno.EROFS else "permission_denied"
            logger.error(f"Cannot create backup target {dest_root}: {exc}")
            logger.debug(f"mkdir permission details: {exc}")
            return SyncResult(dest_root=dest_root, zip_path=zip_path, reason=reason)

    copied = skipped = hashed = 0
    for src in tqdm(files, desc="==> USB Sync", colour="green"):
        rel = src.relative_to(project_root)
        dst = dest_root / rel
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
        should_copy = False
        try:
            if not dst.exists():
                should_copy = True
            else:
                src_stat = src.stat()
                dst_stat = dst.stat()
                if src_stat.st_size != dst_stat.st_size or int(src_stat.st_mtime) != int(dst_stat.st_mtime):
                    should_copy = True
                elif verify_hash:
                    hashed += 1
                    if sha256_file(src) != sha256_file(dst):
                        should_copy = True
        except OSError as exc:
            logger.warning(f"Skipped unavailable source during USB sync: {rel} ({exc})")
            skipped += 1
            continue

        if should_copy:
            if dry_run:
                logger.debug(f"(dry) copy: {rel}")
            else:
                try:
                    if safe_copy(src, dst, logger):
                        copied += 1
                        logger.debug(f"Copied: {rel}")
                    else:
                        skipped += 1
                except OSError as exc:
                    logger.error(f"Failed to copy {rel}: {exc}")
        else:
            skipped += 1

    if not dry_run:
        _backup_runtime_databases(project_root, dest_root, logger)
        records = build_manifest_records(dest_root, logger, "USB manifest entry failed for")
        write_manifest(dest_root, records, logger)
        zip_dir(dest_root, zip_path, logger)
    logger.info(f"USB sync complete. Copied: {copied} | Skipped: {skipped} | HashedChecks: {hashed}")
    return SyncResult(
        dest_root=dest_root,
        zip_path=zip_path,
        copied=copied,
        skipped=skipped,
        hashed=hashed,
        performed=not dry_run,
        reason="dry_run" if dry_run else None,
    )


def _verify_zip_archive(backup_dir: Path, expected_paths: set[str], logger: logging.Logger) -> bool:
    zip_path = backup_dir.with_suffix(ZIP_SUFFIX)
    if not zip_path.is_file():
        logger.error(f"ZIP archive not found: {zip_path}")
        return False
    prefix = f"{backup_dir.name}/"
    expected_members = {f"{prefix}{path}" for path in expected_paths}
    expected_members.add(f"{prefix}{MANIFEST_NAME}")
    try:
        with ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            missing = sorted(expected_members - names)
            if missing:
                logger.error(f"ZIP archive is missing {len(missing)} expected member(s): {missing[:5]}")
                return False
            bad_member = archive.testzip()
    except (OSError, BadZipFile) as exc:
        logger.error(f"ZIP archive cannot be read: {zip_path} ({exc})")
        return False
    if bad_member:
        logger.error(f"ZIP CRC verification failed: {bad_member}")
        return False
    logger.info(f"ZIP verification OK: {zip_path}")
    return True


def _verify_sqlite_databases(
    backup_dir: Path,
    logger: logging.Logger,
    *,
    include_codex_sqlite: bool = False,
) -> bool:
    ok = True
    database_paths = set(backup_dir.rglob("*.sqlite3"))
    if include_codex_sqlite:
        database_paths.update(backup_dir.rglob("*.sqlite"))
    database_paths = sorted(database_paths)
    for database_path in database_paths:
        try:
            with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
                result = connection.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                logger.error(f"SQLite integrity check failed: {database_path} ({result})")
                ok = False
        except sqlite3.Error as exc:
            logger.error(f"SQLite database cannot be opened: {database_path} ({exc})")
            ok = False
    if ok:
        logger.info(f"SQLite verification OK: {len(database_paths)} database(s)")
    return ok


def _verify_forbidden_content(backup_dir: Path, logger: logging.Logger) -> bool:
    forbidden: list[str] = []
    for path in backup_dir.rglob("*"):
        relative = path.relative_to(backup_dir)
        if path.is_dir() and path.name in FORBIDDEN_BACKUP_DIRECTORY_NAMES:
            forbidden.append(str(relative))
        elif path.is_file() and path.name in FORBIDDEN_BACKUP_FILE_NAMES:
            forbidden.append(str(relative))
    if forbidden:
        logger.error(f"Backup contains forbidden private/generated content: {forbidden[:10]}")
        return False
    logger.info("Sensitive/generated content verification OK")
    return True


def verify_backup(
    backup_dir: Path,
    logger: logging.Logger,
    *,
    required_paths: tuple[str, ...] = (),
    allow_private_content: bool = False,
) -> bool:
    manifest_path = backup_dir / MANIFEST_NAME
    if not manifest_path.exists():
        logger.error(f"Manifest not found: {manifest_path}")
        return False
    data: dict[str, object] | None = None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"Failed to read manifest {manifest_path}: {exc}")
    if not isinstance(data, dict):
        return False
    files = data.get("files")
    if not isinstance(files, list):
        logger.error("Manifest is missing a valid files list")
        return False
    ok = True
    manifest_paths: set[str] = set()
    for record in tqdm(files, desc="==> Verifying", colour="yellow"):
        if not isinstance(record, dict):
            logger.error("Manifest contains a non-dictionary record")
            ok = False
            continue
        rel = record.get("path")
        if not isinstance(rel, str) or not rel:
            logger.error("Manifest record is missing a valid path")
            ok = False
            continue
        manifest_paths.add(rel)
        file_path = backup_dir / rel
        if not file_path.exists():
            logger.error(f"Missing file: {rel}")
            ok = False
            continue
        try:
            stat = file_path.stat()
            size_ok = stat.st_size == record.get("size")
            hash_ok = sha256_file(file_path) == record.get("sha256")
            if not size_ok or not hash_ok:
                logger.error(f"Mismatch: {rel} (size_ok={size_ok}, hash_ok={hash_ok})")
                ok = False
        except OSError as exc:
                logger.error(f"Verify error {rel}: {exc}")
                ok = False
    for required_path in required_paths:
        if not (backup_dir / required_path).exists():
            logger.error(f"Required backup content is missing: {required_path}")
            ok = False
    if not _verify_zip_archive(backup_dir, manifest_paths, logger):
        ok = False
    if not _verify_sqlite_databases(
        backup_dir,
        logger,
        include_codex_sqlite=allow_private_content,
    ):
        ok = False
    if allow_private_content:
        logger.warning("Private migration content explicitly allowed for this profile")
    elif not _verify_forbidden_content(backup_dir, logger):
        ok = False
    if ok:
        total_size = sum(int(record.get("size", 0)) for record in files if isinstance(record, dict))
        logger.info(f"Verification OK: {len(files)} file(s), {total_size / (1024 * 1024):.1f} MiB")
    else:
        logger.error("Verification FAILED")
    return ok
