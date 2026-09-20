"""Windowed signal and denied-entry analysis."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re
from typing import Any

from platform_v2.tools.ai_assistant.intents import AssistantIntent
from platform_v2.tools.ai_assistant.runtime_readers import family_rows

from .contracts import CapabilityAnswer


def answer_denied_reason_window(intent: AssistantIntent) -> CapabilityAnswer:
    limit = _extract_limit(intent.question, default=20)
    market = _market(intent)
    family = "futures_denied_entries" if market == "futures" else "denied_entries"
    result = family_rows(market, family)
    rows = _rows(result.row)[-limit:]
    if not rows:
        return CapabilityAnswer("window_analysis", f"No {market.title()} denied-entry rows found. Source: {result.source}")
    counts = Counter(str(row.get("reason") or row.get("permission_reason") or "unknown") for row in rows)
    latest_by_reason: dict[str, dict[str, Any]] = {}
    for row in rows:
        reason = str(row.get("reason") or row.get("permission_reason") or "unknown")
        latest_by_reason[reason] = row
    lines = [
        f"Last {market.title()} denied entries grouped by permission_reason",
        f"Rows checked: {len(rows)}",
        "Counts:",
    ]
    for reason, count in counts.most_common():
        example = latest_by_reason[reason]
        lines.append(f"- {reason}: {count} latest_time={_event_time(example)} side={_value(example.get('signal_side'))}")
    lines.append(f"Source: {result.source}")
    return CapabilityAnswer("window_analysis", "\n".join(lines), (result.source,) if result.source else ())


def answer_signal_permission_window(intent: AssistantIntent) -> CapabilityAnswer:
    limit = _extract_limit(intent.question, default=20)
    market = _market(intent)
    family = "futures_signals" if market == "futures" else "signals"
    result = family_rows(market, family)
    rows = _rows(result.row)[-limit:]
    if not rows:
        return CapabilityAnswer("window_analysis", f"No {market.title()} signal rows found. Source: {result.source}")
    counts = Counter(_signal_status(row) for row in rows)
    reason_counts = Counter(_signal_reason(row) for row in rows)
    lines = [
        f"Last {market.title()} signals by permission status",
        f"Rows checked: {len(rows)}",
        "Permission status counts:",
    ]
    for status, count in counts.most_common():
        lines.append(f"- {status}: {count}")
    lines.append("Permission reason counts:")
    for reason, count in reason_counts.most_common():
        lines.append(f"- {reason}: {count}")
    lines.append(f"Latest row: time={_event_time(rows[-1])}, side={_value(rows[-1].get('side'))}, status={_signal_status(rows[-1])}, reason={_signal_reason(rows[-1])}")
    lines.append(f"Source: {result.source}")
    return CapabilityAnswer("window_analysis", "\n".join(lines), (result.source,) if result.source else ())


def _extract_limit(question: str, default: int) -> int:
    match = re.search(r"\b(\d{1,3})\b", question)
    if not match:
        return default
    return max(1, min(100, int(match.group(1))))


def _market(intent: AssistantIntent) -> str:
    return intent.market if intent.market in {"futures", "spot"} else "futures"


def _signal_status(row: dict[str, Any]) -> str:
    status = row.get("permission_status")
    if status:
        return str(status)
    side = str(row.get("side") or "").upper()
    return "ALLOWED" if side not in {"", "NO_SIGNAL"} else "NO_SIGNAL"


def _signal_reason(row: dict[str, Any]) -> str:
    reason = row.get("permission_reason")
    if reason:
        return str(reason)
    if str(row.get("side") or "").upper() == "NO_SIGNAL":
        failed = _failed_gates(row)
        return "failed_gates:" + ",".join(failed) if failed else "no_signal"
    return "allowed_or_signal"


def _failed_gates(row: dict[str, Any]) -> list[str]:
    raw_gates = row.get("gates")
    gates = raw_gates if isinstance(raw_gates, dict) else {}
    return [key for key, value in gates.items() if value is False]


def _rows(row: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(row, dict):
        return []
    rows = row.get("rows")
    if isinstance(rows, list):
        return [item for item in rows if isinstance(item, dict)]
    return []


def _event_time(row: dict[str, Any]) -> str:
    readable = row.get("decision_time") or row.get("candle_close_time") or row.get("time_readable")
    if readable:
        return str(readable)
    timestamp = row.get("timestamp_ms")
    if timestamp is None:
        return "--"
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        return str(timestamp or "--")
    return datetime.fromtimestamp(timestamp_int / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _value(value: Any) -> str:
    return "--" if value is None else str(value)
