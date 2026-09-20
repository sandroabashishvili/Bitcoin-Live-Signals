"""Grouped metric payload builders for frontend pages."""

from __future__ import annotations

from typing import Any


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_number_item(
    label: str,
    value: Any,
    *,
    kind: str = "generic",
    digits: int = 2,
    explanation_key: str | None = None,
) -> dict[str, str]:
    try:
        text = f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        text = "—"
    item = {"label": label, "value": text, "kind": kind}
    if explanation_key:
        item["explanation_key"] = explanation_key
    return item


def metric_currency_item(
    label: str,
    value: Any,
    *,
    kind: str = "generic",
    digits: int = 2,
    explanation_key: str | None = None,
) -> dict[str, str]:
    try:
        text = f"$ {float(value):.{digits}f}"
    except (TypeError, ValueError):
        text = "—"
    item = {"label": label, "value": text, "kind": kind}
    if explanation_key:
        item["explanation_key"] = explanation_key
    return item


def metric_text_item(
    label: str,
    value: Any,
    *,
    kind: str = "generic",
    explanation_key: str | None = None,
) -> dict[str, str]:
    item = {
        "label": label,
        "value": str(value if value not in (None, "") else "—"),
        "kind": kind,
    }
    if explanation_key:
        item["explanation_key"] = explanation_key
    return item


def metric_percent_item(
    label: str,
    value: Any,
    *,
    kind: str = "pnl",
    explanation_key: str | None = None,
) -> dict[str, str]:
    try:
        text = f"{float(value):.2f}%"
    except (TypeError, ValueError):
        text = "—"
        kind = "generic"
    item = {"label": label, "value": text, "kind": kind}
    if explanation_key:
        item["explanation_key"] = explanation_key
    return item


def metric_kind_from_baseline(value: Any, baseline: Any) -> str:
    try:
        current = float(value)
        reference = float(baseline)
    except (TypeError, ValueError):
        return "generic"
    if current > reference:
        return "tp"
    if current < reference:
        return "sl"
    return "generic"


def build_portfolio_capital_snapshot_items(metrics: dict[str, Any]) -> list[dict[str, str]]:
    starting = metrics.get("starting_capital")
    net_return_pct = as_float(metrics.get("net_return_pct"))
    return [
        metric_currency_item("Starting Capital", metrics.get("starting_capital")),
        metric_currency_item(
            "Equity",
            metrics.get("equity"),
            kind=metric_kind_from_baseline(metrics.get("equity"), starting),
        ),
        metric_currency_item("Available Balance", metrics.get("available_balance")),
        metric_currency_item("Reserved Capital", metrics.get("reserved_capital")),
        metric_currency_item("Unrealized PnL", metrics.get("unrealized_pnl"), kind="pnl"),
        metric_currency_item("Gross PnL", metrics.get("gross_pnl"), kind="pnl"),
        metric_currency_item("Fees Paid", metrics.get("fees_paid"), kind="sl"),
        metric_currency_item("Total Net PnL", metrics.get("total_net_pnl"), kind="pnl"),
        metric_percent_item("Net Return %", net_return_pct, kind="pnl"),
        metric_percent_item("Annualized Return", metrics.get("annualized_return"), kind="pnl"),
        metric_currency_item("Peak Capital", metrics.get("peak_capital"), kind="pnl"),
        metric_currency_item("Lowest Capital", metrics.get("lowest_capital"), kind="sl"),
    ]


