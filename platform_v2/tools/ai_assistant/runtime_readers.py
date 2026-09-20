"""Deterministic runtime readers for the SmartSignalHub assistant."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import load_family_rows_all as load_futures_rows_all
from platform_v2.shared.backend.runtime_store.futures import load_latest_document as load_latest_futures_document
from platform_v2.shared.backend.runtime_store.spot import load_family_rows_all as load_spot_rows_all
from platform_v2.shared.backend.runtime_store.spot import load_latest_document as load_latest_spot_document


REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_ROOT = REPO_ROOT / "platform_v2"


@dataclass(frozen=True)
class RuntimeResult:
    market: str
    family: str
    row: dict[str, Any] | None
    source: str | None
    count: int


def latest_signal(market: str) -> RuntimeResult:
    family = "futures_signals" if market == "futures" else "signals"
    return _latest_family_row(market, family)


def signal_history(market: str) -> RuntimeResult:
    family = "futures_signals" if market == "futures" else "signals"
    rows = sorted(_load_rows(market, family), key=_row_sort_key)
    if not rows:
        return RuntimeResult(market, family, None, _family_dir(market, family), 0)
    return RuntimeResult(
        market,
        family,
        {"first": rows[0], "latest": rows[-1]},
        _family_dir(market, family),
        len(rows),
    )


def latest_position(market: str) -> RuntimeResult:
    family = "futures_positions" if market == "futures" else "positions"
    return _latest_family_row(market, family)


def latest_denied_entry(market: str) -> RuntimeResult:
    family = "futures_denied_entries" if market == "futures" else "denied_entries"
    return _latest_family_row(market, family)


def latest_metrics(market: str) -> RuntimeResult:
    family = "futures_metrics" if market == "futures" else "metrics"
    return _latest_family_row(market, family)


def latest_daily_summary(market: str) -> RuntimeResult:
    family = "futures_daily_summaries" if market == "futures" else "daily_summaries"
    return _latest_family_row(market, family)


def family_rows(market: str, family: str) -> RuntimeResult:
    rows = sorted(_load_rows(market, family), key=_row_sort_key)
    if not rows:
        return RuntimeResult(market, family, None, _family_dir(market, family), 0)
    return RuntimeResult(
        market=market,
        family=family,
        row={"rows": rows},
        source=_family_dir(market, family),
        count=len(rows),
    )


def latest_family_row(market: str, family: str) -> RuntimeResult:
    return _latest_family_row(market, family)


def latest_diagnostics_report(profile: str | None = None) -> RuntimeResult:
    candidates = [
        PLATFORM_ROOT / "runtime" / "artifacts" / "diagnostics",
        PLATFORM_ROOT / "runtime" / "spot" / "artifacts" / "diagnostics",
    ]
    paths: list[Path] = []
    for folder in candidates:
        if folder.exists():
            paths.extend(sorted(folder.glob("*.json")))
    if profile:
        profile_text = profile.strip().casefold()
        if profile_text == "operational":
            paths = [path for path in paths if "_full_" not in path.name]
        elif profile_text == "full":
            paths = [path for path in paths if "_full_" in path.name]

    if not paths:
        return RuntimeResult("system", "diagnostics", None, None, 0)

    latest_path = max(paths, key=lambda path: path.stat().st_mtime)
    try:
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    row = payload if isinstance(payload, dict) else {"payload_type": type(payload).__name__}
    return RuntimeResult("system", "diagnostics", row, str(latest_path), len(paths))


def _latest_family_row(market: str, family: str) -> RuntimeResult:
    rows = _load_rows(market, family)
    if not rows:
        return RuntimeResult(market, family, None, _family_dir(market, family), 0)

    latest = max(rows, key=_row_sort_key)
    return RuntimeResult(market, family, latest, _family_dir(market, family), len(rows))


def _load_rows(market: str, family: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]]
    if market == "futures":
        rows = load_futures_rows_all(family)
    elif market == "spot":
        rows = load_spot_rows_all(family)
    else:
        rows = []
    if rows:
        return rows
    latest = (
        load_latest_futures_document(family)
        if market == "futures"
        else load_latest_spot_document(family) if market == "spot" else None
    )
    if isinstance(latest, dict):
        return [latest]
    if isinstance(latest, list):
        return [row for row in latest if isinstance(row, dict)]
    return _load_family_snapshots(Path(_family_dir(market, family)))


def _load_family_snapshots(folder: Path) -> list[dict[str, Any]]:
    if not folder.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        elif isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def _family_dir(market: str, family: str) -> str:
    if market == "futures":
        return str(PLATFORM_ROOT / "runtime" / "futures" / "data" / family)
    return str(PLATFORM_ROOT / "runtime" / "spot" / "data" / family)


def _row_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    timestamp = row.get("timestamp_ms") or row.get("opened_at_ms") or row.get("closed_at") or 0
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        timestamp_int = 0
    if timestamp_int <= 0:
        timestamp_int = _parse_time_to_ms(row.get("datetime") or row.get("date"))
    readable = str(row.get("decision_time") or row.get("time_readable") or row.get("opened_at") or "")
    return timestamp_int, readable


def _parse_time_to_ms(value: Any) -> int:
    if not value:
        return 0
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)
