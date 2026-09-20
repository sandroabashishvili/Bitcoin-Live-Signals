"""Shared models for Futures simulation services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FuturesCycleSummary:
    signal: str
    position_event: str
    open_positions: int
    equity: float
    total_net_pnl: float
    total_gross_pnl: float
    total_fees_paid: float
    unrealized_pnl: float
    net_return_pct: float
    peak_capital: float
    lowest_capital: float
    signal_to_trade_conversion: float
    force_closes_by_reason: dict[str, int]
    score: float
    threshold: float
    direction_scores: dict[str, float]
    mtf_direction: str
    gates: dict[str, bool]
    permission_status: str
    permission_reason: str
    permission_text: str
    metrics_path: Path
