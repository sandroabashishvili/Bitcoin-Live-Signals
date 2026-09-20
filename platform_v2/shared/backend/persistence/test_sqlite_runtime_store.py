"""Regression tests for the SQLite runtime mirror and export gate."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from platform_v2.shared.backend.persistence.sqlite_runtime_store import (
    database_status,
    export_document_to_json,
    mirror_document,
    parity_for_document,
    read_document,
    read_family_rows,
)


def test_mirror_preserves_document_and_row_index() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        db_path = root / "runtime.sqlite3"
        payload = [
            {
                "timestamp_ms": 123,
                "position_id": "FUT-1",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "status": "OPENED",
            }
        ]

        mirror_document(
            system="futures",
            family="futures_positions",
            date_iso="2026-08-01",
            payload=payload,
            db_path=db_path,
        )

        assert read_document(
            system="futures",
            family="futures_positions",
            date_iso="2026-08-01",
            db_path=db_path,
        ) == payload
        assert database_status(db_path)["documents"] == 1
        assert database_status(db_path)["rows"] == 1


def test_parity_and_export_match_canonical_json() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        db_path = root / "runtime.sqlite3"
        source = root / "signals_2026-08-01.json"
        target = root / "export" / source.name
        payload = [{"timestamp_ms": 123, "side": "BUY", "score": 9.2}]
        source.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        mirror_document(
            system="spot",
            family="signals",
            date_iso="2026-08-01",
            payload=payload,
            source_path=source,
            db_path=db_path,
        )

        parity = parity_for_document(
            system="spot",
            family="signals",
            date_iso="2026-08-01",
            json_path=source,
            db_path=db_path,
        )
        export_document_to_json(
            system="spot",
            family="signals",
            date_iso="2026-08-01",
            target_path=target,
            db_path=db_path,
        )

        assert parity["status"] == "match"
        assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_family_primary_read_rebuilds_documents_from_indexed_rows() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        db_path = root / "trading.sqlite3"
        family_dir = root / "signals"
        family_dir.mkdir()
        first = [{"timestamp_ms": 1, "side": "BUY"}]
        second = [{"timestamp_ms": 2, "side": "NO_SIGNAL"}]
        for date_iso, payload in (("2026-07-31", first), ("2026-08-01", second)):
            source = family_dir / f"signals_{date_iso}.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            mirror_document(
                system="spot",
                family="signals",
                date_iso=date_iso,
                payload=payload,
                source_path=source,
                db_path=db_path,
            )

        assert read_family_rows(
            system="spot",
            family="signals",
            json_folder=family_dir,
            db_path=db_path,
        ) == first + second
