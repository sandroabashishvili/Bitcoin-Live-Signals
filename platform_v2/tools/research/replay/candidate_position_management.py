"""Research-only dynamic position-management outcome policies."""

from __future__ import annotations

from bisect import bisect_right
from typing import Any

from platform_v2.tools.research.replay.candidate_signal_outcome_replay import _outcome
from platform_v2.tools.research.replay.historical_component_replay import _float


LONG_PROFIT_LOCK_70_25 = "long_profit_lock_70_25"


def managed_outcome(
    *,
    policy_ids: tuple[str, ...],
    candles: list[dict[str, Any]],
    candle_timestamps: list[int],
    entry_timestamp_ms: int,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    notional: float,
    entry_fee_rate: float,
    exit_fee_rate: float,
) -> dict[str, Any] | None:
    """Resolve an outcome under the promoted LONG management policy."""

    active = tuple(policy_id for policy_id in policy_ids if policy_id == LONG_PROFIT_LOCK_70_25)
    if not active:
        return _outcome(
            candles=candles,
            candle_timestamps=candle_timestamps,
            entry_timestamp_ms=entry_timestamp_ms,
            side=side,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            notional=notional,
            entry_fee_rate=entry_fee_rate,
            exit_fee_rate=exit_fee_rate,
        )
    if len(active) > 1:
        raise ValueError(f"Duplicate dynamic management policy: {active!r}")
    if str(side).upper() != "LONG":
        return _outcome(
            candles=candles,
            candle_timestamps=candle_timestamps,
            entry_timestamp_ms=entry_timestamp_ms,
            side=side,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            notional=notional,
            entry_fee_rate=entry_fee_rate,
            exit_fee_rate=exit_fee_rate,
        )
    return _long_profit_lock_outcome(
        candles=candles,
        candle_timestamps=candle_timestamps,
        entry_timestamp_ms=entry_timestamp_ms,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        notional=notional,
        entry_fee_rate=entry_fee_rate,
        exit_fee_rate=exit_fee_rate,
    )


def _long_profit_lock_outcome(
    *,
    candles: list[dict[str, Any]],
    candle_timestamps: list[int],
    entry_timestamp_ms: int,
    entry: float,
    stop_loss: float,
    take_profit: float,
    notional: float,
    entry_fee_rate: float,
    exit_fee_rate: float,
) -> dict[str, Any] | None:
    start = bisect_right(candle_timestamps, entry_timestamp_ms)
    if start >= len(candles) or entry <= 0 or notional <= 0 or take_profit <= entry:
        return None

    reward = take_profit - entry
    activation_price = entry + (0.70 * reward)
    protected_stop = entry + (0.25 * reward)
    protection_active = False
    activated_at_ms: int | None = None
    exit_price = _float(candles[-1].get("close"))
    exit_timestamp_ms = int(candles[-1]["timestamp_ms"])
    resolution = "DATA_END"

    for candle in candles[start:]:
        timestamp_ms = int(candle["timestamp_ms"])
        high = _float(candle.get("high"))
        low = _float(candle.get("low"))
        active_stop = protected_stop if protection_active else stop_loss
        stop_hit = low <= active_stop
        target_hit = high >= take_profit

        # Conservative ordering: a stop wins when both levels occur in one candle.
        if stop_hit:
            exit_price = active_stop
            resolution = "PROFIT_LOCK" if protection_active else "SL"
            exit_timestamp_ms = timestamp_ms
            break
        if target_hit:
            exit_price = take_profit
            resolution = "TP"
            exit_timestamp_ms = timestamp_ms
            break
        if not protection_active and high >= activation_price:
            # Activation is effective from the next closed candle. This avoids
            # inventing an unknowable intrabar order on the activation candle.
            protection_active = True
            activated_at_ms = timestamp_ms

    quantity = notional / entry
    gross_pnl = (exit_price - entry) * quantity
    entry_fee = notional * entry_fee_rate
    exit_fee = quantity * exit_price * exit_fee_rate
    return {
        "entry_timestamp_ms": entry_timestamp_ms,
        "exit_timestamp_ms": exit_timestamp_ms,
        "side": "LONG",
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "exit": round(exit_price, 2),
        "resolution": resolution,
        "gross_pnl": round(gross_pnl, 4),
        "fees": round(entry_fee + exit_fee, 4),
        "net_pnl": round(gross_pnl - entry_fee - exit_fee, 4),
        "management_policy": LONG_PROFIT_LOCK_70_25,
        "protection_activation_price": round(activation_price, 2),
        "protected_stop": round(protected_stop, 2),
        "protection_activated_at_ms": activated_at_ms,
    }
