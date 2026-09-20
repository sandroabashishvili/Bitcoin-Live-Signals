"""File: market_context_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Assemble normalized market context from repository-backed inputs.
"""

from __future__ import annotations

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.market_context import MarketContext
from platform_v2.spot.infrastructure.market_data.candle_repository import CandleRepository, JsonCandleRepository
from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import (
    IndicatorSnapshotRepository,
    JsonIndicatorSnapshotRepository,
)
from platform_v2.spot.infrastructure.market_data.orderbook_snapshot_repository import (
    JsonOrderbookSnapshotRepository,
    OrderbookSnapshotRepository,
)
from platform_v2.spot.services.signal.mtf_context_service import MultiTimeframeContextService


class MarketContextService:
    """Build current market context for downstream signal logic."""

    def __init__(
        self,
        candle_repository: CandleRepository | None = None,
        indicator_snapshot_repository: IndicatorSnapshotRepository | None = None,
        orderbook_snapshot_repository: OrderbookSnapshotRepository | None = None,
        mtf_context_service: MultiTimeframeContextService | None = None,
    ) -> None:
        """Initialize repositories for market context assembly."""

        self._candle_repository = candle_repository or JsonCandleRepository()
        self._indicator_snapshot_repository = (
            indicator_snapshot_repository or JsonIndicatorSnapshotRepository()
        )
        self._orderbook_snapshot_repository = (
            orderbook_snapshot_repository or JsonOrderbookSnapshotRepository()
        )
        self._mtf_context_service = mtf_context_service or MultiTimeframeContextService()

    def build_context(
        self,
        symbol: str,
        timeframe: str,
        candle_limit: int = settings.DEFAULT_CANDLE_LIMIT,
    ) -> MarketContext | None:
        """Build market context for one symbol and timeframe.

        Args:
            symbol: Instrument symbol.
            timeframe: Primary decision timeframe.
            candle_limit: Number of recent closed candles to include.

        Returns:
            MarketContext | None: Normalized market context or None when data is missing.
        """

        latest_snapshot = self._indicator_snapshot_repository.get_latest_snapshot(
            symbol=symbol,
            timeframe=timeframe,
        )
        if latest_snapshot is None:
            return None

        recent_candles = self._candle_repository.get_closed_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=candle_limit,
        )
        if not recent_candles:
            return None

        latest_orderbook = self._orderbook_snapshot_repository.get_latest_snapshot(
            symbol=symbol,
            timeframe=timeframe,
        )

        timeframe_snapshots = {
            tf: self._indicator_snapshot_repository.get_latest_snapshot(symbol=symbol, timeframe=tf)
            for tf in settings.DEFAULT_CANDLE_TIMEFRAMES
        }
        mtf_signals, mtf_direction = self._mtf_context_service.build_signals(
            timeframe_snapshots=timeframe_snapshots,
            primary_timeframe=timeframe,
        )

        return MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            latest_snapshot=latest_snapshot,
            latest_orderbook=latest_orderbook,
            recent_candles=tuple(recent_candles),
            mtf_signals=mtf_signals,
            mtf_direction=mtf_direction,
        )
