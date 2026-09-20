"""Identity, canonical encoding, and query indexes for runtime rows."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


_DAILY_FILE_RE = re.compile(r"^(?P<family>.+)_(?P<date>\d{4}-\d{2}-\d{2})\.json$")


def daily_identity(path: Path) -> tuple[str, str] | None:
    match = _DAILY_FILE_RE.match(path.name)
    if match is None or path.parent.name != match.group("family"):
        return None
    return match.group("family"), match.group("date")


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def indexed_row(
    *,
    system: str,
    family: str,
    date_iso: str,
    ordinal: int,
    row: dict[str, Any],
) -> tuple[Any, ...]:
    return (
        system,
        family,
        date_iso,
        ordinal,
        _as_int(row.get("timestamp_ms")),
        _entity_id(row),
        _as_text(row.get("symbol")),
        _as_text(row.get("side") or row.get("position_side") or row.get("signal_side")),
        _as_text(row.get("status") or row.get("event") or row.get("state")),
        _as_float(row.get("net_pnl") or row.get("realized_net_pnl")),
        canonical_json(row),
    )


def row_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    return 1 if payload is not None else 0


def _entity_id(row: dict[str, Any]) -> str | None:
    for key in ("position_id", "order_id", "signal_id", "client_order_id", "id"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _as_text(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
