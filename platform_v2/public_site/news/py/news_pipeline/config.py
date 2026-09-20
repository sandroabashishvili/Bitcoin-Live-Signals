"""File: config.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Central configuration for the V2 frontend-owned news pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class V2NewsPipelineConfig:
    frontend_news_dir: Path
    frontend_assets_dir: Path
    max_news_items: int
    retention_days: int
    download_images: bool
    max_image_width: int
    thumb_width: int
    image_quality: int
    # A documented source/usage review is required before public generation.
    publication_rights_reviewed: bool = False
    reuse_publisher_images: bool = False
    reuse_publisher_summaries: bool = False


def load_config() -> V2NewsPipelineConfig:
    base_dir = Path(__file__).resolve().parents[2]
    frontend_dir = base_dir.parent
    assets_dir = frontend_dir / "assets"
    return V2NewsPipelineConfig(
        frontend_news_dir=base_dir,
        frontend_assets_dir=assets_dir,
        max_news_items=12,
        retention_days=10,
        download_images=False,
        max_image_width=960,
        thumb_width=480,
        image_quality=82,
        publication_rights_reviewed=True,
        reuse_publisher_summaries=True,
    )
