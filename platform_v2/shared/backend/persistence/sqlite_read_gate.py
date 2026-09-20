"""SQLite-primary runtime reads with optional JSON compatibility fallback."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
from typing import Any

from .runtime_document_codec import daily_identity
from .sqlite_document_queries import read_document
from .sqlite_schema import DEFAULT_DATABASE_PATH, PRIMARY_READ_ENABLED, connect


def read_daily_json_list(
    *,
    system: str,
    path: Path,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, Any]]:
    payload = _read_primary_daily_document(system=system, path=path, db_path=db_path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return _read_json_list_fallback(path)


def read_daily_json_dict(
    *,
    system: str,
    path: Path,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> dict[str, Any]:
    payload = _read_primary_daily_document(system=system, path=path, db_path=db_path)
    if isinstance(payload, dict):
        return payload
    return _read_json_dict_fallback(path)


def read_family_rows(
    *,
    system: str,
    family: str,
    json_folder: Path,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, Any]]:
    if PRIMARY_READ_ENABLED and db_path.exists():
        with closing(connect(db_path)) as connection:
            rows = connection.execute(
                """
                SELECT date_iso FROM runtime_documents
                WHERE system=? AND family=? AND payload_type='list'
                ORDER BY date_iso
                """,
                (system, family),
            ).fetchall()
        documents = [
            (str(row[0]), read_document(system=system, family=family, date_iso=str(row[0]), db_path=db_path))
            for row in rows
        ]
        if documents:
            combined: list[dict[str, Any]] = []
            for _, payload in documents:
                if not isinstance(payload, list):
                    continue
                combined.extend(row for row in payload if isinstance(row, dict))
            return combined
    return _read_json_family_rows(json_folder)


def _read_primary_daily_document(
    *,
    system: str,
    path: Path,
    db_path: Path,
) -> list[Any] | dict[str, Any] | None:
    if not PRIMARY_READ_ENABLED:
        return None
    identity = daily_identity(path)
    if identity is None:
        return None
    family, date_iso = identity
    payload = read_document(
        system=system,
        family=family,
        date_iso=date_iso,
        db_path=db_path,
    )
    if payload is not None:
        return payload
    return None


def _read_json_family_rows(json_folder: Path) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for path in sorted(json_folder.glob("*.json")) if json_folder.exists() else ():
        combined.extend(_read_json_list_fallback(path))
    return combined


def _read_json_list_fallback(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def _read_json_dict_fallback(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
