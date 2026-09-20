"""SQLite storage for exchange and future multi-asset market observations."""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from platform_v2.shared.backend.time import utc_now_ms
from platform_v2.shared.runtime_warnings import warn_runtime_fallback

from .database_paths import MARKET_DATA_DATABASE_PATH
from .market_record_codec import canonical_json, event_time_ms, number_or_none
from .sqlite_market_schema import connect_market_database as connect
from .sqlite_market_schema import initialize_market_database


SUPPORTED_DATASETS = ("candles", "indicators", "orderflow")
LIVE_RUNTIME_ROOT = MARKET_DATA_DATABASE_PATH.parents[1]


def replace_market_series(
    *,
    venue: str,
    asset_class: str,
    market_type: str,
    dataset: str,
    symbol: str,
    timeframe: str,
    rows: Iterable[dict[str, Any]],
    source_path: Path | None = None,
    db_path: Path = MARKET_DATA_DATABASE_PATH,
) -> None:
    if dataset not in SUPPORTED_DATASETS:
        raise ValueError(f"Unsupported market dataset: {dataset}")
    if db_path == MARKET_DATA_DATABASE_PATH and source_path is not None:
        try:
            source_path.resolve().relative_to(LIVE_RUNTIME_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("Refusing to write non-runtime test data into the live market database") from exc
    normalized = [dict(row) for row in rows if isinstance(row, dict)]
    canonical = canonical_json(normalized)
    payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    initialize_market_database(db_path)
    identity = (
        venue.strip().lower(),
        asset_class.strip().lower(),
        market_type.strip().lower(),
        dataset,
        symbol.strip().upper(),
        timeframe.strip(),
    )
    with closing(connect(db_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO market_series(
                venue, asset_class, market_type, dataset, symbol, timeframe,
                row_count, payload_sha256, source_path, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(venue, asset_class, market_type, dataset, symbol, timeframe)
            DO UPDATE SET
                row_count=excluded.row_count,
                payload_sha256=excluded.payload_sha256,
                source_path=excluded.source_path,
                updated_at_ms=excluded.updated_at_ms
            """,
            (*identity, len(normalized), payload_hash, str(source_path) if source_path else None, utc_now_ms()),
        )
        connection.execute(
            """
            DELETE FROM market_observations
            WHERE venue=? AND asset_class=? AND market_type=? AND dataset=?
              AND symbol=? AND timeframe=?
            """,
            identity,
        )
        connection.executemany(
            """
            INSERT INTO market_observations(
                venue, asset_class, market_type, dataset, symbol, timeframe,
                event_time_ms, ordinal, open, high, low, close, volume, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (*identity, event_time_ms(row, index), index, number_or_none(row.get("open")),
                 number_or_none(row.get("high")), number_or_none(row.get("low")),
                 number_or_none(row.get("close") or row.get("price")),
                 number_or_none(row.get("volume")), canonical_json(row))
                for index, row in enumerate(normalized)
            ],
        )
        connection.commit()


def replace_market_series_safely(**kwargs: Any) -> bool:
    source_path = kwargs.get("source_path")
    if isinstance(source_path, Path):
        try:
            source_path.resolve().relative_to(LIVE_RUNTIME_ROOT.resolve())
        except ValueError:
            # Unit tests and offline tools may redirect output outside runtime.
            # Such data must never mutate the live market database.
            return False
    try:
        replace_market_series(**kwargs)
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        warn_runtime_fallback(
            scope="sqlite_market_data_store",
            operation="replace_market_series",
            error=exc,
            fallback="market JSON remains available",
            extra={
                "dataset": str(kwargs.get("dataset") or ""),
                "symbol": str(kwargs.get("symbol") or ""),
                "timeframe": str(kwargs.get("timeframe") or ""),
            },
        )
        return False
    return True


def read_market_series(
    *,
    venue: str,
    asset_class: str,
    market_type: str,
    dataset: str,
    symbol: str,
    timeframe: str,
    db_path: Path = MARKET_DATA_DATABASE_PATH,
) -> list[dict[str, Any]]:
    # A clean reset removes the whole database root. Initialize before the
    # first read; this is also safe when Spot and Futures start in parallel.
    if not db_path.exists():
        initialize_market_database(db_path)
    identity = (
        venue.strip().lower(),
        asset_class.strip().lower(),
        market_type.strip().lower(),
        dataset,
        symbol.strip().upper(),
        timeframe.strip(),
    )
    for attempt in range(2):
        try:
            with closing(connect(db_path)) as connection:
                exists = connection.execute(
                    """
                    SELECT 1 FROM market_series
                    WHERE venue=? AND asset_class=? AND market_type=? AND dataset=?
                      AND symbol=? AND timeframe=?
                    """,
                    identity,
                ).fetchone()
                rows = connection.execute(
                    """
                    SELECT payload_json FROM market_observations
                    WHERE venue=? AND asset_class=? AND market_type=? AND dataset=?
                      AND symbol=? AND timeframe=?
                    ORDER BY ordinal
                    """,
                    identity,
                ).fetchall()
            break
        except sqlite3.OperationalError as exc:
            if attempt > 0 or "no such table" not in str(exc).lower():
                raise
            # The sibling process may have created the file but not its schema.
            initialize_market_database(db_path)
    else:  # pragma: no cover - loop either succeeds or raises
        return []
    if exists is None:
        return []
    return [item for row in rows if isinstance((item := json.loads(row[0])), dict)]


def read_market_series_safely(**kwargs: Any) -> list[dict[str, Any]]:
    try:
        return read_market_series(**kwargs)
    except (OSError, sqlite3.Error, TypeError, ValueError, json.JSONDecodeError) as exc:
        warn_runtime_fallback(
            scope="sqlite_market_data_store",
            operation="read_market_series",
            error=exc,
            fallback="caller may read market JSON compatibility file",
            extra={
                "dataset": str(kwargs.get("dataset") or ""),
                "symbol": str(kwargs.get("symbol") or ""),
                "timeframe": str(kwargs.get("timeframe") or ""),
            },
        )
        return []


def market_database_status(db_path: Path = MARKET_DATA_DATABASE_PATH) -> dict[str, Any]:
    if not db_path.exists():
        return {"path": str(db_path), "exists": False, "series": 0, "observations": 0, "size_bytes": 0}
    with closing(connect(db_path)) as connection:
        series = connection.execute("SELECT COUNT(*) FROM market_series").fetchone()[0]
        observations = connection.execute("SELECT COUNT(*) FROM market_observations").fetchone()[0]
    return {
        "path": str(db_path),
        "exists": True,
        "series": int(series),
        "observations": int(observations),
        "size_bytes": db_path.stat().st_size,
    }


def list_market_series(db_path: Path = MARKET_DATA_DATABASE_PATH) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with closing(connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT venue, asset_class, market_type, dataset, symbol, timeframe,
                   row_count, source_path, updated_at_ms
            FROM market_series
            ORDER BY venue, asset_class, market_type, dataset, symbol, timeframe
            """
        ).fetchall()
    keys = (
        "venue", "asset_class", "market_type", "dataset", "symbol", "timeframe",
        "row_count", "source_path", "updated_at_ms",
    )
    return [dict(zip(keys, row)) for row in rows]


def market_series_parity(
    *,
    rows: list[dict[str, Any]],
    venue: str,
    asset_class: str,
    market_type: str,
    dataset: str,
    symbol: str,
    timeframe: str,
    db_path: Path = MARKET_DATA_DATABASE_PATH,
) -> bool:
    stored = read_market_series(
        venue=venue,
        asset_class=asset_class,
        market_type=market_type,
        dataset=dataset,
        symbol=symbol,
        timeframe=timeframe,
        db_path=db_path,
    )
    return canonical_json(rows) == canonical_json(stored)
