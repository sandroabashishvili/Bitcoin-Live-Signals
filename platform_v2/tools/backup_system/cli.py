from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .actions import SyncResult, full_backup, usb_sync, verify_backup
from .config import (
    DEFAULT_BACKUP_ROOT,
    DEFAULT_FLASH_PATH,
    DEFAULT_PROJECT_NAME,
    DEFAULT_USB_PATH,
    HOME_CRITICAL_REQUIRED_PATHS,
    HOME_CRITICAL_BACKUP_ROOT,
    HOME_CRITICAL_EXCLUDES,
    HOME_CRITICAL_INCLUDES,
    HOME_CRITICAL_PROJECT_NAME,
    HOME_ROOT,
    MIGRATION_ALLOWED_EXCLUDE_OVERRIDES,
    MIGRATION_PRIVATE_BACKUP_ROOT,
    MIGRATION_PRIVATE_EXCLUDES,
    MIGRATION_PRIVATE_INCLUDES,
    MIGRATION_PRIVATE_PROJECT_NAME,
    MIGRATION_PRIVATE_REQUIRED_PATHS,
    PROJECT_ROOT,
    SMARTSIGNALHUB_REQUIRED_PATHS,
    WINDOWS_CRITICAL_BACKUP_ROOT,
    WINDOWS_CRITICAL_INCLUDES,
    WINDOWS_CRITICAL_PROJECT_NAME,
    WINDOWS_CRITICAL_REQUIRED_PATHS,
    WINDOWS_USER_ROOT,
)
from .helpers import load_excludes, load_includes, normalize_cli_path
from .logging_utils import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SmartSignalHub workspace backup manager")
    parser.add_argument(
        "--profile",
        choices=(
            "all-critical",
            "linux-migration-final",
            "smartsignalhub",
            "home-critical",
            "migration-private",
            "windows-critical",
        ),
        default="all-critical",
        help=(
            "Backup profile. linux-migration-final runs SmartSignalHub, private WSL state, "
            "and Windows user/Codex state."
        ),
    )
    parser.add_argument("--project-root", default=str(PROJECT_ROOT), help="Workspace root to back up")
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT), help="Where to put local workspace backups")
    parser.add_argument("--usb-path", default=DEFAULT_USB_PATH, help="Primary USB/HDD mount point")
    parser.add_argument("--flash-path", default=DEFAULT_FLASH_PATH, help="Secondary USB flash mount point")
    parser.add_argument("--project-name", default=DEFAULT_PROJECT_NAME, help="Target folder name on external destinations")
    parser.add_argument("--full", action="store_true", help="Create local full backup")
    parser.add_argument("--sync-usb", action="store_true", help="Sync to both external targets")
    parser.add_argument("--local-only", action="store_true", help="Create/verify local backups without external sync")
    parser.add_argument("--skip-flash", action="store_true", help="Skip secondary flash target")
    parser.add_argument(
        "--strict-targets",
        action="store_true",
        help="Fail when any requested external target is unavailable",
    )
    parser.add_argument("--verify", metavar="BACKUP_DIR", help="Verify a given backup dir")
    parser.add_argument("--diagnose", action="store_true", help="Verify source selection and the latest local backup")
    parser.add_argument("--dry-run", action="store_true", help="Simulate only; do not write anything")
    parser.add_argument("--deep-hash", action="store_true", help="Hash-check files during sync")
    parser.add_argument("--exclude", action="append", default=[], help="Extra exclude pattern (can repeat)")
    parser.add_argument("--exclude-from", default=None, help="File with exclude patterns")
    parser.add_argument("--include", action="append", default=[], help="Include pattern (can repeat); empty means include all")
    parser.add_argument("--include-from", default=None, help="File with include patterns")
    parser.add_argument("-q", "--quiet", action="store_true", help="Less console output")
    return parser.parse_args()


def _forwarded_common_args(args: argparse.Namespace) -> list[str]:
    forwarded: list[str] = []
    for flag in (
        "full",
        "sync_usb",
        "local_only",
        "skip_flash",
        "strict_targets",
        "dry_run",
        "deep_hash",
        "diagnose",
        "quiet",
    ):
        if getattr(args, flag):
            forwarded.append(f"--{flag.replace('_', '-')}")
    forwarded.extend(["--usb-path", args.usb_path])
    forwarded.extend(["--flash-path", args.flash_path])
    for pattern in args.exclude or []:
        forwarded.extend(["--exclude", pattern])
    if args.exclude_from:
        forwarded.extend(["--exclude-from", args.exclude_from])
    for pattern in args.include or []:
        forwarded.extend(["--include", pattern])
    if args.include_from:
        forwarded.extend(["--include-from", args.include_from])
    return forwarded


