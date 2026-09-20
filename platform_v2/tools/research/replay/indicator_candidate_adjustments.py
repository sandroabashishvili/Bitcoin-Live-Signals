"""Research-only component adjustments for narrow indicator-band candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platform_v2.tools.research.replay.candidate_profiles import CandidateProfile


def adjusted_components(
    *,
    profile: CandidateProfile,
    components: dict[str, float],
    snapshot: Any,
) -> dict[str, float]:
    """Return a copied component map with declared research adjustments applied."""

    result = {name: float(value) for name, value in components.items()}
    for adjustment_id in profile.adjustment_ids:
        _apply(adjustment_id=adjustment_id, components=result, snapshot=snapshot)
    return {name: round(max(0.0, value), 4) for name, value in result.items()}


def _apply(*, adjustment_id: str, components: dict[str, float], snapshot: Any) -> None:
    values = _IndicatorValues.from_snapshot(snapshot)
    if _apply_long_rsi(adjustment_id, components, values):
        return
    if _apply_long_macd(adjustment_id, components, values):
        return
    if _apply_short(adjustment_id, components, values):
        return
    raise ValueError(f"Unknown indicator candidate adjustment: {adjustment_id}")


def _apply_long_rsi(
    adjustment_id: str,
    components: dict[str, float],
    values: "_IndicatorValues",
) -> bool:
    if adjustment_id == "long_rsi_momentum_disabled":
        components["momentum"] = (
            components.get("momentum", 0.0) - _current_long_rsi_reward(values.rsi)
        )
        return True
    if adjustment_id == "long_rsi_momentum_pullback_map":
        components["momentum"] = (
            components.get("momentum", 0.0)
            - _current_long_rsi_reward(values.rsi)
            + _pullback_long_rsi_reward(values.rsi)
        )
        return True
    if adjustment_id == "long_rsi_58_65_reward_zero":
        if values.rsi is not None and 58.0 <= values.rsi < 65.0:
            components["momentum"] = components.get("momentum", 0.0) - 1.4
        return True
    if adjustment_id == "long_rsi_58_65_reward_half":
        if values.rsi is not None and 58.0 <= values.rsi < 65.0:
            components["momentum"] = components.get("momentum", 0.0) - 0.7
        return True
    return False


def _apply_long_macd(
    adjustment_id: str,
    components: dict[str, float],
    values: "_IndicatorValues",
) -> bool:
    if adjustment_id == "long_macd_alignment_reward_zero":
        if values.macd_aligned:
            components["momentum"] = components.get("momentum", 0.0) - 0.8
        return True
    if adjustment_id == "long_macd_alignment_reward_half":
        if values.macd_aligned:
            components["momentum"] = components.get("momentum", 0.0) - 0.4
        return True
    if adjustment_id == "long_macd_spread_02_05_reward_zero":
        spread_atr = values.long_macd_spread_atr
        if spread_atr is not None and 0.2 <= spread_atr < 0.5:
            components["momentum"] = components.get("momentum", 0.0) - 0.8
        return True
    if adjustment_id == "long_macd_alignment_zero_when_atr_growth_005":
        if (
            values.macd_aligned
            and values.atr_growth is not None
            and values.atr_growth >= 0.05
        ):
            components["momentum"] = components.get("momentum", 0.0) - 0.8
        return True
    macd_rsi_thresholds = {
        "long_macd_alignment_zero_when_rsi_55": 55.0,
        "long_macd_alignment_zero_when_rsi_58": 58.0,
        "long_macd_alignment_zero_when_rsi_60": 60.0,
        "long_macd_alignment_zero_when_rsi_65": 65.0,
    }
    if adjustment_id in macd_rsi_thresholds:
        if (
            values.macd_aligned
            and values.rsi is not None
            and values.rsi >= macd_rsi_thresholds[adjustment_id]
        ):
            components["momentum"] = components.get("momentum", 0.0) - 0.8
        return True
    return False


def _apply_short(
    adjustment_id: str,
    components: dict[str, float],
    values: "_IndicatorValues",
) -> bool:
    if adjustment_id == "short_macd_spread_0_02_reward_zero":
        spread_atr = values.short_macd_spread_atr
        if spread_atr is not None and 0.0 <= spread_atr < 0.2:
            components["momentum"] = components.get("momentum", 0.0) - 0.9
        return True
    if adjustment_id == "short_structure_distance_15_25_reward_zero":
        distance = values.short_swing_distance_atr
        if distance is not None and 1.5 <= distance < 2.5:
            components["structure"] = components.get("structure", 0.0) - 1.3
        return True
    if adjustment_id == "short_di_alignment_reward_zero":
        if values.short_di_aligned:
            components["trend"] = components.get("trend", 0.0) - 1.0
        return True
    return False


@dataclass(frozen=True)
class _IndicatorValues:
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    atr: float | None
    price: float | None
    swing_high: float | None
    adx: float | None
    plus_di: float | None
    minus_di: float | None
    atr_growth: float | None

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> "_IndicatorValues":
        return cls(
            rsi=_optional_float(getattr(snapshot, "rsi", None)),
            macd=_optional_float(getattr(snapshot, "macd", None)),
            macd_signal=_optional_float(getattr(snapshot, "macd_signal", None)),
            atr=_optional_float(getattr(snapshot, "atr", None)),
            price=_optional_float(getattr(snapshot, "price", None)),
            swing_high=_optional_float(getattr(snapshot, "swing_high", None)),
            adx=_optional_float(getattr(snapshot, "adx", None)),
            plus_di=_optional_float(getattr(snapshot, "plus_di", None)),
            minus_di=_optional_float(getattr(snapshot, "minus_di", None)),
            atr_growth=_optional_float(getattr(snapshot, "atr_growth_20", None)),
        )

    @property
    def macd_aligned(self) -> bool:
        return (
            self.macd is not None
            and self.macd_signal is not None
            and self.macd >= self.macd_signal
        )

    @property
    def long_macd_spread_atr(self) -> float | None:
        if None in (self.macd, self.macd_signal, self.atr) or not self.atr:
            return None
        return (self.macd - self.macd_signal) / self.atr

    @property
    def short_macd_spread_atr(self) -> float | None:
        spread = self.long_macd_spread_atr
        return -spread if spread is not None else None

    @property
    def short_swing_distance_atr(self) -> float | None:
        if None in (self.swing_high, self.price, self.atr) or not self.atr:
            return None
        return (self.swing_high - self.price) / self.atr

    @property
    def short_di_aligned(self) -> bool:
        return bool(
            None not in (self.adx, self.plus_di, self.minus_di)
            and self.adx >= 20.0
            and self.minus_di > self.plus_di
        )


def _current_long_rsi_reward(rsi: float | None) -> float:
    if rsi is None:
        return 0.0
    if 52.0 <= rsi < 58.0:
        return 1.0
    if 58.0 <= rsi < 65.0:
        return 1.4
    if 65.0 <= rsi < 72.0:
        return 0.8
    if 50.0 <= rsi < 52.0:
        return 0.5
    return 0.0


def _pullback_long_rsi_reward(rsi: float | None) -> float:
    if rsi is None:
        return 0.0
    if 40.0 <= rsi <= 55.0:
        return 0.8
    if 35.0 <= rsi < 40.0:
        return 0.4
    if 55.0 < rsi <= 60.0:
        return 0.2
    return 0.0


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
