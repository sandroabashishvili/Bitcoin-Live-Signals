"""SQLite runtime database path, feature gates, schema, and connection setup."""

from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
from typing import Any

from .database_paths import TRADING_DATABASE_PATH
from .sqlite_common import connect_sqlite, initialize_sqlite_database


DEFAULT_DATABASE_PATH = TRADING_DATABASE_PATH
MIRROR_ENABLED = os.environ.get("SMARTSIGNALHUB_SQLITE_MIRROR", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
PRIMARY_READ_ENABLED = os.environ.get("SMARTSIGNALHUB_SQLITE_PRIMARY", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SCHEMA_VERSION = 3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_documents (
    system TEXT NOT NULL,
    family TEXT NOT NULL,
    date_iso TEXT NOT NULL,
    payload_type TEXT NOT NULL CHECK (payload_type IN ('list', 'object')),
    row_count INTEGER NOT NULL,
    payload_sha256 TEXT NOT NULL,
    source_path TEXT,
    updated_at_ms INTEGER NOT NULL,
    PRIMARY KEY (system, family, date_iso)
);

CREATE TABLE IF NOT EXISTS runtime_rows (
    system TEXT NOT NULL,
    family TEXT NOT NULL,
    date_iso TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    timestamp_ms INTEGER,
    entity_id TEXT,
    symbol TEXT,
    side TEXT,
    status TEXT,
    net_pnl REAL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (system, family, date_iso, ordinal),
    FOREIGN KEY (system, family, date_iso)
        REFERENCES runtime_documents(system, family, date_iso)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runtime_rows_time
    ON runtime_rows(system, family, timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_runtime_rows_entity
    ON runtime_rows(system, family, entity_id);
CREATE INDEX IF NOT EXISTS idx_runtime_rows_side_status
    ON runtime_rows(system, family, side, status);

CREATE TABLE IF NOT EXISTS runtime_state (
    system TEXT NOT NULL,
    state_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    PRIMARY KEY (system, state_key)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    return connect_sqlite(db_path)


def initialize_database(db_path: Path = DEFAULT_DATABASE_PATH) -> Path:
    return initialize_sqlite_database(
        db_path=db_path,
        schema_sql=SCHEMA_SQL,
        schema_version=SCHEMA_VERSION,
    )


def database_status(db_path: Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "path": str(db_path),
            "exists": False,
            "size_bytes": 0,
            "schema_version": 0,
            "documents": 0,
            "rows": 0,
            "states": 0,
        }
    with closing(connect(db_path)) as connection:
        schema_version = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()[0]
        documents = connection.execute("SELECT COUNT(*) FROM runtime_documents").fetchone()[0]
        rows = connection.execute("SELECT COUNT(*) FROM runtime_rows").fetchone()[0]
        states = connection.execute("SELECT COUNT(*) FROM runtime_state").fetchone()[0]
    return {
        "path": str(db_path),
        "exists": True,
        "size_bytes": db_path.stat().st_size,
        "schema_version": int(schema_version),
        "documents": int(documents),
        "rows": int(rows),
        "states": int(states),
    }