def build_portfolio_trade_outcome_items(metrics: dict[str, Any]) -> list[dict[str, str]]:
    return [
        metric_text_item("Strategy Version", metrics.get("active_strategy_version", "—")),
        metric_text_item("Current Version Closed", metrics.get("current_strategy_closed_positions", "—")),
        metric_currency_item("Current Version Net PnL", metrics.get("current_strategy_net_pnl"), kind="pnl"),
        metric_text_item("Total Positions", metrics.get("total_positions", "—")),
        metric_text_item("Open Positions", metrics.get("open_positions", "—")),
        metric_text_item("Closed Positions", metrics.get("closed_positions", "—")),
        metric_text_item("TP Hits", metrics.get("tp_hits", "—"), kind="tp"),
        metric_text_item("SL Hits", metrics.get("sl_hits", "—"), kind="sl"),
        metric_text_item("Profit Lock Hits", metrics.get("profit_lock_hits", 0), kind="tp"),
        metric_percent_item("Win Rate", metrics.get("win_rate"), kind="rate"),
        metric_text_item("Force Close Events", metrics.get("force_close_events", "—")),
        metric_text_item("Skipped Entries", metrics.get("skipped_entries", "—")),
        metric_currency_item("Avg Net / Trade", metrics.get("avg_net_per_trade"), kind="pnl"),
        metric_currency_item("Gross PnL", metrics.get("gross_pnl"), kind="pnl"),
        metric_currency_item("Fees Paid", metrics.get("fees_paid"), kind="sl"),
        metric_currency_item("Best Trade", metrics.get("best_trade"), kind="pnl"),
        metric_currency_item("Worst Trade", metrics.get("worst_trade"), kind="pnl"),
        metric_currency_item("Peak Capital", metrics.get("peak_capital"), kind="pnl"),
        metric_currency_item("Lowest Capital", metrics.get("lowest_capital"), kind="sl"),
    ]


def build_overview_portfolio_snapshot_items(metrics: dict[str, Any]) -> list[dict[str, str]]:
    net_return_pct = as_float(metrics.get("net_return_pct"))
    return [
        metric_currency_item(
            "Equity",
            metrics.get("equity"),
            kind=metric_kind_from_baseline(metrics.get("equity"), metrics.get("starting_capital")),
        ),
        metric_percent_item("Annualized Return", metrics.get("annualized_return"), kind="pnl"),
        metric_percent_item("Net Return %", net_return_pct, kind="pnl"),
        metric_text_item("Open Positions", metrics.get("open_positions", "—")),
        metric_currency_item("Total Net PnL", metrics.get("total_net_pnl"), kind="pnl"),
        metric_currency_item("Unrealized PnL", metrics.get("unrealized_pnl"), kind="pnl"),
    ]


def build_overview_trade_outcomes_snapshot_items(metrics: dict[str, Any]) -> list[dict[str, str]]:
    return [
        metric_text_item("Total Positions", metrics.get("total_positions", "—")),
        metric_text_item("Open Positions", metrics.get("open_positions", "—")),
        metric_text_item("Closed Positions", metrics.get("closed_positions", "—")),
        metric_text_item("TP Hits", metrics.get("tp_hits", "—"), kind="tp"),
        metric_text_item("SL Hits", metrics.get("sl_hits", "—"), kind="sl"),
        metric_text_item("Profit Lock Hits", metrics.get("profit_lock_hits", 0), kind="tp"),
        metric_percent_item("Win Rate", metrics.get("win_rate"), kind="rate"),
        metric_text_item("Force Close", metrics.get("force_close_events", "—"), kind="sl"),
        metric_currency_item("Avg Net / Trade", metrics.get("avg_net_per_trade"), kind="pnl"),
        metric_currency_item("Gross PnL", metrics.get("gross_pnl"), kind="pnl"),
        metric_currency_item("Fees Paid", metrics.get("fees_paid"), kind="sl"),
        metric_currency_item("Best Trade", metrics.get("best_trade"), kind="pnl"),
        metric_currency_item("Worst Trade", metrics.get("worst_trade"), kind="pnl"),
    ]


def build_overview_strategy_snapshot_items(
    *,
    total_signals: int,
    buy_signals: int,
    no_signal: int,
    denied_entries: int,
    trades_opened: Any,
    conversion_rate: Any,
) -> list[dict[str, str]]:
    return [
        metric_text_item("Total Signals", total_signals),
        metric_text_item("BUY Signals", buy_signals, kind="tp"),
        metric_text_item("No Signal", no_signal, kind="neutral"),
        metric_text_item("Denied Entries", denied_entries, kind="sl"),
        metric_text_item("Trades Opened", trades_opened, kind="neutral"),
        metric_percent_item("Conversion Rate", conversion_rate, kind="rate"),
    ]


