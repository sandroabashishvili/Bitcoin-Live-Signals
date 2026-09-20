"""Load Futures Hedge explanation content."""

from __future__ import annotations

import json
from pathlib import Path

from platform_v2.shared.frontend.explanation_system import ExplanationItem


_DATA_PATH = Path(__file__).resolve().parent / "data" / "explanations.json"


def load_explanation_map() -> dict[str, ExplanationItem]:
    """Return Hedge explanation items keyed by stable explanation id."""

    if not _DATA_PATH.exists():
        return {}

    try:
        payload: object = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    if not isinstance(payload, dict):
        return {}

    items: dict[str, ExplanationItem] = {}
    for key, raw in payload.items():
        if not isinstance(raw, dict):
            continue
        details_raw = raw.get("details") or []
        items[str(key)] = ExplanationItem(
            key=str(key),
            title=str(raw.get("title") or key),
            summary=str(raw.get("summary") or ""),
            details=tuple(str(item) for item in details_raw if str(item).strip()),
            severity=str(raw.get("severity") or "neutral"),
            cta_label=str(raw["cta_label"]) if raw.get("cta_label") else None,
            cta_href=str(raw["cta_href"]) if raw.get("cta_href") else None,
            secondary_cta_label=str(raw["secondary_cta_label"]) if raw.get("secondary_cta_label") else None,
            secondary_cta_href=str(raw["secondary_cta_href"]) if raw.get("secondary_cta_href") else None,
        )
    return items