def _run_profile_group(args: argparse.Namespace, logger, profiles: tuple[str, ...]) -> None:
    if args.verify:
        logger.critical("--verify is profile-specific; select one concrete backup profile.")
        sys.exit(2)
    if args.project_root != str(PROJECT_ROOT) or args.backup_root != str(DEFAULT_BACKUP_ROOT) or args.project_name != DEFAULT_PROJECT_NAME:
        logger.critical(
            f"--profile {args.profile} uses the configured roots for each backup set. "
            "Select one concrete profile for custom roots."
        )
        sys.exit(2)

    common_args = _forwarded_common_args(args)
    failed_profiles: list[str] = []
    for profile in profiles:
        logger.info(f"Running backup profile: {profile}")
        command = [sys.executable, "-m", "platform_v2.tools.backup_system", "--profile", profile, *common_args]
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            logger.critical(f"Backup profile failed: {profile} (exit={result.returncode})")
            failed_profiles.append(profile)
    if failed_profiles:
        logger.critical(f"Backup completed with failed profiles: {', '.join(failed_profiles)}")
        sys.exit(1)
    logger.info(f"All requested backup profiles completed successfully: {', '.join(profiles)}")


def main() -> None:
    args = parse_args()
    logger = setup_logging(verbose=not args.quiet)

    if args.local_only and args.sync_usb:
        logger.critical("--local-only and --sync-usb cannot be used together.")
        sys.exit(2)

    if args.profile == "all-critical":
        _run_profile_group(args, logger, ("smartsignalhub", "home-critical"))
        return

    if args.profile == "linux-migration-final":
        args.strict_targets = True
        _run_profile_group(
            args,
            logger,
            ("smartsignalhub", "migration-private", "windows-critical"),
        )
        return

    allow_private_content = False
    exclude_overrides: set[str] = set()
    if args.profile == "home-critical":
        if args.project_root == str(PROJECT_ROOT):
            args.project_root = str(HOME_ROOT)
        if args.backup_root == str(DEFAULT_BACKUP_ROOT):
            args.backup_root = str(HOME_CRITICAL_BACKUP_ROOT)
        if args.project_name == DEFAULT_PROJECT_NAME:
            args.project_name = HOME_CRITICAL_PROJECT_NAME
        profile_excludes = set(HOME_CRITICAL_EXCLUDES)
        profile_includes = set(HOME_CRITICAL_INCLUDES)
        required_paths = HOME_CRITICAL_REQUIRED_PATHS
    elif args.profile == "migration-private":
        if args.project_root == str(PROJECT_ROOT):
            args.project_root = str(HOME_ROOT)
        if args.backup_root == str(DEFAULT_BACKUP_ROOT):
            args.backup_root = str(MIGRATION_PRIVATE_BACKUP_ROOT)
        if args.project_name == DEFAULT_PROJECT_NAME:
            args.project_name = MIGRATION_PRIVATE_PROJECT_NAME
        profile_excludes = set(MIGRATION_PRIVATE_EXCLUDES)
        profile_includes = set(MIGRATION_PRIVATE_INCLUDES)
        required_paths = MIGRATION_PRIVATE_REQUIRED_PATHS
        allow_private_content = True
        exclude_overrides = set(MIGRATION_ALLOWED_EXCLUDE_OVERRIDES)
    elif args.profile == "windows-critical":
        if args.project_root == str(PROJECT_ROOT):
            args.project_root = str(WINDOWS_USER_ROOT)
        if args.backup_root == str(DEFAULT_BACKUP_ROOT):
            args.backup_root = str(WINDOWS_CRITICAL_BACKUP_ROOT)
        if args.project_name == DEFAULT_PROJECT_NAME:
            args.project_name = WINDOWS_CRITICAL_PROJECT_NAME
        profile_excludes = set()
        profile_includes = set(WINDOWS_CRITICAL_INCLUDES)
        required_paths = WINDOWS_CRITICAL_REQUIRED_PATHS
        allow_private_content = True
        exclude_overrides = set(MIGRATION_ALLOWED_EXCLUDE_OVERRIDES)
    else:
        profile_excludes = set()
        profile_includes = set()
        required_paths = SMARTSIGNALHUB_REQUIRED_PATHS

    project_root = Path(args.project_root).resolve()
    backup_root = Path(args.backup_root).resolve()
    usb_path = normalize_cli_path(args.usb_path)
    flash_path = normalize_cli_path(args.flash_path)
    exclude_file = Path(args.exclude_from).resolve() if args.exclude_from else None
    include_file = Path(args.include_from).resolve() if args.include_from else None

    if not project_root.exists():
        logger.critical(f"Workspace root not found: {project_root}")
        sys.exit(2)

    excludes = sorted(
        (set(load_excludes(project_root, args.exclude, exclude_file)) | profile_excludes)
        - exclude_overrides
    )
    includes = sorted(set(load_includes(args.include, include_file)) | profile_includes)
    logger.info("Workspace backup started...")
    logger.info(f"Profile: {args.profile}")
    if includes:
        logger.info(f"Include patterns: {len(includes)}")

    missing_sources = [path for path in required_paths if not (project_root / path).exists()]
    if missing_sources:
        logger.critical(f"Required source content is missing: {', '.join(missing_sources)}")
        sys.exit(1)

    try:
        if args.diagnose:
            candidates = sorted(
                (path for path in backup_root.glob("full_*") if path.is_dir()),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if not candidates:
                logger.critical(f"No local backup found under: {backup_root}")
                sys.exit(1)
            logger.info(f"Diagnosing latest local backup: {candidates[0]}")
            if not verify_backup(
                candidates[0],
                logger,
                required_paths=required_paths,
                allow_private_content=allow_private_content,
            ):
                sys.exit(1)
            logger.info("Backup diagnostics passed")
            return

        did_full = False
        local_backup_dir: Path | None = None
        local_backup_zip: Path | None = None
        sync_results: list[tuple[str, SyncResult]] = []

        if args.full:
            dest_dir, zip_path = full_backup(
                project_root,
                backup_root,
                args.project_name,
                excludes,
                logger,
                dry_run=args.dry_run,
                includes=includes,
            )
            logger.info(f"Local full backup done: {dest_dir}")
            if not args.dry_run and not verify_backup(
                dest_dir,
                logger,
                required_paths=required_paths,
                allow_private_content=allow_private_content,
            ):
                raise ValueError(f"New local backup failed verification: {dest_dir}")
            local_backup_dir = dest_dir
            local_backup_zip = zip_path
            did_full = True

        if args.sync_usb:
            sync_results.append(
                (
                    "USB",
                    usb_sync(
                        project_root,
                        usb_path,
                        args.project_name,
                        excludes,
                        args.dry_run,
                        args.deep_hash,
                        logger,
                        includes=includes,
                    ),
                )
            )
            if not args.skip_flash:
                sync_results.append(
                    (
                        "FLASH",
                        usb_sync(
                            project_root,
                            flash_path,
                            args.project_name,
                            excludes,
                            args.dry_run,
                            args.deep_hash,
                            logger,
                            includes=includes,
                        ),
                    )
                )

        if args.verify:
            ok = verify_backup(
                Path(args.verify).resolve(),
                logger,
                required_paths=required_paths,
                allow_private_content=allow_private_content,
            )
            if not ok:
                sys.exit(1)

        if not (args.full or args.sync_usb or args.verify):
            dest_dir, zip_path = full_backup(
                project_root,
                backup_root,
                args.project_name,
                excludes,
                logger,
                dry_run=args.dry_run,
                includes=includes,
            )
            logger.info(f"Local full backup done: {dest_dir}")
            if not args.dry_run and not verify_backup(
                dest_dir,
                logger,
                required_paths=required_paths,
                allow_private_content=allow_private_content,
            ):
                raise ValueError(f"New local backup failed verification: {dest_dir}")
            local_backup_dir = dest_dir
            local_backup_zip = zip_path
            if not args.local_only:
                sync_results.append(
                    (
                        "USB",
                        usb_sync(
                            project_root,
                            usb_path,
                            args.project_name,
                            excludes,
                            args.dry_run,
                            False,
                            logger,
                            includes=includes,
                        ),
                    )
                )
                if not args.skip_flash:
                    sync_results.append(
                        (
                            "FLASH",
                            usb_sync(
                                project_root,
                                flash_path,
                                args.project_name,
                                excludes,
                                args.dry_run,
                                False,
                                logger,
                                includes=includes,
                            ),
                        )
                    )

        if did_full and not args.sync_usb and not args.local_only:
            sync_results.append(
                (
                    "USB",
                    usb_sync(
                        project_root,
                        usb_path,
                        args.project_name,
                        excludes,
                        args.dry_run,
                        args.deep_hash,
                        logger,
                        includes=includes,
                    ),
                )
            )
            if not args.skip_flash:
                sync_results.append(
                    (
                        "FLASH",
                        usb_sync(
                            project_root,
                            flash_path,
                            args.project_name,
                            excludes,
                            args.dry_run,
                            args.deep_hash,
                            logger,
                            includes=includes,
                        ),
                    )
                )

        if local_backup_dir is not None and local_backup_zip is not None:
            logger.info("Backup summary:")
            logger.info(f"  Local folder: {local_backup_dir}")
            logger.info(f"  Local ZIP: {local_backup_zip}")

        for label, result in sync_results:
            if result.performed:
                logger.info(f"Verifying {label} backup: {result.dest_root}")
                if not verify_backup(
                    result.dest_root,
                    logger,
                    required_paths=required_paths,
                    allow_private_content=allow_private_content,
                ):
                    raise ValueError(f"{label} backup failed verification: {result.dest_root}")
                logger.info(
                    f"  {label}: {result.dest_root} | zip={result.zip_path} | copied={result.copied} | skipped={result.skipped} | hashed={result.hashed}"
                )
            else:
                message = f"{label}: not completed ({result.reason}) -> {result.dest_root}"
                if args.strict_targets and not args.dry_run:
                    raise ValueError(message)
                logger.warning(f"  {message}")

    except KeyboardInterrupt:
        logger.error("Interrupted by user")
        sys.exit(130)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.exception(f"Unhandled backup error: {exc}")
        sys.exit(1)
    finally:
        logger.info("Backup module finished")
