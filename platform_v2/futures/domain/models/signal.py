"""File: signal.py
Folder: platform_v2/domain/models
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Core signal-side domain models for SmartSignalHub V2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SignalSide(str, Enum):
    """Supported signal directions."""

    BUY = "BUY"
    SELL = "SELL"
    NO_SIGNAL = "NO_SIGNAL"


@dataclass(frozen=True)
class GateSnapshot:
    """Decision-gate states for a signal.

    Args:
        mtf: Multi-timeframe gate result.
        regime: Regime gate result.
        momentum: Momentum gate result.
        trend: Trend gate result.
        orderbook: Orderbook gate result.
        structure: Structure gate result.
    """

    mtf: bool = False
    regime: bool = False
    momentum: bool = False
    trend: bool = False
    orderbook: bool = False
    structure: bool = False


@dataclass(frozen=True)
class TheoreticalSetup:
    """Theoretical setup derived from a signal snapshot.

    Args:
        entry_price: Snapshot entry price.
        stop_loss: Theoretical stop-loss level.
        take_profit: Theoretical take-profit level.
        rr_ratio: Risk-reward ratio.
        mode: SL/TP mode identifier.
    """

    entry_price: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    mode: str = "unknown"


@dataclass(frozen=True)
class SignalDecision:
    """Normalized signal decision used across V2.

    Args:
        timestamp_ms: Decision timestamp in milliseconds.
        symbol: Instrument symbol.
        timeframe: Decision timeframe.
        side: Signal direction.
        snapshot_price: Price used during signal evaluation.
        score: Signal score.
        threshold: Minimum threshold required for action.
        gates: Gate snapshot.
        reasons: Human-readable explanation list.
        mtf_signals: Per-timeframe directional context used during the decision.
        mtf_direction: Resolved MTF direction summary.
        theoretical_setup: Optional theoretical SL/TP setup.
        strategy_version: Version label for the scoring rules used.
        direction_thresholds: Threshold used for each evaluated direction.
        direction_component_weights: Weights used for each evaluated direction.
    """

    timestamp_ms: int
    symbol: str
    timeframe: str
    side: SignalSide
    snapshot_price: float
    score: float
    threshold: float
    gates: GateSnapshot = field(default_factory=GateSnapshot)
    reasons: tuple[str, ...] = ()
    mtf_signals: dict[str, str] = field(default_factory=dict)
    mtf_direction: str = "NO_SIGNAL"
    theoretical_setup: TheoreticalSetup | None = None
    selected_direction: str = "NO_SIGNAL"
    direction_scores: dict[str, float] = field(default_factory=dict)
    direction_gates: dict[str, GateSnapshot] = field(default_factory=dict)
    direction_reasons: dict[str, tuple[str, ...]] = field(default_factory=dict)
    direction_component_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    strategy_version: str = "unknown"
    direction_thresholds: dict[str, float] = field(default_factory=dict)
    direction_component_weights: dict[str, dict[str, float]] = field(default_factory=dict)
