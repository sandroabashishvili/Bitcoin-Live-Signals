"""Shared SQLite connection and schema-initialization primitives."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from platform_v2.shared.backend.time import utc_now_ms


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=5.0)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def initialize_sqlite_database(
    *,
    db_path: Path,
    schema_sql: str,
    schema_version: int,
) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect_sqlite(db_path)) as connection:
        connection.executescript(schema_sql)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at_ms) VALUES (?, ?)",
            (schema_version, utc_now_ms()),
        )
        connection.commit()
    return db_path
