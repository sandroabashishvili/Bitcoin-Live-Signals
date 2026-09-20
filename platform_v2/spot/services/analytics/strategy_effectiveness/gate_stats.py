"""File: gate_stats.py
Folder: platform_v2/spot/services/analytics/strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Gate effectiveness aggregation for Spot strategy analytics.
"""

from __future__ import annotations

from typing import Any

from .outcome import (
    build_signal_lookup,
    closed_trade_outcome_key,
    load_candle_rows,
    net_pnl_value,
    signal_lookup_key,
    theoretical_outcome,
)
from .types import (
    ClosedTradeLogicEvaluationRow,
    ClosedTradeLogicEvaluationTotals,
    GateEffectivenessStat,
    LogicEvaluationRow,
    LogicEvaluationTotals,
)


TheoreticalOutcome = str


def gate_effectiveness(
    signal_rows: list[dict[str, Any]],
    *,
    gate_names: tuple[str, ...],
) -> dict[str, GateEffectivenessStat]:
    stats: dict[str, GateEffectivenessStat] = {
        gate_name: {"participated": 0, "tp": 0, "sl": 0, "open": 0, "win_rate": 0.0}
        for gate_name in gate_names
    }
    buy_rows = [row for row in signal_rows if str(row.get("side") or "").upper() == "BUY"]
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
        outcome: TheoreticalOutcome = theoretical_outcome(row=row, candles=candle_cache[cache_key])
        gates = row.get("gates") or {}
        for gate_name in gate_names:
            if not gates.get(gate_name):
                continue
            gate_stat = stats[gate_name]
            gate_stat["participated"] += 1
            if outcome == "tp":
                gate_stat["tp"] += 1
            elif outcome == "sl":
                gate_stat["sl"] += 1
            else:
                gate_stat["open"] += 1

    for gate_stat in stats.values():
        resolved = gate_stat["tp"] + gate_stat["sl"]
        gate_stat["win_rate"] = (gate_stat["tp"] / resolved * 100.0) if resolved else 0.0
    return stats


def closed_trade_gate_effectiveness(
    *,
    signal_rows: list[dict[str, Any]],
    closed_positions: list[Any],
    gate_names: tuple[str, ...],
) -> dict[str, dict[str, float | int]]:
    stats: dict[str, dict[str, float | int]] = {
        gate_name: {
            "participated": 0,
            "tp": 0,
            "sl": 0,
            "force_close": 0,
            "lock": 0,
            "wins": 0,
            "win_rate": 0.0,
        }
        for gate_name in gate_names
    }
    signal_lookup = build_signal_lookup(signal_rows)
    # Old positions did not persist their source candle. Preserve their former
    # bucket-based attribution only for those records, never for new positions.
    windows = {"5m": 300000, "15m": 900000, "1h": 3600000,
               "4h": 14400000, "1d": 86400000}
    legacy_lookup = {
        (symbol, timeframe, stamp // windows.get(timeframe, 1)): row
        for (symbol, timeframe, stamp), row in signal_lookup.items()
    }

    for position in closed_positions:
        key = signal_lookup_key(position)
        signal_row = signal_lookup.get(key)
        if signal_row is None and not getattr(position, "signal_candle_close_time", None):
            symbol, timeframe, stamp = key
            signal_row = legacy_lookup.get((symbol, timeframe, stamp // windows.get(timeframe, 1)))
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
            gate_stat = stats[gate_name]
            gate_stat["participated"] = int(gate_stat["participated"]) + 1
            if outcome_key == "tp":
                gate_stat["tp"] = int(gate_stat["tp"]) + 1
            elif outcome_key == "lock":
                gate_stat["lock"] = int(gate_stat["lock"]) + 1
            elif outcome_key == "force_close":
                gate_stat["force_close"] = int(gate_stat["force_close"]) + 1
            else:
                gate_stat["sl"] = int(gate_stat["sl"]) + 1
            if is_win:
                gate_stat["wins"] = int(gate_stat["wins"]) + 1

    for gate_stat in stats.values():
        participated = int(gate_stat["participated"])
        wins = int(gate_stat["wins"])
        gate_stat["win_rate"] = (wins / participated * 100.0) if participated else 0.0
    return stats


def build_group_rows(
    gate_names: tuple[str, ...],
    gate_stats: dict[str, GateEffectivenessStat],
) -> tuple[list[LogicEvaluationRow], LogicEvaluationTotals]:
    rows: list[LogicEvaluationRow] = []
    total_tp = 0
    total_sl = 0
    total_open = 0

    for gate_name in gate_names:
        stats = gate_stats.get(
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
        rows.append(
            {
                "gate": gate_name.upper(),
                "participated": participated,
                "tp": tp,
                "sl": sl,
                "open": open_count,
                "win_rate": round(float(stats["win_rate"]), 2),
            }
        )

    return rows, {"tp": total_tp, "sl": total_sl, "open": total_open}


def build_closed_trade_group_rows(
    gate_names: tuple[str, ...],
    gate_stats: dict[str, dict[str, float | int]],
) -> tuple[list[ClosedTradeLogicEvaluationRow], ClosedTradeLogicEvaluationTotals]:
    rows: list[ClosedTradeLogicEvaluationRow] = []
    total_participated = 0
    total_tp = 0
    total_sl = 0
    total_force_close = 0
    total_lock = 0
    total_wins = 0
    win_rate_values: list[float] = []

    for gate_name in gate_names:
        stats = gate_stats.get(
            gate_name,
            {
                "participated": 0,
                "tp": 0,
                "sl": 0,
                "force_close": 0,
                "lock": 0,
                "wins": 0,
                "win_rate": 0.0,
            },
        )
        participated = int(stats["participated"])
        tp = int(stats["tp"])
        sl = int(stats["sl"])
        force_close = int(stats["force_close"])
        lock = int(stats.get("lock", 0))
        total_lock += lock
        wins = int(stats["wins"])
        total_participated += participated
        total_tp += tp
        total_sl += sl
        total_force_close += force_close
        total_wins += wins
        if participated:
            win_rate_values.append(float(stats["win_rate"]))
        rows.append(
            {
                "gate": gate_name.upper(),
                "participated": participated,
                "tp": tp,
                "sl": sl,
                "force_close": force_close,
                "lock": lock,
                "win_rate": round(float(stats["win_rate"]), 2),
            }
        )

    total_win_rate = sum(win_rate_values) / len(win_rate_values) if win_rate_values else 0.0
    return rows, {
        "tp": total_tp,
        "sl": total_sl,
        "force_close": total_force_close,
        "lock": total_lock,
        "wins": total_wins,
        "participated": total_participated,
        "win_rate": round(total_win_rate, 2),
    }
