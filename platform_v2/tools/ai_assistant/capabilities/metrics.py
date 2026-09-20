"""Metrics capability for PnL, win/loss, and system performance."""

from __future__ import annotations

from typing import Any

from platform_v2.tools.ai_assistant.runtime_readers import latest_metrics

from .contracts import CapabilityAnswer


def answer_metrics(market: str | None = None) -> CapabilityAnswer:
    markets = [market] if market in ("futures", "spot") else ["futures", "spot"]
    sections = [_format_metrics(selected_market) for selected_market in markets]
    return CapabilityAnswer("metrics", "\n\n".join(sections))


def answer_why_winning_or_losing(market: str | None = None) -> CapabilityAnswer:
    markets = [market] if market in ("futures", "spot") else ["futures", "spot"]
    sections = []
    for selected_market in markets:
        result = latest_metrics(selected_market)
        row = result.row
        if row is None:
            sections.append(f"{selected_market.title()} metrics: no rows found. Source: {result.source}")
            continue
        net_pnl = _float(row.get("total_net_pnl"))
        fees = _float(row.get("fees_paid") or row.get("total_fees_paid"))
        unrealized = _float(row.get("unrealized_pnl"))
        win_rate = _value(row.get("win_rate"))
        long_net = row.get("long_net_pnl")
        short_net = row.get("short_net_pnl")
        if net_pnl > 0:
            verdict = "currently winning"
        elif net_pnl < 0:
            verdict = "currently losing"
        else:
            verdict = "flat"
        lines = [
            f"{selected_market.title()} is {verdict}.",
            f"Total net PnL: {_value(row.get('total_net_pnl'))}",
            f"Unrealized PnL: {_value(unrealized)}",
            f"Fees paid: {_value(fees)}",
            f"Win rate: {win_rate}",
            f"Trades opened: {_value(row.get('trades_opened_since_start') or row.get('total_positions'))}",
            f"Signal conversion: {_value(row.get('signal_to_trade_conversion'))}",
        ]
        if long_net is not None or short_net is not None:
            lines.append(f"Direction attribution: LONG={_value(long_net)}, SHORT={_value(short_net)}")
        if fees > abs(net_pnl) and net_pnl <= 0:
            lines.append("Main pressure: fees are larger than or close to net result.")
        if unrealized < 0:
            lines.append("Open-position pressure: current unrealized PnL is negative.")
        denied = _float(row.get("denied_entries_since_start") or row.get("today_denied_entries"))
        opened = _float(row.get("trades_opened_since_start") or row.get("total_positions"))
        if denied > opened and opened > 0:
            lines.append("Execution pressure: many signals are denied before becoming trades.")
        if _float(long_net) < 0 and _float(short_net) > 0:
            lines.append("Attribution: SHORT is carrying gains while LONG is negative.")
        elif _float(short_net) < 0 and _float(long_net) > 0:
            lines.append("Attribution: LONG is carrying gains while SHORT is negative.")
        lines.append(f"Source: {result.source}")
        sections.append("\n".join(lines))
    return CapabilityAnswer("metrics", "\n\n".join(sections))


def _format_metrics(market: str) -> str:
    result = latest_metrics(market)
    row = result.row
    if row is None:
        return f"{market.title()} metrics: no rows found. Source: {result.source}"
    lines = [
        f"{market.title()} latest metrics",
        f"Time: {_value(row.get('datetime') or row.get('date'))}",
        f"Equity: {_value(row.get('equity'))}",
        f"Total net PnL: {_value(row.get('total_net_pnl'))}",
        f"Gross PnL: {_value(row.get('gross_pnl') or row.get('total_gross_pnl'))}",
        f"Fees paid: {_value(row.get('fees_paid') or row.get('total_fees_paid'))}",
        f"Unrealized PnL: {_value(row.get('unrealized_pnl'))}",
        f"Win rate: {_value(row.get('win_rate'))}",
        f"Open positions: {_value(row.get('open_positions'))}",
        f"Closed positions: {_value(row.get('closed_positions'))}",
        f"Today signals: {_value(row.get('today_total_signals'))}",
        f"Today denied entries: {_value(row.get('today_denied_entries'))}",
        f"Source: {result.source}",
    ]
    return "\n".join(lines)


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _value(value: Any) -> str:
    if value is None:
        return "--"
    return str(value)
