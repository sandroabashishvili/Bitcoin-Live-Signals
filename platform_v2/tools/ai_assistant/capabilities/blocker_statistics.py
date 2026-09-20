"""Blocker statistics over recent runtime windows."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from platform_v2.tools.ai_assistant.intents import AssistantIntent
from platform_v2.tools.ai_assistant.runtime_readers import family_rows

from .contracts import CapabilityAnswer


def answer_blocker_statistics(intent: AssistantIntent | str | None = None) -> CapabilityAnswer:
    question = intent.question if isinstance(intent, AssistantIntent) else str(intent or "")
    market = intent.market if isinstance(intent, AssistantIntent) and intent.market in {"futures", "spot"} else "futures"
    days = _extract_days(question, default=7)
    if market == "spot":
        return _answer_spot_signal_blockers(days)
    result = family_rows("futures", "futures_denied_entries")
    rows = _rows(result)
    cutoff_ms = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    window = [row for row in rows if _timestamp(row) >= cutoff_ms]
    if not window:
        window = rows[-100:]
    reason_counts = Counter(str(row.get("reason") or row.get("permission_reason") or "unknown") for row in window)
    check_counts: Counter[str] = Counter()
    for row in window:
        raw_checks = row.get("checks")
        checks = raw_checks if isinstance(raw_checks, dict) else {}
        check_counts.update(key for key, value in checks.items() if value is False)
    total = len(window)
    lines = [
        f"Futures blocker statistics ({days}-day window)",
        f"Rows checked: {total}",
        "Top permission reasons:",
    ]
    for reason, count in reason_counts.most_common():
        lines.append(f"- {reason}: {count} ({_pct(count, total)}%)")
    lines.append("Top failed checks:")
    for check, count in check_counts.most_common():
        lines.append(f"- {check}: {count} ({_pct(count, total)}%)")
    lines.append(f"Source: {result.source}")
    return CapabilityAnswer("blocker_statistics", "\n".join(lines), (result.source,) if result.source else ())


def _answer_spot_signal_blockers(days: int) -> CapabilityAnswer:
    result = family_rows("spot", "signals")
    rows = _rows(result)
    cutoff_ms = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    window = [row for row in rows if _timestamp(row) >= cutoff_ms]
    if not window:
        window = rows[-100:]
    gate_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    side_counts = Counter(str(row.get("side") or "UNKNOWN") for row in window)
    for row in window:
        raw_gates = row.get("gates")
        gates = raw_gates if isinstance(raw_gates, dict) else {}
        gate_counts.update(key for key, value in gates.items() if value is False)
        raw_reasons = row.get("reasons")
        reasons = raw_reasons if isinstance(raw_reasons, list) else []
        for reason in reasons:
            text = str(reason)
            if "gate failed" in text or "cannot become actionable" in text or "requires primary timeframe" in text:
                reason_counts[text] += 1
    total = len(window)
    lines = [
        f"Spot blocker statistics ({days}-day signal window)",
        f"Rows checked: {total}",
        "Signal side counts:",
    ]
    for side, count in side_counts.most_common():
        lines.append(f"- {side}: {count} ({_pct(count, total)}%)")
    lines.append("Top failed gates:")
    for gate, count in gate_counts.most_common():
        lines.append(f"- {gate}: {count} ({_pct(count, total)}%)")
    lines.append("Top reason lines:")
    for reason, count in reason_counts.most_common(8):
        lines.append(f"- {reason}: {count}")
    lines.append("Note: Spot has signals/metrics ledgers but no separate denied_entries ledger in current runtime data.")
    lines.append(f"Source: {result.source}")
    return CapabilityAnswer("blocker_statistics", "\n".join(lines), (result.source,) if result.source else ())


def _extract_days(question: str, default: int) -> int:
    text = question.casefold()
    if "today" in text or "დღეს" in text:
        return 1
    match = re.search(r"(\d{1,2})\s*(day|days|დღ)", text)
    if match:
        return max(1, min(30, int(match.group(1))))
    if "7" in text or "week" in text:
        return 7
    return default


def _rows(result: Any) -> list[dict[str, Any]]:
    row_payload = result.row
    if isinstance(row_payload, dict):
        rows = row_payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _timestamp(row: dict[str, Any]) -> int:
    try:
        return int(row.get("timestamp_ms") or 0)
    except (TypeError, ValueError):
        return 0


def _pct(count: int, total: int) -> float:
    return round(count / total * 100.0, 2) if total else 0.0
