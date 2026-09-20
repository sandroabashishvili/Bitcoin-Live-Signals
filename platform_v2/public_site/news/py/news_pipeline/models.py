"""File: models.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Shared typed models for the V2 news pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    summary: str
    source: str
    date: str
    date_human: str
    pub_ts: int
    image_candidates: list[str]
    license_url: str | None = None
    image: str | None = None
    image_local: str | None = None


@dataclass(frozen=True)
class NewsCollectionResult:
    day_iso: str
    items: list[NewsItem]
    generated_at_utc: str
    source_names: list[str]
    lookback_hours: list[int]
    image: str | None = None
