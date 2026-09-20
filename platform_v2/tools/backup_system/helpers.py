from __future__ import annotations

import errno
import fnmatch
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from tqdm import tqdm

from .config import DEFAULT_EXCLUDES, MANIFEST_NAME


def now_tag() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def backup_name(project_name: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", project_name.strip()).strip("._-")
    return f"full_{safe_name or 'backup'}_{now_tag()}"


def normalize_cli_path(raw_path: str) -> Path:
    match = re.match(r"^([A-Za-z]):[\\/]*(.*)$", raw_path.strip())
    if not match:
        return Path(raw_path).expanduser().resolve()
    drive = match.group(1).lower()
    remainder = match.group(2).replace("\\", "/").strip("/")
    wsl_path = Path("/mnt") / drive
    if remainder:
        wsl_path = wsl_path / Path(remainder)
    return wsl_path.resolve()


def disk_has_space(path: Path, required_bytes: int, logger: logging.Logger) -> bool:
    free: int | None = None
    try:
        _, _, free = shutil.disk_usage(path)
    except OSError as exc:
        logger.error(f"Failed to check disk space on {path}: {exc}")
    if free is None:
        return False
    if free < required_bytes:
        logger.error(
            f"Not enough free space on {path} (need ~{required_bytes/1e6:.0f} MB, have {free/1e6:.0f} MB)"
        )
        return False
    return True


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def is_ignored(rel_path: str, patterns: list[str]) -> bool:
    rel_norm = rel_path.replace("\\", "/")
    rel_dir = f"{rel_norm}/"
    for pattern in patterns:
        pat = pattern.replace("\\", "/")
        if fnmatch.fnmatch(rel_norm, pat):
            return True
        if pat.endswith("/") and fnmatch.fnmatch(rel_dir, pat):
            return True
    return False


def is_included(rel_path: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    rel_norm = rel_path.replace("\\", "/")
    for pattern in patterns:
        pat = pattern.replace("\\", "/")
        if fnmatch.fnmatch(rel_norm, pat):
            return True
        if pat.endswith("/**"):
            prefix = pat[:-3].rstrip("/")
            if rel_norm == prefix or rel_norm.startswith(f"{prefix}/"):
                return True
    return False


def can_contain_included(rel_dir: str, patterns: list[str]) -> bool:
    """Return whether a directory can contain at least one included path."""

    if not patterns:
        return True
    rel_norm = rel_dir.replace("\\", "/").strip("/")
    for pattern in patterns:
        pat = pattern.replace("\\", "/").strip("/")
        literal_prefix = pat.split("*", 1)[0].rstrip("/")
        if not rel_norm:
            return True
        if not literal_prefix:
            return True
        if literal_prefix == rel_norm:
            return True
        if literal_prefix.startswith(f"{rel_norm}/"):
            return True
        if rel_norm.startswith(f"{literal_prefix}/"):
            return True
    return False


def load_excludes(project_root: Path, cli_patterns: list[str], exclude_file: Path | None) -> list[str]:
    patterns = set(DEFAULT_EXCLUDES)
    local_file = project_root / ".backupignore"
    for file_path in [exclude_file, local_file]:
        if file_path and file_path.exists():
            for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.add(line)
    patterns.update(cli_patterns or [])
    return list(patterns)


def load_includes(cli_patterns: list[str], include_file: Path | None) -> list[str]:
    patterns: set[str] = set()
    if include_file and include_file.exists():
        for line in include_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.add(line)
    patterns.update(cli_patterns or [])
    return list(patterns)


def iter_project_files(project_root: Path, exclude_patterns: list[str], include_patterns: list[str] | None = None) -> list[Path]:
    include_patterns = include_patterns or []
    files: list[Path] = []
    for root, dirs, names in os.walk(project_root):
        root_path = Path(root)
        dirs[:] = [
            name
            for name in dirs
            if can_contain_included(
                str(Path(root_path.relative_to(project_root), name)),
                include_patterns,
            )
            and not is_ignored(str(Path(root_path.relative_to(project_root), name)), exclude_patterns)
            and not ((root_path / name).is_symlink() and not (root_path / name).exists())
        ]
        for name in names:
            rel = Path(root_path.relative_to(project_root), name)
            if not is_included(str(rel), include_patterns):
                continue
            if is_ignored(str(rel), exclude_patterns):
                continue
            source = project_root / rel
            if source.is_symlink() and not source.exists():
                continue
            files.append(source)
    return files


def write_manifest(dest_dir: Path, records: list[dict[str, object]], logger: logging.Logger) -> None:
    manifest_path = dest_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps({"generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "files": records}, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Manifest written: {manifest_path}")


def build_manifest_records(root_dir: Path, logger: logging.Logger, warning_prefix: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in iter_project_files(root_dir, []):
        rel = path.relative_to(root_dir)
        try:
            stat = path.stat()
            records.append(
                {
                    "path": str(rel).replace("\\", "/"),
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                    "sha256": sha256_file(path),
                }
            )
        except OSError as exc:
            logger.warning(f"{warning_prefix} {rel}: {exc}")
    return records


def zip_dir(src_dir: Path, zip_path: Path, logger: logging.Logger) -> None:
    tmp = zip_path.with_suffix(zip_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    with ZipFile(tmp, "w", compression=ZIP_DEFLATED, allowZip64=True) as zip_file:
        base = src_dir.parent
        for path in tqdm(iter_project_files(src_dir, []), desc="==> Zipping", colour="cyan"):
            arcname = path.relative_to(base)
            info = ZipInfo.from_file(path, arcname)
            with path.open("rb") as handle:
                zip_file.writestr(info, handle.read())
    tmp.replace(zip_path)
    try:
        zip_path.chmod(0o600)
    except OSError as exc:
        logger.debug(f"Could not restrict ZIP permissions for {zip_path}: {exc}")
    logger.info(f"ZIP archive created: {zip_path}")


def _wsl_drive_mount_root(path: Path) -> Path | None:
    parts = [part for part in path.parts if part != "/"]
    if len(parts) >= 2 and parts[0] == "mnt" and len(parts[1]) == 1 and parts[1].isalpha():
        return Path("/") / parts[0] / parts[1]
    return None


def _ensure_wsl_drive_mounted(path: Path, logger: logging.Logger) -> bool:
    mount_root = _wsl_drive_mount_root(path)
    if mount_root is None:
        return True
    if os.path.ismount(mount_root):
        return True

    drive_letter = mount_root.name.upper()
    logger.warning(f"{mount_root} is not mounted. Trying to mount Windows drive {drive_letter}:")
    try:
        result = subprocess.run(
            ["mount", "-t", "drvfs", f"{drive_letter}:", str(mount_root)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        logger.error(f"Failed to execute mount command for {drive_letter}: {exc}")
        return False

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if stderr:
            logger.error(f"Auto-mount failed for {drive_letter}: {stderr}")
        logger.error(
            f"Run this manually, then retry backup: "
            f"sudo mkdir -p {mount_root} && sudo mount -t drvfs {drive_letter}: {mount_root}"
        )
        return False

    if not os.path.ismount(mount_root):
        logger.error(f"{mount_root} still not mounted after auto-mount attempt.")
        return False

    logger.info(f"Mounted Windows drive {drive_letter}: at {mount_root}")
    return True


def ensure_base_dir(path: Path, logger: logging.Logger) -> bool:
    if not _ensure_wsl_drive_mounted(path, logger):
        return False
    if path.exists():
        return True
    logger.warning(f"USB path not found: {path}, creating it...")
    created = False
    try:
        path.mkdir(parents=True, exist_ok=True)
        created = True
    except OSError as exc:
        logger.error(f"Failed to create target directory {path}: {exc}")
    if not created:
        return False
    logger.info(f"Created target directory: {path}")
    return True


def build_sync_base_path(target_path: Path, project_name: str) -> Path:
    if target_path.name.casefold() == project_name.casefold():
        return target_path
    return target_path / project_name


def safe_copy(src: Path, dst: Path, logger: logging.Logger) -> bool:
    try:
        shutil.copy2(src, dst)
        return True
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            logger.warning(f"Skipped unavailable source during backup: {src}")
            return False
        if exc.errno in (errno.EPERM, errno.EACCES, errno.ENOTSUP):
            try:
                shutil.copyfile(src, dst)
            except OSError as fallback_exc:
                if fallback_exc.errno == errno.ENOENT:
                    logger.warning(f"Skipped unavailable source during backup: {src}")
                    return False
                raise
            try:
                stat = src.stat()
                os.utime(dst, (stat.st_atime, stat.st_mtime), follow_symlinks=False)
            except OSError:
                logger.debug(f"Could not preserve timestamps for fallback copy: {dst}")
            logger.debug(f"Fallback copy (no metadata): {src} -> {dst}")
            return True
        raise


def backup_sqlite_database(source: Path, target: Path, logger: logging.Logger) -> bool:
    """Create a transactionally consistent SQLite copy using the backup API."""

    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(source) as source_connection:
            with sqlite3.connect(target) as target_connection:
                source_connection.backup(target_connection)
    except sqlite3.Error as exc:
        logger.error(f"SQLite backup failed {source} -> {target}: {exc}")
        return False
    logger.info(f"SQLite snapshot created: {target}")
    return True
