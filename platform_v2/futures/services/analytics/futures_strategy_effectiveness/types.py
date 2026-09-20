"""File: types.py
Folder: platform_v2/futures/services/analytics/futures_strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Typed payloads for Futures strategy effectiveness analytics.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class GateEffectivenessStat(TypedDict):
    participated: int
    tp: int
    sl: int
    open: int
    win_rate: float


class LogicEvaluationRow(TypedDict):
    gate: str
    participated: int
    tp: int
    sl: int
    open: int
    win_rate: float


class LogicEvaluationTotals(TypedDict):
    tp: int
    sl: int
    open: int
    win_rate: float


class LogicEvaluationPayload(TypedDict):
    primary_rows: list[LogicEvaluationRow]
    confirmation_rows: list[LogicEvaluationRow]
    primary_totals: LogicEvaluationTotals
    confirmation_totals: LogicEvaluationTotals
    long_primary_rows: NotRequired[list[LogicEvaluationRow]]
    long_confirmation_rows: NotRequired[list[LogicEvaluationRow]]
    long_primary_totals: NotRequired[LogicEvaluationTotals]
    long_confirmation_totals: NotRequired[LogicEvaluationTotals]
    short_primary_rows: NotRequired[list[LogicEvaluationRow]]
    short_confirmation_rows: NotRequired[list[LogicEvaluationRow]]
    short_primary_totals: NotRequired[LogicEvaluationTotals]
    short_confirmation_totals: NotRequired[LogicEvaluationTotals]


class ClosedTradeLogicEvaluationRow(TypedDict):
    gate: str
    participated: int
    tp: int
    sl: int
    profit_lock: int
    force_close: int
    win_rate: float


class ClosedTradeSummary(TypedDict):
    closed_positions: int
    tp_hits: int
    sl_hits: int
    profit_lock_hits: int
    force_close_events: int
    win_rate: float
    avg_net_per_trade: float


class ClosedTradeLogicEvaluationTotals(TypedDict):
    tp: int
    sl: int
    profit_lock: int
    force_close: int
    win_rate: float
    wins: NotRequired[int]
    participated: NotRequired[int]


class ClosedTradeLogicEvaluationPayload(TypedDict):
    primary_rows: list[ClosedTradeLogicEvaluationRow]
    confirmation_rows: list[ClosedTradeLogicEvaluationRow]
    primary_totals: ClosedTradeLogicEvaluationTotals
    confirmation_totals: ClosedTradeLogicEvaluationTotals
    closed_trade_summary: ClosedTradeSummary
    long_primary_rows: NotRequired[list[ClosedTradeLogicEvaluationRow]]
    long_confirmation_rows: NotRequired[list[ClosedTradeLogicEvaluationRow]]
    long_primary_totals: NotRequired[ClosedTradeLogicEvaluationTotals]
    long_confirmation_totals: NotRequired[ClosedTradeLogicEvaluationTotals]
    short_primary_rows: NotRequired[list[ClosedTradeLogicEvaluationRow]]
    short_confirmation_rows: NotRequired[list[ClosedTradeLogicEvaluationRow]]
    short_primary_totals: NotRequired[ClosedTradeLogicEvaluationTotals]
    short_confirmation_totals: NotRequired[ClosedTradeLogicEvaluationTotals]


class SignalActivitySummary(TypedDict):
    total_signals: int
    buy_signals: int
    short_signals: int
    no_signal: int
    theoretical_tp_hits: int
    theoretical_sl_hits: int
    theoretical_open_signals: int
    signal_win_rate: float
