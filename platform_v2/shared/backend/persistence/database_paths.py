"""Canonical SQLite database boundaries for SmartSignalHub."""

from __future__ import annotations

from pathlib import Path


V2_ROOT = Path(__file__).resolve().parents[3]
DATABASE_ROOT = V2_ROOT / "runtime" / "database"

# Trading decisions, positions, capital, strategy/audit outputs, and runtime state.
TRADING_DATABASE_PATH = DATABASE_ROOT / "smartsignalhub_trading.sqlite3"

# Exchange/venue observations: candles, indicators, orderflow, and future assets.
MARKET_DATA_DATABASE_PATH = DATABASE_ROOT / "smartsignalhub_market_data.sqlite3"

# Public-site content such as collected news. Images and rendered HTML stay files.
CONTENT_DATABASE_PATH = DATABASE_ROOT / "smartsignalhub_content.sqlite3"

# Kept only so migration/backup tooling can recognize the pre-split pilot database.
LEGACY_RUNTIME_DATABASE_PATH = DATABASE_ROOT / "smartsignalhub_runtime.sqlite3"

ACTIVE_DATABASE_PATHS = (
    TRADING_DATABASE_PATH,
    MARKET_DATA_DATABASE_PATH,
    CONTENT_DATABASE_PATH,
)


def sqlite_sidecar_paths(path: Path) -> tuple[Path, Path, Path]:
    """Return the main SQLite file and its WAL/SHM sidecars."""

    return path, Path(f"{path}-wal"), Path(f"{path}-shm")
