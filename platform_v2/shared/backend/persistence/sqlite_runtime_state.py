"""Small mutable runtime state stored in the trading database."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.time import utc_now_ms

from .sqlite_schema import DEFAULT_DATABASE_PATH, connect, initialize_database


def write_runtime_state(
    *,
    system: str,
    state_key: str,
    payload: dict[str, Any],
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    initialize_database(db_path)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with closing(connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO runtime_state(system, state_key, payload_json, updated_at_ms)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(system, state_key) DO UPDATE SET
                payload_json=excluded.payload_json,
                updated_at_ms=excluded.updated_at_ms
            """,
            (system, state_key, canonical, utc_now_ms()),
        )
        connection.commit()


def read_runtime_state(
    *,
    system: str,
    state_key: str,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> dict[str, Any] | None:
    if not db_path.exists():
        return None
    with closing(connect(db_path)) as connection:
        row = connection.execute(
            "SELECT payload_json FROM runtime_state WHERE system=? AND state_key=?",
            (system, state_key),
        ).fetchone()
    if row is None:
        return None
    payload = json.loads(row[0])
    return payload if isinstance(payload, dict) else None


def delete_runtime_state(
    *,
    system: str,
    state_key: str | None = None,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    if not db_path.exists():
        return
    with closing(connect(db_path)) as connection:
        if state_key is None:
            connection.execute("DELETE FROM runtime_state WHERE system=?", (system,))
        else:
            connection.execute(
                "DELETE FROM runtime_state WHERE system=? AND state_key=?",
                (system, state_key),
            )
        connection.commit()
