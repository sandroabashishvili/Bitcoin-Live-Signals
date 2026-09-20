"""Build runtime storage paths for Futures engine."""

from __future__ import annotations

from pathlib import Path

from platform_v2.shared.backend.runtime_store import system_runtime_root



def futures_root() -> Path:
    return Path(__file__).resolve().parents[1]


def runtime_root() -> Path:
    return system_runtime_root("futures")


def runtime_data_root() -> Path:
    return runtime_root() / "data"


def family_dir(family_name: str) -> Path:
    return runtime_data_root() / family_name


def daily_json_path(family_name: str, date_iso: str) -> Path:
    return family_dir(family_name) / f"{family_name}_{date_iso}.json"


def candles_root() -> Path:
    return family_dir("candles_futures")


def candle_file_name(timeframe: str) -> str:
    return f"candles_{timeframe}.json"


def candle_file_path(symbol: str, timeframe: str) -> Path:
    return candles_root() / symbol / candle_file_name(timeframe)


def orderflow_root() -> Path:
    return family_dir("orderflow_futures")


def orderflow_file_name(timeframe: str) -> str:
    return f"orderflow_{timeframe}.json"


def orderflow_file_path(symbol: str, timeframe: str) -> Path:
    return orderflow_root() / symbol / orderflow_file_name(timeframe)


def indicator_snapshots_root() -> Path:
    return family_dir("indicator_snapshots_futures")


def indicator_snapshot_file_name(timeframe: str) -> str:
    return f"indicators_{timeframe}.json"


def indicator_snapshot_file_path(symbol: str, timeframe: str) -> Path:
    return indicator_snapshots_root() / symbol / indicator_snapshot_file_name(timeframe)


def state_dir() -> Path:
    return runtime_root() / "state"


def engine_state_path() -> Path:
    return state_dir() / "engine_state_futures.json"
