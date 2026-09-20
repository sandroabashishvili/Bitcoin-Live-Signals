"""File: retention.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-05-25
Last updated date: 2026-05-25
Author: Codex
Purpose: Retain only the recent public news archive, data, and image assets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import shutil

from .config import V2NewsPipelineConfig
from .paths import news_archive_dir, news_assets_dir, news_data_dir


@dataclass(frozen=True)
class NewsRetentionResult:
    cutoff_day: str
    removed_archive_pages: list[Path]
    removed_data_files: list[Path]
    removed_asset_dirs: list[Path]

    @property
    def removed_count(self) -> int:
        return len(self.removed_archive_pages) + len(self.removed_data_files) + len(self.removed_asset_dirs)


def apply_news_retention(
    *,
    config: V2NewsPipelineConfig,
    today_iso: str,
    dry_run: bool = False,
) -> NewsRetentionResult:
    """Remove date-scoped news artifacts older than the configured retention window."""

    cutoff = _cutoff_day(today_iso=today_iso, retention_days=config.retention_days)
    removed_archive_pages = _remove_old_archive_pages(config=config, cutoff=cutoff, dry_run=dry_run)
    removed_data_files = _remove_old_data_files(config=config, cutoff=cutoff, dry_run=dry_run)
    removed_asset_dirs = _remove_old_asset_dirs(config=config, cutoff=cutoff, dry_run=dry_run)
    return NewsRetentionResult(
        cutoff_day=cutoff.isoformat(),
        removed_archive_pages=removed_archive_pages,
        removed_data_files=removed_data_files,
        removed_asset_dirs=removed_asset_dirs,
    )


def _cutoff_day(*, today_iso: str, retention_days: int) -> date:
    today = datetime.strptime(today_iso, "%Y-%m-%d").date()
    kept_days = max(1, retention_days)
    return today - timedelta(days=kept_days - 1)


def _remove_old_archive_pages(
    *,
    config: V2NewsPipelineConfig,
    cutoff: date,
    dry_run: bool,
) -> list[Path]:
    removed: list[Path] = []
    for path in sorted(news_archive_dir(config).glob("*.html")):
        day = _parse_day(path.stem)
        if day is None or day >= cutoff:
            continue
        removed.append(path)
        if not dry_run:
            path.unlink(missing_ok=True)
    return removed


def _remove_old_data_files(
    *,
    config: V2NewsPipelineConfig,
    cutoff: date,
    dry_run: bool,
) -> list[Path]:
    removed: list[Path] = []
    for path in sorted(news_data_dir(config).glob("news_items_*.json")):
        day = _parse_day(path.stem.removeprefix("news_items_"))
        if day is None or day >= cutoff:
            continue
        removed.append(path)
        if not dry_run:
            path.unlink(missing_ok=True)
    return removed


def _remove_old_asset_dirs(
    *,
    config: V2NewsPipelineConfig,
    cutoff: date,
    dry_run: bool,
) -> list[Path]:
    removed: list[Path] = []
    assets_dir = news_assets_dir(config)
    for path in sorted(item for item in assets_dir.iterdir() if item.is_dir()):
        day = _parse_day(path.name)
        if day is None or day >= cutoff:
            continue
        removed.append(path)
        if not dry_run:
            shutil.rmtree(path, ignore_errors=True)
    return removed


def _parse_day(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
