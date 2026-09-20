"""Shared adaptive SL/TP contracts for Spot and Futures."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SlTpInputs:
    side: str
    entry: float
    atr: float
    fee_buffer_pct: float
    swing_low: float | None = None
    swing_high: float | None = None
    ema50: float | None = None
    kijun: float | None = None
    resistance_level: float | None = None
    liquidity_zone: float | None = None
    liquidity_tolerance: float = 100.0
    adx: float | None = None
    confidence: float | None = None
    min_rrr: float = 1.5
    max_rrr: float = 2.4
    min_effective_rrr_after_clamp: float = 1.5
    sl_atr_mult: float = 1.3
    min_sl_atr_mult: float = 0.9
    max_sl_atr_mult: float = 2.2
    level_buffer_atr: float = 0.15
    use_psych_levels: bool = True
    psych_steps: list[float] | None = None


@dataclass(frozen=True)
class StopLossResult:
    stop_loss: float
    risk: float
    source: str
    debug: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TakeProfitResult:
    take_profit: float
    rr_ratio: float
    source: str
    debug: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SlTpPayload:
    stop_loss: float
    take_profit: float
    rr_ratio: float
    risk: float
    mode: str = "adaptive_v2"
    debug: tuple[str, ...] = field(default_factory=tuple)
