"""File: builder_service.py
Folder: platform_v2/futures/services/analytics/indicator_pipeline
Created date: 2026-04-19
Last updated date: 2026-05-14
Author: Codex
Purpose: Build and persist Futures indicator snapshots from Futures candles.
"""

from __future__ import annotations

from pathlib import Path

from platform_v2.futures.infrastructure.market_data import JsonCandleRepository
from platform_v2.shared.backend.persistence import replace_market_series
from .snapshot_builder import IndicatorSnapshotBuilder
from platform_v2.futures.storage import indicator_snapshot_file_path


class FuturesIndicatorBuilderService:
    """Persist indicator snapshots for Futures-only runtime inspection."""

    def __init__(self, candle_repository: JsonCandleRepository | None = None) -> None:
        self._candle_repository = candle_repository or JsonCandleRepository()
        self._snapshot_builder = IndicatorSnapshotBuilder()

    def build_and_store(self, *, symbol: str, timeframe: str) -> Path | None:
        candles = self._candle_repository.get_closed_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=None,
        )
        if len(candles) < 35:
            return None

        snapshots = self._snapshot_builder.build_rows(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
        if not snapshots:
            return None

        target_path = indicator_snapshot_file_path(symbol, timeframe)
        replace_market_series(
            venue="binance",
            asset_class="crypto",
            market_type="futures",
            dataset="indicators",
            symbol=symbol,
            timeframe=timeframe,
            rows=snapshots,
            source_path=target_path,
        )
        return target_path

    def build_many(self, *, symbol: str, timeframes: tuple[str, ...] | list[str]) -> list[Path]:
        written_paths: list[Path] = []
        for timeframe in timeframes:
            path = self.build_and_store(symbol=symbol, timeframe=timeframe)
            if path is not None:
                written_paths.append(path)
        return written_paths
