"""Futures hero renderer for dashboard pages."""

from __future__ import annotations

import html
from datetime import datetime

from platform_v2.shared.backend.runtime_store.futures import load_latest_document
from platform_v2.shared.frontend.components import render_content_hero


def _format_strategy_start(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "—":
        return "—"
    for pattern in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.strftime("%Y-%m-%d UTC")
        except ValueError:
            continue
    return text


def _format_elapsed(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "—":
        return "—"
    if "," in text:
        days_part, remainder = text.split(",", 1)
        days_text = days_part.strip()
        time_text = remainder.strip().split(":", 2)
        if len(time_text) >= 2:
            hours_minutes = f"{time_text[0]}:{time_text[1]}"
            if days_text:
                return f"{days_text}, {hours_minutes}"
        return days_text or text
    return text


def _load_latest_runtime_meta() -> tuple[str, str]:
    payload: object = load_latest_document("futures_metrics")
    if not isinstance(payload, dict):
        return "—", "—"

    strategy_start = _format_strategy_start(payload.get("strategy_start"))
    elapsed = _format_elapsed(payload.get("elapsed"))
    return strategy_start, elapsed


def _load_mode_leverage_line() -> str:
    payload: object = load_latest_document("futures_metrics")
    if not isinstance(payload, dict):
        return "Mode: simulation | Futures Market | Leverage: x5"
    mode = str(payload.get("mode") or "simulation")
    leverage = str(payload.get("leverage") or "5")
    return f"Mode: {mode} | Futures Market | Leverage: x{leverage}"


def _render_runtime_meta() -> str:
    strategy_start, elapsed = _load_latest_runtime_meta()
    return f"""
                <div class="hero-runtime-meta" aria-label="Strategy lifecycle">
                  <span class="hero-runtime-meta-item">
                    <span class="hero-runtime-meta-label">Strategy Start</span>
                    <strong class="hero-runtime-meta-value">{html.escape(strategy_start)}</strong>
                  </span>
                  <span class="hero-runtime-meta-item">
                    <span class="hero-runtime-meta-label">Elapsed</span>
                    <strong class="hero-runtime-meta-value">{html.escape(elapsed)}</strong>
                  </span>
                </div>"""


def render_futures_runtime_hero(
    *,
    title: str,
    href: str,
    intro: str,
    subline: str | None = None,
    note: str = "Educational use only. Not financial advice.",
    show_subnav_toggle: bool = True,
) -> str:
    resolved_subline = subline if subline else _load_mode_leverage_line()
    return render_content_hero(
        title=title,
        href=href,
        intro=intro,
        subline=resolved_subline,
        note=note,
        show_runtime=True,
        show_subnav_toggle=show_subnav_toggle,
        runtime_meta_html=_render_runtime_meta(),
    )
