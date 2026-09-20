"""SQLite runtime document writes, indexed rows, parity, and JSON export."""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from platform_v2.shared.backend.serialization import to_runtime_dict
from platform_v2.shared.backend.time import utc_now_ms
from platform_v2.shared.runtime_warnings import warn_runtime_fallback

from .runtime_document_codec import canonical_json, daily_identity, indexed_row
from .sqlite_schema import (
    DEFAULT_DATABASE_PATH,
    MIRROR_ENABLED,
    connect,
    initialize_database,
)


def mirror_document(
    *,
    system: str,
    family: str,
    date_iso: str,
    payload: Any,
    source_path: Path | None = None,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    normalized = to_runtime_dict(payload)
    if not isinstance(normalized, (list, dict)):
        raise TypeError("Runtime SQLite documents must be a list or object.")
    payload_type = "list" if isinstance(normalized, list) else "object"
    rows = normalized if isinstance(normalized, list) else [normalized]
    canonical = canonical_json(normalized)
    payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    initialize_database(db_path)

    with closing(connect(db_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO runtime_documents(
                system, family, date_iso, payload_type, row_count,
                payload_sha256, source_path, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(system, family, date_iso) DO UPDATE SET
                payload_type=excluded.payload_type,
                row_count=excluded.row_count,
                payload_sha256=excluded.payload_sha256,
                source_path=excluded.source_path,
                updated_at_ms=excluded.updated_at_ms
            """,
            (
                system,
                family,
                date_iso,
                payload_type,
                len(rows),
                payload_hash,
                str(source_path) if source_path else None,
                utc_now_ms(),
            ),
        )
        connection.execute(
            "DELETE FROM runtime_rows WHERE system=? AND family=? AND date_iso=?",
            (system, family, date_iso),
        )
        connection.executemany(
            """
            INSERT INTO runtime_rows(
                system, family, date_iso, ordinal, timestamp_ms, entity_id,
                symbol, side, status, net_pnl, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                indexed_row(
                    system=system,
                    family=family,
                    date_iso=date_iso,
                    ordinal=index,
                    row=row,
                )
                for index, row in enumerate(rows)
                if isinstance(row, dict)
            ],
        )
        connection.commit()


def mirror_document_safely(
    *,
    system: str,
    family: str,
    date_iso: str,
    payload: Any,
    source_path: Path | None = None,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> bool:
    if not MIRROR_ENABLED:
        return False
    try:
        mirror_document(
            system=system,
            family=family,
            date_iso=date_iso,
            payload=payload,
            source_path=source_path,
            db_path=db_path,
        )
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        warn_runtime_fallback(
            scope="sqlite_runtime_store",
            operation="mirror_document",
            error=exc,
            fallback="return failure to the database-first runtime writer",
            extra={"system": system, "family": family, "date_iso": date_iso},
        )
        return False
    return True


def mirror_daily_json_path_safely(
    *,
    system: str,
    path: Path,
    payload: Any,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> bool:
    identity = daily_identity(path)
    if identity is None:
        return False
    family, date_iso = identity
    return mirror_document_safely(
        system=system,
        family=family,
        date_iso=date_iso,
        payload=payload,
        source_path=path,
        db_path=db_path,
    )


def import_json_document(
    *,
    system: str,
    family: str,
    date_iso: str,
    source_path: Path,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    mirror_document(
        system=system,
        family=family,
        date_iso=date_iso,
        payload=payload,
        source_path=source_path,
        db_path=db_path,
    )
