"""Schema and connection setup for the market-data database."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from .database_paths import MARKET_DATA_DATABASE_PATH
from .sqlite_common import connect_sqlite, initialize_sqlite_database


SCHEMA_VERSION = 2
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS market_series (
    venue TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    market_type TEXT NOT NULL,
    dataset TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    payload_sha256 TEXT NOT NULL,
    source_path TEXT,
    updated_at_ms INTEGER NOT NULL,
    PRIMARY KEY (venue, asset_class, market_type, dataset, symbol, timeframe)
);

CREATE TABLE IF NOT EXISTS market_observations (
    venue TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    market_type TEXT NOT NULL,
    dataset TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    event_time_ms INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (
        venue, asset_class, market_type, dataset, symbol, timeframe,
        event_time_ms, ordinal
    ),
    FOREIGN KEY (venue, asset_class, market_type, dataset, symbol, timeframe)
        REFERENCES market_series(venue, asset_class, market_type, dataset, symbol, timeframe)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_market_observations_lookup
    ON market_observations(
        venue, asset_class, market_type, symbol, timeframe, dataset, event_time_ms
    );
"""


def connect_market_database(db_path: Path = MARKET_DATA_DATABASE_PATH) -> sqlite3.Connection:
    return connect_sqlite(db_path)


def initialize_market_database(db_path: Path = MARKET_DATA_DATABASE_PATH) -> Path:
    return initialize_sqlite_database(
        db_path=db_path,
        schema_sql=SCHEMA_SQL,
        schema_version=SCHEMA_VERSION,
    )
