"""File: paths.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Path helpers for the V2 frontend-owned news pipeline.
"""

from __future__ import annotations

from pathlib import Path

from .config import V2NewsPipelineConfig


def news_frontend_dir(config: V2NewsPipelineConfig) -> Path:
    return config.frontend_news_dir


def news_data_dir(config: V2NewsPipelineConfig) -> Path:
    return news_frontend_dir(config) / "data"


def news_archive_dir(config: V2NewsPipelineConfig) -> Path:
    return news_frontend_dir(config) / "archive"


def news_assets_dir(config: V2NewsPipelineConfig) -> Path:
    return config.frontend_assets_dir / "news"


def daily_news_assets_dir(config: V2NewsPipelineConfig, day_iso: str) -> Path:
    return news_assets_dir(config) / day_iso


def daily_news_json_path(config: V2NewsPipelineConfig, day_iso: str) -> Path:
    return news_data_dir(config) / f"news_items_{day_iso}.json"


def daily_news_html_path(config: V2NewsPipelineConfig, day_iso: str) -> Path:
    return news_archive_dir(config) / f"{day_iso}.html"


def news_index_html_path(config: V2NewsPipelineConfig) -> Path:
    return news_frontend_dir(config) / "index.html"
