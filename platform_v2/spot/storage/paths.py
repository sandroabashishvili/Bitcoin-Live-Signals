"""File: paths.py
Folder: platform_v2/spot/storage
Created date: 2026-03-25
Last updated date: 2026-03-31
Author: Codex
Purpose: Build runtime storage paths for SmartSignalHub V2.
"""

from __future__ import annotations

from pathlib import Path

from platform_v2.shared.backend.runtime_store import system_runtime_root


def runtime_root() -> Path:
    """Return the root runtime directory for V2."""

    return system_runtime_root("spot")


def runtime_data_root() -> Path:
    """Return the root path for runtime JSON data files."""

    return runtime_root() / "data"


def family_dir(family_name: str) -> Path:
    """Return the directory for a specific runtime data family."""

    return runtime_data_root() / family_name


def daily_json_path(family_name: str, date_iso: str) -> Path:
    """Return the daily JSON path for a runtime data family."""

    return family_dir(family_name) / f"{family_name}_{date_iso}.json"


def candles_root() -> Path:
    """Return the root directory for V2 candle storage."""

    return runtime_data_root() / "candles"


def candle_file_path(symbol: str, timeframe: str) -> Path:
    """Return the V2 candle JSON path for one symbol and timeframe."""

    return candles_root() / symbol / f"{timeframe}.json"


def indicator_snapshots_root() -> Path:
    """Return the root directory for V2 indicator snapshot storage."""

    return runtime_data_root() / "indicator_snapshots"


def indicator_snapshot_file_path(symbol: str, timeframe: str) -> Path:
    """Return the V2 indicator snapshot JSON path for one symbol and timeframe."""

    return indicator_snapshots_root() / symbol / f"{timeframe}.json"


def orderflow_root() -> Path:
    """Return the root directory for V2 orderflow storage."""

    return runtime_data_root() / "orderflow"


def orderflow_file_path(symbol: str, timeframe: str) -> Path:
    """Return the V2 orderflow JSON path for one symbol and timeframe."""

    return orderflow_root() / symbol / f"{timeframe}.json"
