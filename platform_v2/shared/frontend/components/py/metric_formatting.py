"""Shared value-formatting helpers for frontend metric coloring."""

from __future__ import annotations

import html
from typing import Any


def escape(value: Any) -> str:
    return html.escape(str(value))


def value_class(value: Any, *, kind: str = "generic") -> str:
    text = str(value or "").upper()
    kind = str(kind or "generic").lower()

    if kind == "pnl" or kind == "delta":
        try:
            number = float(str(value).replace("$", "").replace("%", "").replace(",", ""))
        except (TypeError, ValueError):
            return "value-muted"
        if number > 0:
            return "value-green"
        if number < 0:
            return "value-red"
        return "value-muted"

    if kind == "rate":
        try:
            number = float(str(value).replace("%", ""))
        except (TypeError, ValueError):
            return "value-muted"
        if number >= 60.0:
            return "value-green"
        if number <= 40.0:
            return "value-red"
        return "value-amber"

    if kind in {"tp", "pass", "buy", "positive"}:
        return "value-green"
    if kind in {"sl", "fail", "sell", "negative"}:
        return "value-red"
    if kind in {"neutral", "amber"}:
        return "value-amber"

    if text in {"BUY", "LONG", "OPEN", "FILLED", "PASS", "TP_HIT", "TP", "PROFIT_LOCK_HIT"}:
        return "value-green"
    if text in {"SELL", "SHORT", "SL_HIT", "SL", "DENIED", "FAIL", "REJECTED", "ERROR"}:
        return "value-red"
    if text in {"NO_SIGNAL", "NO SIGNAL"}:
        return "value-muted"
    if text in {"FORCE_CLOSE", "FORCE_CLOSED", "CLOSED", "WATCH"}:
        return "value-amber"
    return ""


def strong(value: Any, *, kind: str = "generic") -> str:
    klass = value_class(value, kind=kind)
    safe = escape(value if value not in (None, "") else "—")
    if klass:
        return f'<strong class="{klass}">{safe}</strong>'
    return f"<strong>{safe}</strong>"
