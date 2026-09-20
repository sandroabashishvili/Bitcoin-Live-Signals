"""SQLite storage for public-site content independently from trading state."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from platform_v2.shared.backend.time import utc_now_ms
from platform_v2.shared.runtime_warnings import warn_runtime_fallback

from .database_paths import CONTENT_DATABASE_PATH
from .sqlite_common import connect_sqlite, initialize_sqlite_database


SCHEMA_VERSION = 1
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS news_batches (
    day_iso TEXT PRIMARY KEY,
    generated_at_utc TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS news_articles (
    day_iso TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    link TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    published_at_ms INTEGER,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (day_iso, ordinal),
    FOREIGN KEY (day_iso) REFERENCES news_batches(day_iso) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_news_articles_link ON news_articles(link);
CREATE INDEX IF NOT EXISTS idx_news_articles_published ON news_articles(published_at_ms);
"""


def connect(db_path: Path = CONTENT_DATABASE_PATH) -> sqlite3.Connection:
    return connect_sqlite(db_path)


def initialize_content_database(db_path: Path = CONTENT_DATABASE_PATH) -> Path:
    return initialize_sqlite_database(
        db_path=db_path,
        schema_sql=SCHEMA_SQL,
        schema_version=SCHEMA_VERSION,
    )


def replace_news_batch(
    *,
    day_iso: str,
    generated_at_utc: str,
    items: Iterable[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    db_path: Path = CONTENT_DATABASE_PATH,
) -> None:
    rows = [dict(item) for item in items if isinstance(item, dict)]
    initialize_content_database(db_path)
    with closing(connect(db_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO news_batches(day_iso, generated_at_utc, item_count, metadata_json, updated_at_ms)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(day_iso) DO UPDATE SET
                generated_at_utc=excluded.generated_at_utc,
                item_count=excluded.item_count,
                metadata_json=excluded.metadata_json,
                updated_at_ms=excluded.updated_at_ms
            """,
            (day_iso, generated_at_utc, len(rows), json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True), utc_now_ms()),
        )
        connection.execute("DELETE FROM news_articles WHERE day_iso=?", (day_iso,))
        connection.executemany(
            """
            INSERT INTO news_articles(
                day_iso, ordinal, link, source, title, summary, published_at_ms, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    day_iso,
                    index,
                    str(row.get("link") or ""),
                    str(row.get("source") or ""),
                    str(row.get("title") or ""),
                    str(row.get("summary") or ""),
                    _int_or_none(row.get("pub_ts")),
                    json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                )
                for index, row in enumerate(rows)
            ],
        )
        connection.commit()


def replace_news_batch_safely(**kwargs: Any) -> bool:
    try:
        replace_news_batch(**kwargs)
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        warn_runtime_fallback(
            scope="sqlite_content_store",
            operation="replace_news_batch",
            error=exc,
            fallback="continue with collected in-memory news items",
            extra={"day_iso": str(kwargs.get("day_iso") or "")},
        )
        return False
    return True


def read_news_batch(day_iso: str, db_path: Path = CONTENT_DATABASE_PATH) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with closing(connect(db_path)) as connection:
        rows = connection.execute(
            "SELECT payload_json FROM news_articles WHERE day_iso=? ORDER BY ordinal",
            (day_iso,),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def content_database_status(db_path: Path = CONTENT_DATABASE_PATH) -> dict[str, Any]:
    if not db_path.exists():
        return {"path": str(db_path), "exists": False, "batches": 0, "articles": 0, "size_bytes": 0}
    with closing(connect(db_path)) as connection:
        batches = connection.execute("SELECT COUNT(*) FROM news_batches").fetchone()[0]
        articles = connection.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
    return {
        "path": str(db_path),
        "exists": True,
        "batches": int(batches),
        "articles": int(articles),
        "size_bytes": db_path.stat().st_size,
    }


def list_news_batches(db_path: Path = CONTENT_DATABASE_PATH) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with closing(connect(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT day_iso, generated_at_utc, item_count, metadata_json, updated_at_ms
            FROM news_batches ORDER BY day_iso
            """
        ).fetchall()
    return [
        {
            "day_iso": row[0],
            "generated_at_utc": row[1],
            "item_count": int(row[2]),
            "metadata": json.loads(row[3]),
            "updated_at_ms": int(row[4]),
        }
        for row in rows
    ]


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
