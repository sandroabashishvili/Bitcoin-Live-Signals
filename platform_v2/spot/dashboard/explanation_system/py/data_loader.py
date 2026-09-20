"""Load explanation content from frontend-owned data files."""

from __future__ import annotations

import json
from pathlib import Path

from platform_v2.shared.frontend.explanation_system import ExplanationItem


_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "explanations.json"


def load_explanation_map() -> dict[str, ExplanationItem]:
    """Return explanation items keyed by stable explanation id."""

    if not _DATA_PATH.exists():
        return {}

    payload: object = None
    try:
        payload = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = None

    if not isinstance(payload, dict):
        return {}

    items: dict[str, ExplanationItem] = {}
    for key, raw in payload.items():
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or key)
        summary = str(raw.get("summary") or "")
        details_raw = raw.get("details") or []
        details = tuple(str(item) for item in details_raw if str(item).strip())
        severity = str(raw.get("severity") or "neutral")
        cta_label = raw.get("cta_label")
        cta_href = raw.get("cta_href")
        secondary_cta_label = raw.get("secondary_cta_label")
        secondary_cta_href = raw.get("secondary_cta_href")
        items[str(key)] = ExplanationItem(
            key=str(key),
            title=title,
            summary=summary,
            details=details,
            severity=severity,
            cta_label=str(cta_label) if cta_label else None,
            cta_href=str(cta_href) if cta_href else None,
            secondary_cta_label=str(secondary_cta_label) if secondary_cta_label else None,
            secondary_cta_href=str(secondary_cta_href) if secondary_cta_href else None,
        )
    return items
