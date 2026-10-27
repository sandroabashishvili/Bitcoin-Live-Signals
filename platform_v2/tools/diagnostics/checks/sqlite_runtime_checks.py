"""Operational health checks for SQLite-primary runtime persistence."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing

from platform_v2.shared.backend.runtime_store.families.spot import FAMILY_BY_NAME as SPOT_FAMILIES
from platform_v2.shared.backend.runtime_store.families.futures import FAMILY_BY_NAME as FUTURES_FAMILIES
from platform_v2.shared.backend.runtime_store.validation import validate_runtime_record

from platform_v2.shared.backend.persistence import (
    CONTENT_DATABASE_PATH,
    DEFAULT_DATABASE_PATH,
    MARKET_DATA_DATABASE_PATH,
    content_database_status,
    database_status,
    market_database_status,
    parity_for_document,
)
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding
from platform_v2.tools.runtime_database_system.service import (
    content_parity_items,
    iter_runtime_documents,
    market_parity_items,
)


def sqlite_runtime_parity_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    source_documents = list(iter_runtime_documents())
    for path, status_reader, label in (
        (DEFAULT_DATABASE_PATH, database_status, "trading"),
        (MARKET_DATA_DATABASE_PATH, market_database_status, "market_data"),
        (CONTENT_DATABASE_PATH, content_database_status, "content"),
    ):
        if not path.exists():
            add_finding(findings, str(path), "sqlite_runtime_database_missing",
                        f"Required {label} database is missing", "high")
            continue
        try:
            status_reader()
            with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                integrity = [row[0] for row in connection.execute("PRAGMA quick_check")]
            if integrity != ["ok"]:
                add_finding(findings, str(path), "sqlite_integrity_error", f"{label}: {integrity}", "high")
        except (OSError, sqlite3.Error, KeyError, ValueError) as exc:
            add_finding(
                findings,
                str(path),
                "sqlite_database_unreadable",
                f"{label}: {type(exc).__name__}: {exc}",
                "high",
            )

    for system, family, date_iso, path in source_documents:
        if not DEFAULT_DATABASE_PATH.exists():
            break
        try:
            result = parity_for_document(
                system=system,
                family=family,
                date_iso=date_iso,
                json_path=path,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            add_finding(
                findings,
                str(path),
                "sqlite_runtime_parity_error",
                f"{type(exc).__name__}: {exc}",
                "high",
            )
            continue
        if result["status"] != "match":
            add_finding(
                findings,
                str(path),
                "sqlite_runtime_parity_mismatch",
                f"JSON rows={result['json_rows']} SQLite rows={result['sqlite_rows']}",
                "high",
            )
    findings.extend(_partitioned_database_findings())
    if DEFAULT_DATABASE_PATH.exists() and not any(
        item.issue == "sqlite_database_unreadable" and item.path == str(DEFAULT_DATABASE_PATH)
        for item in findings
    ):
        findings.extend(_sqlite_record_schema_findings())
    return findings


def _sqlite_record_schema_findings() -> list[FileFinding]:
    """Validate stored rows even when no legacy JSON export exists."""
    findings: list[FileFinding] = []
    registries = {"spot": SPOT_FAMILIES, "futures": FUTURES_FAMILIES}
    try:
        with closing(sqlite3.connect(DEFAULT_DATABASE_PATH.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            for system, family, day, ordinal, raw in connection.execute(
                "SELECT system, family, date_iso, ordinal, payload_json FROM runtime_rows"
            ):
                identity = f"{DEFAULT_DATABASE_PATH}#{system}/{family}/{day}/{ordinal}"
                try:
                    payload = json.loads(raw)
                except (ValueError, TypeError) as exc:
                    add_finding(findings, identity, "runtime_json_decode_error", str(exc), "high")
                    continue
                errors = validate_runtime_record(family, payload, family_by_name=registries.get(system, {}))
                if errors:
                    add_finding(findings, identity, "runtime_schema_error", "; ".join(errors), "high")
    except (OSError, sqlite3.Error) as exc:
        add_finding(findings, str(DEFAULT_DATABASE_PATH), "sqlite_database_unreadable", str(exc), "high")
    return findings


def _partitioned_database_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    if MARKET_DATA_DATABASE_PATH.exists():
        for item in market_parity_items():
            if item["status"] != "match":
                add_finding(
                    findings,
                    str(item["path"]),
                    "sqlite_market_data_parity_mismatch",
                    f"rows={item['rows']}",
                    "high",
                )
    if CONTENT_DATABASE_PATH.exists():
        for item in content_parity_items():
            if item["status"] != "match":
                add_finding(
                    findings,
                    str(item["path"]),
                    "sqlite_content_parity_mismatch",
                    f"items={item['items']}",
                    "high",
                )
    return findings
