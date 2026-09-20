"""HTML helpers for dashboard explanation triggers and payloads."""

from __future__ import annotations

import html
import json

from .models import ExplanationItem, ExplanationPresentation


def render_explanation_anchor(
    *,
    key: str,
    label_html: str,
    presentation: ExplanationPresentation | None = None,
) -> str:
    """Render a lightweight trigger element for one explanation target."""

    resolved = presentation or ExplanationPresentation()
    attrs = {
        "class": f"explanation-anchor explanation-anchor-{resolved.css_variant}",
        "data-expl-key": key,
        "data-expl-mode": resolved.mode,
        "data-expl-trigger": resolved.trigger,
    }
    attrs.update(resolved.attrs)
    attr_html = " ".join(f'{name}="{html.escape(value, quote=True)}"' for name, value in attrs.items())
    return f"<span {attr_html}>{label_html}</span>"


def render_explanation_payload(items: dict[str, ExplanationItem]) -> str:
    """Serialize explanation items for frontend bootstrapping."""

    payload = {
        key: {
            "title": item.title,
            "summary": item.summary,
            "details": list(item.details),
            "severity": item.severity,
            "cta_label": item.cta_label,
            "cta_href": item.cta_href,
            "secondary_cta_label": item.secondary_cta_label,
            "secondary_cta_href": item.secondary_cta_href,
        }
        for key, item in items.items()
    }
    safe_json = json.dumps(payload, ensure_ascii=True).replace("</", "<\\/")
    return f"<script>window.__SSH_EXPLANATIONS__ = {safe_json};</script>"
