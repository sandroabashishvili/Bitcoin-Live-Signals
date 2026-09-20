"""File: orchestrator.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Orchestrate V2 frontend-owned news generation.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json

from platform_v2.shared.backend.persistence import read_news_batch, replace_news_batch_safely

from .source_policy import SOURCE_POLICIES, validate_sources
from .config import V2NewsPipelineConfig, load_config
from .daily_page_builder import DailyNewsPageBuilder
from .feed_collector import NEWS_WINDOW_HOURS, NEWS_SOURCES, collect_top_news
from .index_builder import NewsIndexBuilder
from .models import NewsCollectionResult, NewsItem
from .paths import daily_news_json_path, news_archive_dir, news_assets_dir, news_data_dir
from .retention import apply_news_retention


def run_news_generation(config: V2NewsPipelineConfig | None = None) -> dict[str, object]:
    resolved = config or load_config()
    if not resolved.publication_rights_reviewed:
        raise RuntimeError(
            "News publication paused: source collection and reuse rights require a documented review. "
            "No feeds fetched and no public files changed; existing archives require a separate review."
        )
    validate_sources(NEWS_SOURCES)
    day_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    data_dir = news_data_dir(resolved)
    archive_dir = news_archive_dir(resolved)
    assets_dir = news_assets_dir(resolved)

    data_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    diagnostics: dict = {}
    items = collect_top_news(diagnostics=diagnostics, target_count=resolved.max_news_items, resolve_images=resolved.reuse_publisher_images, enforce_source_policy=True)
    generated_at_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    stored = replace_news_batch_safely(
        day_iso=day_iso,
        generated_at_utc=generated_at_utc,
        items=[asdict(item) for item in items],
        metadata={
            "collection_diagnostics": diagnostics,
            "source_names": list(NEWS_SOURCES.keys()),
            "source_policies": {name: asdict(SOURCE_POLICIES[name]) for name in NEWS_SOURCES},
            "lookback_hours": [NEWS_WINDOW_HOURS],
        },
    )
    if stored:
        database_rows = read_news_batch(day_iso)
        items = [_news_item_from_row(row) for row in database_rows]
    collection = NewsCollectionResult(
        day_iso=day_iso,
        items=items,
        generated_at_utc=generated_at_utc,
        source_names=list(NEWS_SOURCES.keys()),
        lookback_hours=[NEWS_WINDOW_HOURS],
    )
    daily_archive_path, render_ready_items = DailyNewsPageBuilder().build(items, day_iso, resolved)
    replace_news_batch_safely(
        day_iso=day_iso,
        generated_at_utc=generated_at_utc,
        items=[asdict(item) for item in render_ready_items],
        metadata={
            "source_names": collection.source_names,
            "lookback_hours": collection.lookback_hours,
            "render_ready": True,
            "collection_diagnostics": diagnostics,
        },
    )
    daily_json = daily_news_json_path(resolved, day_iso)
    daily_json.write_text(
        json.dumps(
            {
                "day_iso": collection.day_iso,
                "generated_at_utc": collection.generated_at_utc,
                "source_names": collection.source_names,
                "lookback_hours": collection.lookback_hours,
                "collection_diagnostics": diagnostics,
                "count": len(render_ready_items),
                "items": [asdict(item) for item in render_ready_items],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    retention_result = apply_news_retention(config=resolved, today_iso=day_iso)
    index_builder = NewsIndexBuilder()
    news_index_path = index_builder.build(day_iso, render_ready_items, daily_archive_path, resolved, generated_at=generated_at_utc)
    archive_index_path = index_builder.build_archive_index(
        latest_day_iso=day_iso,
        latest_count=len(render_ready_items),
        latest_sources=len({item.source.strip() for item in render_ready_items if item.source.strip()}),
        archive_dir=archive_dir,
    )

    return {
        "data_dir": data_dir,
        "archive_dir": archive_dir,
        "assets_dir": assets_dir,
        "daily_json_path": daily_json,
        "daily_archive_path": daily_archive_path,
        "news_index_path": news_index_path,
        "archive_index_path": archive_index_path,
        "news_retention_cutoff": retention_result.cutoff_day,
        "news_retention_removed_count": retention_result.removed_count,
    }


def _news_item_from_row(row: dict[str, object]) -> NewsItem:
    raw_candidates = row.get("image_candidates")
    image_candidates = raw_candidates if isinstance(raw_candidates, list) else []
    return NewsItem(
        license_url=str(row.get("license_url")) if row.get("license_url") else None,
        title=str(row.get("title") or ""),
        link=str(row.get("link") or ""),
        summary=str(row.get("summary") or ""),
        source=str(row.get("source") or ""),
        date=str(row.get("date") or ""),
        date_human=str(row.get("date_human") or ""),
        pub_ts=int(row.get("pub_ts") or 0),
        image_candidates=[str(value) for value in image_candidates if value],
        image=str(row.get("image")) if row.get("image") else None,
        image_local=str(row.get("image_local")) if row.get("image_local") else None,
    )
