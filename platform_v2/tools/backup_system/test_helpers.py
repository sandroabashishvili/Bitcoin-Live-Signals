from __future__ import annotations

import logging
import sqlite3

from platform_v2.tools.backup_system.actions import full_backup, verify_backup
from platform_v2.tools.backup_system.config import (
    DEFAULT_EXCLUDES,
    HOME_CRITICAL_EXCLUDES,
    HOME_CRITICAL_INCLUDES,
    MIGRATION_ALLOWED_EXCLUDE_OVERRIDES,
    MIGRATION_PRIVATE_INCLUDES,
    PROJECT_ROOT,
    SMARTSIGNALHUB_REQUIRED_PATHS,
    WINDOWS_CRITICAL_INCLUDES,
)

from platform_v2.tools.backup_system.helpers import (
    backup_sqlite_database,
    can_contain_included,
    is_ignored,
    is_included,
    iter_project_files,
    safe_copy,
)


def test_include_directory_pruning_only_enters_relevant_trees() -> None:
    patterns = [".codex/**", "AppData/Roaming/Code/User/settings.json", "Desktop/**"]
    assert can_contain_included(".codex", patterns)
    assert can_contain_included(".codex/sessions", patterns)
    assert can_contain_included("AppData", patterns)
    assert can_contain_included("AppData/Roaming/Code/User", patterns)
    assert can_contain_included("Desktop/references", patterns)
    assert not can_contain_included("AppData/Local/Google", patterns)
    assert not can_contain_included("Windows", patterns)


def test_backup_sqlite_database_creates_readable_consistent_copy(tmp_path) -> None:
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "backup" / "copy.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample(value) VALUES (?)", ("kept",))
        connection.commit()

    assert backup_sqlite_database(source, target, logging.getLogger(__name__))

    with sqlite3.connect(target) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("kept",)


def test_backup_sqlite_database_skips_missing_source(tmp_path) -> None:
    assert not backup_sqlite_database(
        tmp_path / "missing.sqlite3",
        tmp_path / "copy.sqlite3",
        logging.getLogger(__name__),
    )


def test_iter_project_files_skips_dangling_symlinks(tmp_path) -> None:
    kept = tmp_path / "kept.txt"
    kept.write_text("important", encoding="utf-8")
    (tmp_path / "SingletonCookie").symlink_to("missing-cookie-target")

    files = iter_project_files(tmp_path, [])

    assert files == [kept]


def test_safe_copy_skips_source_removed_after_scan(tmp_path, caplog) -> None:
    source = tmp_path / "removed.txt"
    target = tmp_path / "backup" / "removed.txt"
    target.parent.mkdir()

    with caplog.at_level(logging.WARNING):
        copied = safe_copy(source, target, logging.getLogger(__name__))

    assert not copied
    assert not target.exists()
    assert "Skipped unavailable source" in caplog.text




def test_home_critical_excludes_generated_quality_artifacts_only() -> None:
    patterns = list(HOME_CRITICAL_EXCLUDES)
    assert is_ignored(
        "portfolio_projects/quality_system/artifacts/scan/screenshot.png",
        patterns,
    )
    assert is_ignored(
        "portfolio_projects/education_center_crm/.ruff_cache/CACHEDIR.TAG",
        patterns,
    )
    assert is_ignored(
        "portfolio_projects/education_center_crm/.pytest_cache/README.md",
        patterns,
    )
    assert not is_ignored(
        "portfolio_projects/quality_system/reports/latest.html",
        patterns,
    )


def test_default_excludes_python_tool_caches() -> None:
    patterns = list(DEFAULT_EXCLUDES)
    assert is_ignored(".pytest_cache/v/cache/nodeids", patterns)
    assert is_ignored("platform_v2/.ruff_cache/CACHEDIR.TAG", patterns)
    assert is_ignored("platform_v2/.mypy_cache/3.12/cache.json", patterns)


def test_home_critical_includes_terminal_reference() -> None:
    assert is_included("docs/terminal_commands_reference.md", list(HOME_CRITICAL_INCLUDES))


def test_home_critical_includes_migration_knowledge_and_research() -> None:
    patterns = list(HOME_CRITICAL_INCLUDES)
    assert is_included("docs/00_MASTER_PLAN.md", patterns)
    assert is_included("docs/terminal_commands_reference.md", patterns)
    assert is_included("docs/github-standard/GITHUB_PROJECT_STANDARD.md", patterns)
    assert is_included("research_snapshots/example/manifest.json", patterns)
    assert is_included("Screenshot/example.png", patterns)


def test_final_migration_profiles_include_private_and_windows_state() -> None:
    private_patterns = list(MIGRATION_PRIVATE_INCLUDES)
    windows_patterns = list(WINDOWS_CRITICAL_INCLUDES)
    assert is_included(".codex/sessions/2026/session.jsonl", private_patterns)
    assert is_included(".ssh/id_ed25519", private_patterns)
    assert is_included("SmartSignalHub/.env", private_patterns)
    assert is_included("runtime_archives/reset/database.sqlite3", private_patterns)
    assert is_included(".codex/sessions/2026/session.jsonl", windows_patterns)
    assert is_included("Desktop/references/photo.png", windows_patterns)
    assert ".env" in MIGRATION_ALLOWED_EXCLUDE_OVERRIDES
    assert "**/.git/**" in MIGRATION_ALLOWED_EXCLUDE_OVERRIDES


def test_smartsignalhub_required_paths_exist() -> None:
    assert all((PROJECT_ROOT / path).exists() for path in SMARTSIGNALHUB_REQUIRED_PATHS)


def test_verify_backup_checks_manifest_zip_sqlite_and_required_content(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "required.txt").write_text("restore me", encoding="utf-8")
    database = source / "sample.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample(value) VALUES ('kept')")
        connection.commit()

    backup_dir, _ = full_backup(source, tmp_path / "backups", "sample", [], logging.getLogger(__name__))

    assert verify_backup(backup_dir, logging.getLogger(__name__), required_paths=("required.txt",))


def test_verify_backup_rejects_corrupt_zip(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "required.txt").write_text("restore me", encoding="utf-8")
    backup_dir, zip_path = full_backup(source, tmp_path / "backups", "sample", [], logging.getLogger(__name__))
    zip_path.write_bytes(b"not a zip")

    assert not verify_backup(backup_dir, logging.getLogger(__name__), required_paths=("required.txt",))


def test_verify_backup_rejects_missing_required_content(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "present.txt").write_text("kept", encoding="utf-8")
    backup_dir, _ = full_backup(source, tmp_path / "backups", "sample", [], logging.getLogger(__name__))

    assert not verify_backup(backup_dir, logging.getLogger(__name__), required_paths=("missing.txt",))


def test_verify_backup_rejects_forbidden_secret_content(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".env").write_text("SECRET=must-not-be-backed-up", encoding="utf-8")
    backup_dir, _ = full_backup(source, tmp_path / "backups", "sample", [], logging.getLogger(__name__))

    assert not verify_backup(backup_dir, logging.getLogger(__name__))


def test_verify_backup_allows_explicit_private_migration_content(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".env").write_text("SECRET=explicitly-approved", encoding="utf-8")
    backup_dir, _ = full_backup(source, tmp_path / "backups", "private", [], logging.getLogger(__name__))

    assert verify_backup(
        backup_dir,
        logging.getLogger(__name__),
        allow_private_content=True,
    )
