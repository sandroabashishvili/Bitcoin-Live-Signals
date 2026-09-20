"""Canonical encoding helpers for market-data observations."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def number_or_none(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def event_time_ms(row: dict[str, Any], ordinal: int) -> int:
    for key in ("timestamp_ms", "timestamp", "open_time_ms", "close_time_ms", "close_time"):
        value = row.get(key)
        try:
            if value not in (None, ""):
                parsed = int(value)
                if parsed > 0:
                    return parsed
        except (TypeError, ValueError):
            continue
    for key in ("decision_time", "datetime", "timestamp_text", "date"):
        value = row.get(key)
        if not value:
            continue
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1000)
    return ordinal
