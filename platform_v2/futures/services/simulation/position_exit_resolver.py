"""Resolve fixed and managed Futures exits from closed candles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platform_v2.futures.config import settings


LONG_PROFIT_LOCK_70_25 = "long_profit_lock_70_25"


@dataclass(frozen=True)
class PositionExitTrigger:
    """One deterministic exit trigger found in candle history."""

    candle: dict[str, Any]
    outcome: str
    exit_price: float
    management_policy: str | None = None


def build_position_management(*, side: str, entry: float, take_profit: float) -> dict[str, Any] | None:
    """Attach the promoted policy only to newly opened LONG positions."""

    if (
        not settings.LONG_PROFIT_LOCK_ENABLED
        or str(side).upper() != "LONG"
        or entry <= 0
        or take_profit <= entry
    ):
        return None
    reward = take_profit - entry
    activation_fraction = float(settings.LONG_PROFIT_LOCK_ACTIVATION_FRACTION)
    lock_fraction = float(settings.LONG_PROFIT_LOCK_FRACTION)
    return {
        "policy": LONG_PROFIT_LOCK_70_25,
        "activation_fraction": activation_fraction,
        "lock_fraction": lock_fraction,
        "activation_price": round(entry + (activation_fraction * reward), 2),
        "protected_stop": round(entry + (lock_fraction * reward), 2),
        "effective_from": f"next_closed_{settings.EXIT_MONITORING_TIMEFRAME}_candle",
    }


def resolve_position_exit(
    *,
    position: dict[str, Any],
    candles: list[dict[str, Any]],
) -> PositionExitTrigger | None:
    """Return the first exit using conservative stop-first candle ordering."""

    side = _position_side(position)
    entry = _float(position.get("entry_price"))
    take_profit = _float(position.get("tp_price"))
    original_stop = _float(position.get("sl_price"))
    if entry <= 0 or take_profit <= 0 or original_stop <= 0:
        return None

    management = position.get("position_management")
    policy = str(management.get("policy") or "") if isinstance(management, dict) else ""
    managed_long = policy == LONG_PROFIT_LOCK_70_25 and side == "LONG"
    activation_price = _float(management.get("activation_price")) if managed_long else 0.0
    protected_stop = _float(management.get("protected_stop")) if managed_long else 0.0
    managed_long = managed_long and entry < protected_stop < activation_price < take_profit
    protection_active = False

    for candle in candles:
        low = _float(candle.get("low") or candle.get("close"))
        high = _float(candle.get("high") or candle.get("close"))
        active_stop = protected_stop if protection_active else original_stop

        # The stop wins if both stop and target are touched in one monitoring candle.
        if side == "SHORT":
            if high >= original_stop:
                return PositionExitTrigger(candle, "SL_HIT", original_stop)
            if low <= take_profit:
                return PositionExitTrigger(candle, "TP_HIT", take_profit)
        else:
            if low <= active_stop:
                outcome = "PROFIT_LOCK_HIT" if protection_active else "SL_HIT"
                return PositionExitTrigger(
                    candle,
                    outcome,
                    active_stop,
                    LONG_PROFIT_LOCK_70_25 if protection_active else None,
                )
            if high >= take_profit:
                return PositionExitTrigger(candle, "TP_HIT", take_profit)

        # A high on this candle activates protection for the next closed candle.
        if managed_long and not protection_active and high >= activation_price:
            protection_active = True
    return None


def _position_side(position: dict[str, Any]) -> str:
    side = str(position.get("side") or "LONG").upper()
    if side == "SELL":
        return "SHORT"
    return "LONG" if side == "BUY" else side


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
