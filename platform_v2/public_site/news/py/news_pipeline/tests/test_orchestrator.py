from __future__ import annotations

from pathlib import Path

import pytest

from platform_v2.public_site.news.py.news_pipeline import orchestrator
from platform_v2.public_site.news.py.news_pipeline.config import V2NewsPipelineConfig


def test_failed_collection_does_not_replace_last_good_snapshot(monkeypatch, tmp_path: Path) -> None:
    config = V2NewsPipelineConfig(
        frontend_news_dir=tmp_path / "news",
        frontend_assets_dir=tmp_path / "assets",
        max_news_items=12,
        retention_days=10,
        download_images=False,
        max_image_width=960,
        thumb_width=480,
        image_quality=82,
        publication_rights_reviewed=True,
    )
    def failed_collection(**kwargs):
        raise RuntimeError("No usable feeds")
    monkeypatch.setattr(orchestrator, "collect_top_news", failed_collection)

    def fail_if_called(**_kwargs):
        raise AssertionError("storage must not be touched after a failed collection")

    monkeypatch.setattr(orchestrator, "replace_news_batch_safely", fail_if_called)

    with pytest.raises(RuntimeError, match="No usable feeds"):
        orchestrator.run_news_generation(config)

    assert not list((config.frontend_news_dir / "data").glob("news_items_*.json"))
    assert not list((config.frontend_news_dir / "archive").glob("*.html"))


def test_unreviewed_publication_does_not_fetch_or_write(monkeypatch, tmp_path):
    from dataclasses import replace
    from platform_v2.public_site.news.py.news_pipeline.config import load_config
    config = replace(load_config(), publication_rights_reviewed=False, frontend_news_dir=tmp_path / 'news', frontend_assets_dir=tmp_path / 'assets')
    def forbidden(**kwargs):
        raise AssertionError('No collection before rights review')
    monkeypatch.setattr(orchestrator, 'collect_top_news', forbidden)
    with pytest.raises(RuntimeError, match='publication paused'):
        orchestrator.run_news_generation(config)
    assert not (tmp_path / 'news').exists()


def test_default_render_preparation_removes_unlicensed_cached_media(tmp_path, monkeypatch):
    from dataclasses import replace
    from platform_v2.public_site.news.py.news_pipeline.config import load_config
    from platform_v2.public_site.news.py.news_pipeline.daily_page_builder import DailyNewsPageBuilder
    from platform_v2.public_site.news.py.news_pipeline.models import NewsItem
    item = NewsItem(title='Test headline', link='https://example.com', summary='Publisher excerpt', source='Example', date='2026-09-18', date_human='Sep 18', pub_ts=1, image_candidates=['https://example.com/image.jpg'], image='remote.jpg', image_local='../assets/cached.jpg')
    config = replace(load_config(), frontend_news_dir=tmp_path / 'news', frontend_assets_dir=tmp_path / 'assets')
    builder = DailyNewsPageBuilder()
    result = builder._prepare_items([item], '2026-09-18', config)[0]
    assert result.summary == ''
    assert result.image is None and result.image_local is None
    assert result.image_candidates == []


def test_successful_empty_collection_replaces_stale_front_page(monkeypatch, tmp_path):
    from dataclasses import replace
    from platform_v2.public_site.news.py.news_pipeline.config import load_config
    config = replace(load_config(), frontend_news_dir=tmp_path/'news', frontend_assets_dir=tmp_path/'assets')
    monkeypatch.setattr(orchestrator, 'collect_top_news', lambda **kw: [])
    monkeypatch.setattr(orchestrator, 'replace_news_batch_safely', lambda **kw: False)
    monkeypatch.setattr(orchestrator, 'apply_news_retention', lambda **kw: type('Retention', (), {'cutoff_day':'2026-09-01', 'removed_count':0})())
    result = orchestrator.run_news_generation(config)
    page = result['news_index_path'].read_text()
    assert 'No fresh stories' in page
    assert 'Updated:' in page
    assert 'last 48 hours' in page


def test_index_preserves_collection_timestamp_and_separates_calendar(tmp_path):
    from platform_v2.public_site.news.py.news_pipeline.index_builder import NewsIndexBuilder
    archive=tmp_path/'archive'; archive.mkdir()
    rendered=NewsIndexBuilder().render('2026-09-20',[],archive/'2026-09-20.html',generated_at='2026-09-20 04:05:03 UTC')
    assert 'Updated: 2026-09-20 04:05:03 UTC' in rendered
    assert 'Economic calendar' in rendered
    assert 'official schedules' in rendered
    assert 'Maximum 4 per publisher' not in rendered
