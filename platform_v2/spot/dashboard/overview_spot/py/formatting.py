"""Formatting helpers for the Overview page renderer."""

from __future__ import annotations

import html
from typing import Any

from platform_v2.shared.frontend.components import metric_value_class

def escape(value: Any) -> str:
    return html.escape(str(value))


def fmt_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def value_class(value: Any, *, kind: str = "generic") -> str:
    return metric_value_class(value, kind=kind)


def strong(value: Any, *, kind: str = "generic") -> str:
    klass = value_class(value, kind=kind)
    safe = escape(value if value not in (None, "") else "—")
    if klass:
        return f'<strong class="{klass}">{safe}</strong>'
    return f"<strong>{safe}</strong>"


def baseline_strong(value: Any, baseline: Any) -> str:
    try:
        current = float(value)
        reference = float(baseline)
    except (TypeError, ValueError):
        return strong(fmt_number(value))
    if current > reference:
        kind = "tp"
    elif current < reference:
        kind = "sl"
    else:
        kind = "generic"
    return strong(fmt_number(current), kind=kind)
