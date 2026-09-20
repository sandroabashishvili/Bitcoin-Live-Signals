from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_DIR = Path(__file__).resolve().parent / "state"
SUBSCRIBERS_PATH = STATE_DIR / "subscribers.json"


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _load_payload(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _store_payload(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def list_subscribers(path: Path = SUBSCRIBERS_PATH) -> list[dict[str, Any]]:
    return _load_payload(path)


def list_active_chat_ids(path: Path = SUBSCRIBERS_PATH) -> list[int]:
    active_ids: list[int] = []
    for row in _load_payload(path):
        if row.get("status") != "active":
            continue
        chat_id = row.get("chat_id")
        if isinstance(chat_id, int):
            active_ids.append(chat_id)
    return active_ids


def upsert_subscriber(
    chat_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
    path: Path = SUBSCRIBERS_PATH,
) -> dict[str, Any]:
    rows = _load_payload(path)
    now_iso = _utc_now_iso()
    for row in rows:
        if row.get("chat_id") != chat_id:
            continue
        row["status"] = "active"
        row["updated_at"] = now_iso
        if username is not None:
            row["username"] = username
        if first_name is not None:
            row["first_name"] = first_name
        _store_payload(path, rows)
        return row
    row = {
        "chat_id": chat_id,
        "username": username,
        "first_name": first_name,
        "status": "active",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    rows.append(row)
    _store_payload(path, rows)
    return row


def deactivate_subscriber(chat_id: int, path: Path = SUBSCRIBERS_PATH) -> bool:
    rows = _load_payload(path)
    changed = False
    now_iso = _utc_now_iso()
    for row in rows:
        if row.get("chat_id") != chat_id:
            continue
        if row.get("status") != "inactive":
            row["status"] = "inactive"
            row["updated_at"] = now_iso
            changed = True
    if changed:
        _store_payload(path, rows)
    return changed
