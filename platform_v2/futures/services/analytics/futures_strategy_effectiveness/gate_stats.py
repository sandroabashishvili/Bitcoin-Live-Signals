"""File: gate_stats.py
Folder: platform_v2/futures/services/analytics/futures_strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Gate effectiveness aggregation for Futures strategy analytics.
"""

from __future__ import annotations

from typing import Any

from .outcome import (
    build_signal_lookup,
    closed_trade_outcome_key,
    load_candle_rows,
    net_pnl_value,
    signal_direction,
    signal_lookup_key_from_position,
    theoretical_outcome,
)
from .types import (
    ClosedTradeLogicEvaluationRow,
    ClosedTradeLogicEvaluationTotals,
    GateEffectivenessStat,
    LogicEvaluationRow,
    LogicEvaluationTotals,
)


ClosedTradeGateStat = dict[str, float | int]


def gate_effectiveness(
    signal_rows: list[dict[str, Any]],
    *,
    gate_names: tuple[str, ...],
) -> dict[str, GateEffectivenessStat]:
    stats: dict[str, GateEffectivenessStat] = {
        gate_name: {"participated": 0, "tp": 0, "sl": 0, "open": 0, "win_rate": 0.0}
        for gate_name in gate_names
    }
    buy_rows = [row for row in signal_rows if signal_direction(row) == "LONG"]
    candle_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in buy_rows:
        theoretical_setup = row.get("theoretical_setup")
        if not isinstance(theoretical_setup, dict):
            continue
        symbol = str(row.get("symbol") or "")
        timeframe = str(row.get("timeframe") or "")
        cache_key = (symbol, timeframe)
        if cache_key not in candle_cache:
            candle_cache[cache_key] = load_candle_rows(symbol=symbol, timeframe=timeframe)
        outcome = theoretical_outcome(row=row, candles=candle_cache[cache_key])
        gates = row.get("gates") or {}
        if not isinstance(gates, dict):
            continue
        for gate_name in gate_names:
            if not gates.get(gate_name):
                continue
            gate_stats = stats[gate_name]
            gate_stats["participated"] += 1
            gate_stats[outcome] += 1

    for gate_stats in stats.values():
        resolved = gate_stats["tp"] + gate_stats["sl"]
        gate_stats["win_rate"] = (gate_stats["tp"] / resolved * 100.0) if resolved else 0.0
    return stats


def closed_trade_gate_effectiveness(
    *,
    signal_rows: list[dict[str, Any]],
    closed_positions: list[Any],
    gate_names: tuple[str, ...],
) -> dict[str, ClosedTradeGateStat]:
    stats: dict[str, ClosedTradeGateStat] = {
        gate_name: {
            "participated": 0,
            "tp": 0,
            "sl": 0,
            "profit_lock": 0,
            "force_close": 0,
            "wins": 0,
            "win_rate": 0.0,
        }
        for gate_name in gate_names
    }
    signal_lookup = build_signal_lookup(signal_rows)

    for position in closed_positions:
        lookup_key = signal_lookup_key_from_position(position)
        if lookup_key is None:
            continue
        signal_row = signal_lookup.get(lookup_key)
        if signal_row is None:
            continue
        gates = signal_row.get("gates")
        if not isinstance(gates, dict):
            continue

        outcome_key = closed_trade_outcome_key(position)
        is_win = net_pnl_value(position) > 0.0
        for gate_name in gate_names:
            if not gates.get(gate_name):
                continue
            gate_stats = stats[gate_name]
            gate_stats["participated"] = int(gate_stats["participated"]) + 1
            gate_stats[outcome_key] = int(gate_stats[outcome_key]) + 1
            if is_win:
                gate_stats["wins"] = int(gate_stats["wins"]) + 1

    for gate_stats in stats.values():
        participated = int(gate_stats["participated"])
        wins = int(gate_stats["wins"])
        gate_stats["win_rate"] = (wins / participated * 100.0) if participated else 0.0
    return stats


def build_group_rows(
    gate_names: tuple[str, ...],
    stats_by_gate: dict[str, GateEffectivenessStat],
) -> tuple[list[LogicEvaluationRow], LogicEvaluationTotals]:
    rows: list[LogicEvaluationRow] = []
    total_tp = 0
    total_sl = 0
    total_open = 0

    for gate_name in gate_names:
        stats = stats_by_gate.get(
            gate_name,
            {"participated": 0, "tp": 0, "sl": 0, "open": 0, "win_rate": 0.0},
        )
        participated = int(stats["participated"])
        tp = int(stats["tp"])
        sl = int(stats["sl"])
        open_count = int(stats["open"])
        total_tp += tp
        total_sl += sl
        total_open += open_count
        resolved = tp + sl
        win_rate = (tp / resolved * 100.0) if resolved else 0.0
        rows.append(
            {
                "gate": gate_name.upper(),
                "participated": participated,
                "tp": tp,
                "sl": sl,
                "open": open_count,
                "win_rate": round(win_rate, 2),
            }
        )

    total_resolved = total_tp + total_sl
    total_win_rate = (total_tp / total_resolved * 100.0) if total_resolved else 0.0
    return rows, {
        "tp": total_tp,
        "sl": total_sl,
        "open": total_open,
        "win_rate": round(total_win_rate, 2),
    }


def build_closed_trade_group_rows(
    gate_names: tuple[str, ...],
    stats_by_gate: dict[str, ClosedTradeGateStat],
) -> tuple[list[ClosedTradeLogicEvaluationRow], ClosedTradeLogicEvaluationTotals]:
    rows: list[ClosedTradeLogicEvaluationRow] = []
    total_tp = 0
    total_sl = 0
    total_profit_lock = 0
    total_force_close = 0
    win_rate_values: list[float] = []

    for gate_name in gate_names:
        stats = stats_by_gate.get(
            gate_name,
            {
                "participated": 0,
                "tp": 0,
                "sl": 0,
                "profit_lock": 0,
                "force_close": 0,
                "wins": 0,
                "win_rate": 0.0,
            },
        )
        participated = int(stats["participated"])
        tp = int(stats["tp"])
        sl = int(stats["sl"])
        profit_lock = int(stats["profit_lock"])
        force_close = int(stats["force_close"])
        total_tp += tp
        total_sl += sl
        total_profit_lock += profit_lock
        total_force_close += force_close
        if participated:
            win_rate_values.append(float(stats["win_rate"]))
        rows.append(
            {
                "gate": gate_name.upper(),
                "participated": participated,
                "tp": tp,
                "sl": sl,
                "profit_lock": profit_lock,
                "force_close": force_close,
                "win_rate": round(float(stats["win_rate"]), 2),
            }
        )

    total_win_rate = (
        sum(win_rate_values) / len(win_rate_values) if win_rate_values else 0.0
    )
    return rows, {
        "tp": total_tp,
        "sl": total_sl,
        "profit_lock": total_profit_lock,
        "force_close": total_force_close,
        "win_rate": round(total_win_rate, 2),
    }
