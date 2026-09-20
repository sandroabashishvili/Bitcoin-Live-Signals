"""Audit log storage for assistant-confirmed actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from platform_v2.tools.ai_assistant.runtime_readers import PLATFORM_ROOT

from .action_catalog import AssistantAction


ACTION_AUDIT_DIR = PLATFORM_ROOT / "runtime" / "artifacts" / "ai_assistant"


def current_audit_log_path() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return ACTION_AUDIT_DIR / f"action_audit_{today}.jsonl"


def build_audit_record(*, action: AssistantAction, status: str, question: str, note: str = "") -> dict[str, object]:
    return {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action_key": action.key,
        "title": action.title,
        "command": list(action.command),
        "risk": action.risk,
        "confirmation": action.confirmation,
        "assistant_scope": action.assistant_scope,
        "status": status,
        "question": question,
        "note": note,
        "writes_to": [str(path) for path in action.writes_to],
    }


def write_action_audit_record(record: dict[str, object]) -> Path:
    ACTION_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = current_audit_log_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def find_latest_pending_action(action_id: str) -> dict[str, object] | None:
    matching = [row for row in read_action_audit_rows() if row.get("action_id") == action_id]
    if any(row.get("status") in {"started", "completed", "failed", "timeout", "canceled"} for row in matching):
        return None
    for row in reversed(matching):
        if row.get("status") == "pending":
            return row
    return None


def pending_actions() -> list[dict[str, object]]:
    by_id: dict[str, list[dict[str, object]]] = {}
    for row in read_action_audit_rows():
        action_id = row.get("action_id")
        if isinstance(action_id, str) and action_id:
            by_id.setdefault(action_id, []).append(row)

    closed_statuses = {"started", "completed", "failed", "timeout", "canceled"}
    pending: list[dict[str, object]] = []
    for rows_for_id in by_id.values():
        if any(row.get("status") in closed_statuses for row in rows_for_id):
            continue
        latest = rows_for_id[-1]
        if latest.get("status") == "pending":
            pending.append(latest)
    return pending


def latest_action_rows(limit: int = 20) -> list[dict[str, object]]:
    rows = read_action_audit_rows()
    if limit <= 0:
        return rows
    return rows[-limit:]


def read_action_audit_rows() -> list[dict[str, object]]:
    if not ACTION_AUDIT_DIR.exists():
        return []
    rows: list[dict[str, object]] = []
    for path in sorted(ACTION_AUDIT_DIR.glob("action_audit_*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows
