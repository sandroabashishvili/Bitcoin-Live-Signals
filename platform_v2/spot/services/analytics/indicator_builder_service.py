"""File: indicator_builder_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Build V2 indicator snapshots from V2 candle storage.
"""

from __future__ import annotations

from pathlib import Path

from platform_v2.shared.backend.market.candle import Candle
from platform_v2.shared.backend.persistence import replace_market_series
from platform_v2.spot.storage.paths import indicator_snapshot_file_path
from platform_v2.spot.services.analytics.indicator_snapshot_builder import IndicatorSnapshotBuilder
from platform_v2.spot.services.market.candle_reader_service import CandleReaderService


class IndicatorBuilderService:
    """Build and persist indicator snapshots from normalized candles."""

    def __init__(self, candle_reader_service: CandleReaderService | None = None) -> None:
        self._candle_reader_service = candle_reader_service or CandleReaderService()
        self._snapshot_builder = IndicatorSnapshotBuilder()

    def build_and_store(self, *, symbol: str, timeframe: str) -> Path | None:
        """Build indicator snapshots for one symbol/timeframe and persist them."""

        candles = self._candle_reader_service.read_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=None,
        )
        if len(candles) < 35:
            return None

        snapshots = self._build_snapshots(symbol=symbol, timeframe=timeframe, candles=candles)
        if not snapshots:
            return None

        target_path = indicator_snapshot_file_path(symbol, timeframe)
        replace_market_series(
            venue="binance",
            asset_class="crypto",
            market_type="spot",
            dataset="indicators",
            symbol=symbol,
            timeframe=timeframe,
            rows=snapshots,
            source_path=target_path,
        )
        return target_path

    def build_many(self, *, symbol: str, timeframes: tuple[str, ...] | list[str]) -> list[Path]:
        """Build indicator snapshots for multiple timeframes."""

        written_paths: list[Path] = []
        for timeframe in timeframes:
            path = self.build_and_store(symbol=symbol, timeframe=timeframe)
            if path is not None:
                written_paths.append(path)
        return written_paths

    def _build_snapshots(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[Candle],
    ) -> list[dict[str, object]]:
        """Build normalized snapshot payloads for all warm candles."""
        return self._snapshot_builder.build_rows(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