def build_strategy_page_snapshot_items(
    *,
    total_signals: int,
    buy_signals: int,
    no_signal: int,
    denied_entries: int,
    open_positions: Any,
    closed_positions: Any,
    tp_hits: Any,
    sl_hits: Any,
    force_close_events: Any,
    win_rate: Any,
    total_net_pnl: Any,
    avg_net_per_trade: Any,
) -> list[dict[str, str]]:
    return [
        metric_text_item("Total Signals", total_signals),
        metric_text_item("BUY Signals", buy_signals, kind="tp"),
        metric_text_item("No Signal", no_signal, kind="neutral"),
        metric_text_item("Denied Entries", denied_entries, kind="sl"),
        metric_text_item("Open Positions", open_positions, kind="neutral"),
        metric_text_item("Closed Positions", closed_positions, kind="neutral"),
        metric_text_item("TP Hits", tp_hits, kind="tp"),
        metric_text_item("SL Hits", sl_hits, kind="sl"),
        metric_text_item("Force Close Events", force_close_events, kind="sl"),
        metric_percent_item("Win Rate", win_rate, kind="rate"),
        metric_number_item("Total Net PnL", total_net_pnl, kind="pnl"),
        metric_number_item("Avg Net / Trade", avg_net_per_trade, kind="pnl"),
    ]


def build_strategy_activity_items(metrics: dict[str, Any]) -> list[dict[str, str]]:
    return [
        metric_text_item("Total Signals", metrics.get("total_signals_since_start", "—")),
        metric_text_item("BUY Signals", metrics.get("buy_signals_since_start", "—"), kind="tp"),
        metric_text_item("No Signal", metrics.get("no_signal_since_start", "—"), kind="neutral"),
        metric_text_item("Denied Entries", metrics.get("denied_entries_since_start", "—"), kind="sl"),
        metric_text_item("Trades Opened", metrics.get("trades_opened_since_start", "—"), kind="neutral"),
        metric_percent_item("Conversion Rate", metrics.get("signal_to_trade_conversion"), kind="generic"),
    ]


def build_strategy_activity_evaluation_items(summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        metric_text_item("Total Signals", summary.get("total_signals", "—")),
        metric_text_item("BUY Signals", summary.get("buy_signals", "—"), kind="tp"),
        metric_text_item("No Signal", summary.get("no_signal", "—"), kind="neutral"),
        metric_text_item(
            "Theoretical TP",
            summary.get("theoretical_tp_hits", "—"),
            kind="tp",
            explanation_key="strategy_edge.summary.theoretical_tp",
        ),
        metric_text_item(
            "Theoretical SL",
            summary.get("theoretical_sl_hits", "—"),
            kind="sl",
            explanation_key="strategy_edge.summary.theoretical_sl",
        ),
        metric_text_item(
            "Theoretical Open",
            summary.get("theoretical_open_signals", "—"),
            kind="neutral",
            explanation_key="strategy_edge.summary.theoretical_open",
        ),
        metric_percent_item("Signal Win Rate", summary.get("signal_win_rate"), kind="rate"),
    ]


def build_strategy_outcome_items(metrics: dict[str, Any]) -> list[dict[str, str]]:
    return [
        metric_text_item("Closed Trades", metrics.get("closed_positions", "—"), kind="neutral"),
        metric_text_item("TP Hits", metrics.get("tp_hits", "—"), kind="tp"),
        metric_text_item("SL Hits", metrics.get("sl_hits", "—"), kind="sl"),
        metric_text_item("Profit Lock Hits", metrics.get("profit_lock_hits", 0), kind="tp"),
        metric_text_item("Force Close Events", metrics.get("force_close_events", "—"), kind="sl"),
        metric_percent_item("Win Rate", metrics.get("win_rate"), kind="rate"),
        metric_number_item("Avg Net / Trade", metrics.get("avg_net_per_trade"), kind="pnl"),
    ]


def build_strategy_funnel_items(metrics: dict[str, Any]) -> list[dict[str, str]]:
    return [
        metric_text_item("Total Signals", metrics.get("total_signals_since_start", "—")),
        metric_text_item("BUY Signals", metrics.get("buy_signals_since_start", "—"), kind="tp"),
        metric_text_item("Denied BUY", metrics.get("denied_entries_since_start", "—"), kind="sl"),
        metric_text_item("Trades Opened", metrics.get("trades_opened_since_start", "—"), kind="neutral"),
        metric_text_item("Closed Trades", metrics.get("closed_positions", "—"), kind="neutral"),
    ]
