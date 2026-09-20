"""Runtime read/write helpers for Futures simulation data families."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    METRICS_FAMILY,
    append_runtime_record,
    load_family_rows,
    load_family_rows_all,
    store_runtime_snapshot,
    upsert_runtime_row,
)
from platform_v2.futures.storage import (
    candle_file_path,
    load_json_list,
)


class FuturesSimulationRuntimeStore:
    def load_candles(self, *, symbol: str, timeframe: str) -> list[dict[str, Any]]:
        return load_json_list(candle_file_path(symbol, timeframe))

    def append_daily_row(self, *, family_name: str, date_iso: str, row: dict[str, Any]) -> None:
        append_runtime_record(family_name, date_iso, row)

    def upsert_daily_row(
        self,
        *,
        family_name: str,
        date_iso: str,
        row: dict[str, Any],
        match_keys: tuple[str, ...],
    ) -> None:
        upsert_runtime_row(
            family_name=family_name,
            date_iso=date_iso,
            row=row,
            match_keys=match_keys,
        )

    def store_metrics(self, *, metrics: dict[str, Any], date_iso: str) -> Path:
        return store_runtime_snapshot(METRICS_FAMILY, date_iso, metrics)

    def load_family_rows(self, *, family_name: str, date_iso: str) -> list[dict[str, Any]]:
        return load_family_rows(family_name, date_iso)

    def load_family_rows_all(self, *, family_name: str) -> list[dict[str, Any]]:
        return load_family_rows_all(family_name)
