"""Reusable JSON persistence primitives for subsystem-owned runtime ledgers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable

from platform_v2.shared.backend.serialization import to_runtime_dict


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_family_rows(folder: Path, *, pattern: str = "*.json") -> list[dict[str, Any]]:
    if not folder.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob(pattern)):
        rows.extend(load_json_list(path))
    return rows


def write_json(path: Path, payload: Any, *, ensure_ascii: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = to_runtime_dict(payload)
    path.write_text(
        json.dumps(serialized, ensure_ascii=ensure_ascii, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def append_json_record(path: Path, record: Any) -> tuple[Path, dict[str, Any]]:
    rows = load_json_list(path)
    runtime_row = _runtime_row(record)
    rows.append(runtime_row)
    return write_json(path, rows), runtime_row


def upsert_json_record(
    path: Path,
    record: Any,
    *,
    match_keys: tuple[str, ...],
) -> tuple[Path, dict[str, Any]]:
    if not match_keys:
        raise ValueError("match_keys must contain at least one key.")
    rows = load_json_list(path)
    runtime_row = _runtime_row(record)
    match_values = tuple(runtime_row.get(key) for key in match_keys)
    if any(value is None for value in match_values):
        missing = ", ".join(
            key for key, value in zip(match_keys, match_values) if value is None
        )
        raise KeyError(f"Runtime row is missing required upsert keys: {missing}")
    for index, existing in enumerate(rows):
        if tuple(existing.get(key) for key in match_keys) == match_values:
            rows[index] = runtime_row
            break
    else:
        rows.append(runtime_row)
    return write_json(path, rows), runtime_row


def replace_family_rows(
    *,
    folder: Path,
    family_name: str,
    rows: list[dict[str, Any]],
    row_date: Callable[[dict[str, Any]], str] | None = None,
    ensure_ascii: bool = False,
) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    for path in folder.glob(f"{family_name}_*.json"):
        path.unlink()
    date_resolver = row_date or resolve_row_date
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(date_resolver(row), []).append(row)
    return [
        write_json(
            folder / f"{family_name}_{date_iso}.json",
            date_rows,
            ensure_ascii=ensure_ascii,
        )
        for date_iso, date_rows in sorted(grouped.items())
    ]


def resolve_row_date(row: dict[str, Any]) -> str:
    for key in ("date", "time_readable"):
        value = row.get(key)
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
    try:
        timestamp_ms = int(row.get("timestamp_ms") or 0)
    except (TypeError, ValueError):
        timestamp_ms = 0
    if timestamp_ms > 0:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).strftime("%Y-%m-%d")
    return datetime.now(tz=UTC).strftime("%Y-%m-%d")


def _runtime_row(record: Any) -> dict[str, Any]:
    runtime_row = to_runtime_dict(record)
    if not isinstance(runtime_row, dict):
        raise TypeError("Runtime record must serialize to a dictionary.")
    return runtime_row
