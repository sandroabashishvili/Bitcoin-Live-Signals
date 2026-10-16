"""File: orderbook_snapshot.py
Folder: platform_v2/domain/models
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Normalized trade-flow/orderbook proxy snapshot for V2 signal decisions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderbookSnapshot:
    """Normalized trade-flow snapshot used as the V2 orderbook gate input."""

    symbol: str
    timeframe: str
    timestamp_text: str
    buyers: float
    sellers: float
    dominance_ratio: float
    imbalance: float
    momentum_classification: str
    period_count: int
    source: str = "binance_aggtrades"
    window_start_ms: int | None = None
    window_end_ms: int | None = None
    first_trade_ms: int | None = None
    last_trade_ms: int | None = None
    page_count: int = 0
    completeness: str = "LEGACY_UNKNOWN"
