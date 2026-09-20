"""File: candle_reader_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Thin wrapper around candle repository for service-side candle reads.
"""

from __future__ import annotations

from platform_v2.spot.config import settings
from platform_v2.shared.backend.market.candle import Candle
from platform_v2.spot.infrastructure.market_data.candle_repository import CandleRepository, JsonCandleRepository


class CandleReaderService:
    """Read candles from the current V2 candle repository."""

    def __init__(self, candle_repository: CandleRepository | None = None) -> None:
        self._candle_repository = candle_repository or JsonCandleRepository()

    def read_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int | None = settings.DEFAULT_FETCH_LIMIT,
    ) -> list[Candle]:
        return self._candle_repository.get_closed_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
