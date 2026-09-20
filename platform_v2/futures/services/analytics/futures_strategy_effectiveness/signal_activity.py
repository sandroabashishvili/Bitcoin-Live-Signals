"""File: signal_activity.py
Folder: platform_v2/futures/services/analytics/futures_strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Signal activity aggregation for Futures strategy effectiveness analytics.
"""

from __future__ import annotations

from typing import Any

from .outcome import load_candle_rows, signal_direction, theoretical_outcome
from .types import SignalActivitySummary


def build_signal_activity_summary(signal_rows: list[dict[str, Any]]) -> SignalActivitySummary:
    buy_rows = [row for row in signal_rows if signal_direction(row) == "LONG"]
    short_rows = [row for row in signal_rows if signal_direction(row) == "SHORT"]
    no_signal_rows = [
        row for row in signal_rows if str(row.get("side") or "").upper() == "NO_SIGNAL"
    ]
    candle_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    theoretical_tp_hits = 0
    theoretical_sl_hits = 0
    theoretical_open_signals = 0

    for row in buy_rows + short_rows:
        symbol = str(row.get("symbol") or "")
        timeframe = str(row.get("timeframe") or "")
        cache_key = (symbol, timeframe)
        if cache_key not in candle_cache:
            candle_cache[cache_key] = load_candle_rows(symbol=symbol, timeframe=timeframe)
        outcome = theoretical_outcome(row=row, candles=candle_cache[cache_key])
        if outcome == "tp":
            theoretical_tp_hits += 1
        elif outcome == "sl":
            theoretical_sl_hits += 1
        else:
            theoretical_open_signals += 1

    resolved = theoretical_tp_hits + theoretical_sl_hits
    signal_win_rate = (theoretical_tp_hits / resolved * 100.0) if resolved else 0.0
    return {
        "total_signals": len(signal_rows),
        "buy_signals": len(buy_rows),
        "short_signals": len(short_rows),
        "no_signal": len(no_signal_rows),
        "theoretical_tp_hits": theoretical_tp_hits,
        "theoretical_sl_hits": theoretical_sl_hits,
        "theoretical_open_signals": theoretical_open_signals,
        "signal_win_rate": round(signal_win_rate, 2),
    }
