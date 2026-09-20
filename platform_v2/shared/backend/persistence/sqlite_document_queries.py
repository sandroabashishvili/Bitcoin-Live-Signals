"""Runtime-document reads, parity, export, and lifecycle queries."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
from typing import Any

from .runtime_document_codec import canonical_json, row_count
from .sqlite_schema import DEFAULT_DATABASE_PATH, connect, initialize_database


def read_document(
    *, system: str, family: str, date_iso: str, db_path: Path = DEFAULT_DATABASE_PATH
) -> list[Any] | dict[str, Any] | None:
    if not db_path.exists():
        return None
    with closing(connect(db_path)) as connection:
        document = connection.execute(
            "SELECT payload_type FROM runtime_documents WHERE system=? AND family=? AND date_iso=?",
            (system, family, date_iso),
        ).fetchone()
        rows = connection.execute(
            """
            SELECT payload_json FROM runtime_rows
            WHERE system=? AND family=? AND date_iso=? ORDER BY ordinal
            """,
            (system, family, date_iso),
        ).fetchall()
    if document is None:
        return None
    payload = [json.loads(row[0]) for row in rows]
    return (payload[0] if payload else {}) if document[0] == "object" else payload


def read_latest_document(
    *, system: str, family: str, db_path: Path = DEFAULT_DATABASE_PATH
) -> tuple[str, list[Any] | dict[str, Any]] | None:
    if not db_path.exists():
        return None
    with closing(connect(db_path)) as connection:
        row = connection.execute(
            """
            SELECT date_iso FROM runtime_documents
            WHERE system=? AND family=? ORDER BY date_iso DESC LIMIT 1
            """,
            (system, family),
        ).fetchone()
    if row is None:
        return None
    date_iso = str(row[0])
    payload = read_document(system=system, family=family, date_iso=date_iso, db_path=db_path)
    return (date_iso, payload) if payload is not None else None


def list_documents(*, db_path: Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with closing(connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT system, family, date_iso, payload_type, row_count,
                   payload_sha256, source_path, updated_at_ms
            FROM runtime_documents ORDER BY system, family, date_iso
            """
        ).fetchall()
    keys = (
        "system", "family", "date_iso", "payload_type", "row_count",
        "payload_sha256", "source_path", "updated_at_ms",
    )
    return [dict(zip(keys, row)) for row in rows]


def export_document_to_json(
    *, system: str, family: str, date_iso: str, target_path: Path,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> Path:
    payload = read_document(system=system, family=family, date_iso=date_iso, db_path=db_path)
    if payload is None:
        raise KeyError(f"SQLite document not found: {system}/{family}/{date_iso}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target_path


def parity_for_document(
    *, system: str, family: str, date_iso: str, json_path: Path,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> dict[str, Any]:
    json_payload = json.loads(json_path.read_text(encoding="utf-8"))
    sqlite_payload = read_document(system=system, family=family, date_iso=date_iso, db_path=db_path)
    matches = sqlite_payload is not None and canonical_json(json_payload) == canonical_json(sqlite_payload)
    return {
        "system": system,
        "family": family,
        "date_iso": date_iso,
        "json_path": str(json_path),
        "json_rows": row_count(json_payload),
        "sqlite_rows": row_count(sqlite_payload),
        "hash_match": matches,
        "status": "match" if matches else "mismatch",
    }


def remove_family_documents_except(
    *, system: str, family: str, keep_dates: set[str], db_path: Path = DEFAULT_DATABASE_PATH
) -> None:
    initialize_database(db_path)
    with closing(connect(db_path)) as connection:
        if keep_dates:
            placeholders = ",".join("?" for _ in keep_dates)
            connection.execute(
                f"DELETE FROM runtime_documents WHERE system=? AND family=? AND date_iso NOT IN ({placeholders})",
                (system, family, *sorted(keep_dates)),
            )
        else:
            connection.execute(
                "DELETE FROM runtime_documents WHERE system=? AND family=?", (system, family)
            )
        connection.commit()


def clear_system_documents(*, system: str, db_path: Path = DEFAULT_DATABASE_PATH) -> None:
    if not db_path.exists():
        return
    with closing(connect(db_path)) as connection:
        connection.execute("DELETE FROM runtime_documents WHERE system=?", (system,))
        connection.commit()
