"""Operational health checks for SQLite-primary runtime persistence."""

from __future__ import annotations

import json
import sqlite3

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
    if source_documents and not DEFAULT_DATABASE_PATH.exists():
        add_finding(
            findings,
            str(DEFAULT_DATABASE_PATH),
            "sqlite_runtime_database_missing",
            "JSON ledgers exist but the SQLite mirror has not been initialized",
            "high",
        )
        return findings

    for path, status_reader, label in (
        (DEFAULT_DATABASE_PATH, database_status, "trading"),
        (MARKET_DATA_DATABASE_PATH, market_database_status, "market_data"),
        (CONTENT_DATABASE_PATH, content_database_status, "content"),
    ):
        if not path.exists():
            continue
        try:
            status_reader()
        except (OSError, sqlite3.Error, KeyError, ValueError) as exc:
            add_finding(
                findings,
                str(path),
                "sqlite_database_unreadable",
                f"{label}: {type(exc).__name__}: {exc}",
                "high",
            )

    for system, family, date_iso, path in source_documents:
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
