"""Snapshot-card render helpers for the Overview page."""

from __future__ import annotations

from typing import Any

from platform_v2.spot.dashboard.explanation_system import render_explanation_anchor

from .formatting import escape, fmt_number, strong


def render_trade_outcomes_snapshot(payload: dict[str, Any]) -> str:
    items = payload.get("trade_outcomes_snapshot_items") or []
    parts: list[str] = []
    for item in items:
        label = str(item.get("label", "—"))
        value_html = strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))
        label_html = f"<span>{escape(label)}</span>"
        if label in {"Force Close", "Force Close Events"}:
            label_html = (
                '<span class="metric-label-with-action">'
                f"<span>{escape(label)}</span>"
                f"{render_explanation_anchor(key='overview.trade_outcomes_snapshot.force_close', label_html='')}"
                "</span>"
            )
        parts.append(f'<div class="metric-card">{label_html}{value_html}</div>')
    return "".join(parts)


def render_primary_signal(payload: dict[str, Any]) -> str:
    signal = payload["latest_signal"] or {}
    order = payload["latest_order"] or {}
    position = payload.get("latest_position") or {}
    denied_entry = payload.get("latest_denied_entry") or {}
    setup = signal.get("theoretical_setup") or {}
    signal_side = signal.get("side")

    execution = position.get("execution") or {}
    entry_value = fmt_number(execution.get("entry_price") or setup.get("entry_price")) if signal_side == "BUY" else "—"
    take_profit_value = fmt_number(execution.get("take_profit") or setup.get("take_profit")) if signal_side == "BUY" else "—"
    stop_loss_value = fmt_number(execution.get("stop_loss") or setup.get("stop_loss")) if signal_side == "BUY" else "—"

    entry_status = "No Action"
    if order.get("status") == "FILLED":
        entry_status = "Opened"
    elif denied_entry:
        entry_status = "Denied"
    elif signal.get("side") == "NO_SIGNAL":
        entry_status = "Blocked by Logic"

    cards = (
        ("Signal", strong(signal.get("side", "—"))),
        ("Signal Close", strong(position.get("signal_candle_close_time") or signal.get("candle_close_time") or "—")),
        ("Signal Price", strong(fmt_number(signal.get("snapshot_price")))),
        ("Decision", strong(position.get("decision_time") or signal.get("decision_time") or "—")),
        ("Position Opened", strong(position.get("opened_at") or "—")),
        ("Execution Entry", strong(entry_value)),
        ("TP", strong(take_profit_value, kind="tp")),
        ("SL", strong(stop_loss_value, kind="sl")),
        ("Entry Status", strong(entry_status)),
    )
    parts: list[str] = []
    for label, value_html in cards:
        label_html = f"<span>{escape(label)}</span>"
        card_class = "metric-card"
        if label == "Entry Status":
            label_html = (
                '<span class="metric-label-with-action">'
                f"<span>{escape(label)}</span>"
                f"{render_explanation_anchor(key='overview.primary_signal.entry_status', label_html='')}"
                "</span>"
            )
            card_class = "metric-card metric-card-entry-status"
        parts.append(f'<div class="{card_class}">{label_html}{value_html}</div>')
    return "".join(parts)


def render_strategy_snapshot(payload: dict[str, Any]) -> str:
    items = payload.get("strategy_snapshot_items") or []
    parts: list[str] = []
    for item in items:
        label = str(item.get("label", "—"))
        value_html = strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))
        label_html = f"<span>{escape(label)}</span>"
        parts.append(f'<div class="metric-card">{label_html}{value_html}</div>')
    return "".join(parts)


def render_portfolio_snapshot(payload: dict[str, Any]) -> str:
    items = payload.get("portfolio_snapshot_items") or []
    return "".join(
        f'<div class="metric-card"><span>{escape(item.get("label", "—"))}</span>{strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))}</div>'
        for item in items
    )
