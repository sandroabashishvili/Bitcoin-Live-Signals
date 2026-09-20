"""Compatibility reader exports for Futures runtime ledger."""

from __future__ import annotations

from pathlib import Path

from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.shared.backend.runtime_store.futures import (
    load_family_rows,
    load_family_rows_all,
    load_json_dict,
    load_json_list as load_runtime_json_list,
)


def load_json_list(path: Path):
    dataset = _market_dataset(path)
    if dataset is not None:
        rows = read_market_series_safely(
            venue="binance",
            asset_class="crypto",
            market_type="futures",
            dataset=dataset,
            symbol=path.parent.name,
            timeframe=_market_timeframe(path),
        )
        if rows:
            return rows
    return load_runtime_json_list(path)


def _market_dataset(path: Path) -> str | None:
    parts = set(path.parts)
    if "candles_futures" in parts:
        return "candles"
    if "indicator_snapshots_futures" in parts:
        return "indicators"
    if "orderflow_futures" in parts:
        return "orderflow"
    return None


def _market_timeframe(path: Path) -> str:
    stem = path.stem
    for prefix in ("candles_", "indicators_", "orderflow_"):
        if stem.startswith(prefix):
            return stem.removeprefix(prefix)
    return stem

__all__ = [
    "load_family_rows",
    "load_family_rows_all",
    "load_json_dict",
    "load_json_list",
]
