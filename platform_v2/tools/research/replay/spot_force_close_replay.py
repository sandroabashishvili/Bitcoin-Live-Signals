"""Spot minus-rule force-close parity for state-aware research replay."""

from __future__ import annotations

from bisect import bisect_right
from typing import Any

from platform_v2.tools.research.replay.portfolio_replay_state import OpenPosition


def apply_minus_rule_force_closes(
    *,
    open_positions: list[OpenPosition],
    timestamp_ms: int,
    candles: list[dict[str, Any]],
    candle_timestamps: list[int],
    weak_open_position_pct: float,
    exit_fee_rate: float,
) -> tuple[list[OpenPosition], list[dict[str, Any]]]:
    """Close profitable peers when one open Spot position breaches the weak limit."""

    candle_index = bisect_right(candle_timestamps, timestamp_ms) - 1
    if not open_positions or candle_index < 0:
        return open_positions, []

    candle = candles[candle_index]
    close_price = float(candle.get("close") or 0.0)
    close_timestamp_ms = int(candle.get("timestamp_ms") or 0)
    if close_price <= 0 or close_timestamp_ms <= 0:
        return open_positions, []

    trigger = next(
        (
            position
            for position in open_positions
            if _unrealized_pct(position, close_price) <= weak_open_position_pct
        ),
        None,
    )
    if trigger is None:
        return open_positions, []

    remaining: list[OpenPosition] = []
    forced: list[dict[str, Any]] = []
    for position in open_positions:
        gross_pnl = _gross_pnl(position, close_price)
        if position is trigger or gross_pnl <= 0.0:
            remaining.append(position)
            continue
        forced.append(
            _forced_outcome(
                position=position,
                trigger=trigger,
                close_price=close_price,
                close_timestamp_ms=close_timestamp_ms,
                gross_pnl=gross_pnl,
                exit_fee_rate=exit_fee_rate,
            )
        )
    return remaining, forced


def _gross_pnl(position: OpenPosition, close_price: float) -> float:
    if position.entry <= 0 or position.margin <= 0:
        return 0.0
    quantity = position.margin / position.entry
    return (close_price - position.entry) * quantity


def _unrealized_pct(position: OpenPosition, close_price: float) -> float:
    if position.margin <= 0:
        return 0.0
    return _gross_pnl(position, close_price) / position.margin


def _forced_outcome(
    *,
    position: OpenPosition,
    trigger: OpenPosition,
    close_price: float,
    close_timestamp_ms: int,
    gross_pnl: float,
    exit_fee_rate: float,
) -> dict[str, Any]:
    exit_fee = position.margin * exit_fee_rate
    source = position.outcome
    return {
        **source,
        "exit_timestamp_ms": close_timestamp_ms,
        "exit": round(close_price, 2),
        "resolution": "FORCE_CLOSE",
        "gross_pnl": round(gross_pnl, 4),
        "fees": round(position.entry_fee + exit_fee, 4),
        "net_pnl": round(gross_pnl - position.entry_fee - exit_fee, 4),
        "was_force_closed": True,
        "force_close_reason": "minus_rule",
        "force_close_trigger_entry_timestamp_ms": trigger.entry_timestamp_ms,
        "force_close_trigger_unrealized_pct": round(
            _unrealized_pct(trigger, close_price),
            8,
        ),
    }
