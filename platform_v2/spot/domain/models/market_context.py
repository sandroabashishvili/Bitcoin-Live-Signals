"""File: market_context.py
Folder: platform_v2/spot/domain/models
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Bundle normalized market inputs before signal evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

from platform_v2.shared.backend.market.candle import Candle
from .indicator_snapshot import IndicatorSnapshot
from .orderbook_snapshot import OrderbookSnapshot


@dataclass(frozen=True)
class MarketContext:
    """Bundle the current normalized market inputs for one symbol and timeframe.

    Args:
        symbol: Instrument symbol.
        timeframe: Primary decision timeframe.
        latest_snapshot: Latest indicator snapshot for the same symbol/timeframe.
        latest_orderbook: Latest orderbook/trade-flow snapshot for the same symbol/timeframe.
        recent_candles: Recent closed candles used for context and validation.
        mtf_signals: Per-timeframe directional context used by the MTF gate.
        mtf_direction: Resolved MTF direction summary.
    """

    symbol: str
    timeframe: str
    latest_snapshot: IndicatorSnapshot
    latest_orderbook: OrderbookSnapshot | None
    recent_candles: tuple[Candle, ...]
    mtf_signals: dict[str, str]
    mtf_direction: str = "NO_SIGNAL"

    @property
    def latest_candle(self) -> Candle:
        """Return the most recent closed candle in the context."""

        return self.recent_candles[-1]
