"""File: candle_repository.py
Folder: platform_v2/spot/infrastructure/market_data
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Read candle data from storage and expose normalized V2 candle objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from platform_v2.shared.backend.market.candle import Candle
from platform_v2.shared.backend.persistence import read_market_series_safely
from ...storage.paths import candles_root as v2_candles_root
from platform_v2.shared.backend.time import utc_now_ms


class CandleRepository(Protocol):
    """Repository contract for normalized candle access."""

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
        closed_only: bool = True,
    ) -> list[Candle]:
        """Return normalized candles for a symbol and timeframe."""
        ...

    def get_closed_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> list[Candle]:
        """Return normalized closed candles for a symbol and timeframe."""
        ...


class JsonCandleRepository:
    """Read normalized candles from V2 candle storage."""

    def __init__(self, candles_root: Path | None = None) -> None:
        """Initialize the repository.

        Args:
            candles_root: Optional candle root directory.
        """

        self._use_database = candles_root is None
        if candles_root is None:
            candles_root = v2_candles_root()
        self._candles_root = candles_root

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
        closed_only: bool = True,
    ) -> list[Candle]:
        """Return normalized candles from the JSON source.

        Args:
            symbol: Instrument symbol.
            timeframe: Candle timeframe.
            limit: Optional maximum number of returned rows.
            closed_only: When True, filter out still-forming candles.

        Returns:
            list[Candle]: Normalized candles.
        """

        source_path = self._candles_root / symbol / f"{timeframe}.json"
        raw_rows = (
            read_market_series_safely(
                venue="binance",
                asset_class="crypto",
                market_type="spot",
                dataset="candles",
                symbol=symbol,
                timeframe=timeframe,
            )
            if self._use_database
            else []
        )
        if not raw_rows:
            if not source_path.exists():
                return []
            raw_rows = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(raw_rows, list):
            return []

        cutoff_ms = utc_now_ms()
        candles: list[Candle] = []

        for row in raw_rows:
            candle = self._parse_candle_row(symbol=symbol, timeframe=timeframe, row=row)
            if candle is None:
                continue

            if closed_only and candle.close_time_ms > cutoff_ms:
                continue

            candles.append(candle)

        if limit is not None and limit > 0:
            return candles[-limit:]

        return candles

    def get_closed_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> list[Candle]:
        """Return only closed candles from the JSON source."""

        return self.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            closed_only=True,
        )

    @staticmethod
    def _parse_candle_row(symbol: str, timeframe: str, row: object) -> Candle | None:
        """Parse one legacy candle row into a normalized Candle model."""

        if not isinstance(row, dict):
            return None

        try:
            return Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time_ms=int(row.get("timestamp", 0) or 0),
                close_time_ms=int(row.get("close_time", 0) or 0),
                open_price=float(row.get("open", 0.0) or 0.0),
                high_price=float(row.get("high", 0.0) or 0.0),
                low_price=float(row.get("low", 0.0) or 0.0),
                close_price=float(row.get("close", 0.0) or 0.0),
                volume=float(row.get("volume", 0.0) or 0.0),
            )
        except (TypeError, ValueError):
            return None
