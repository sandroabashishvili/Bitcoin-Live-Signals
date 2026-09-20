from __future__ import annotations

from time import struct_time

from platform_v2.public_site.news.py.news_pipeline import feed_collector


class FeedEntry(dict):
    published_parsed: struct_time
    enclosures: list[dict[str, str]]


def test_normalize_feed_item_allows_missing_image(monkeypatch) -> None:
    entry = FeedEntry(
        title="A sufficiently descriptive Bitcoin headline for the daily archive",
        link="https://example.com/story",
        summary="A valid story summary.",
    )
    entry.published_parsed = struct_time((2026, 8, 26, 12, 0, 0, 2, 238, 0))
    entry.enclosures = []
    monkeypatch.setattr(feed_collector, "resolve_image_candidates", lambda _entry: [])

    item = feed_collector._normalize_feed_item(entry, "Example")

    assert item is not None
    assert item.image is None
    assert item.image_candidates == []


def _entry(title, link, hours=1):
    from datetime import datetime, timedelta, timezone
    entry = FeedEntry(title=title, link=link, summary='Summary')
    entry.published_parsed = (datetime.now(timezone.utc) - timedelta(hours=hours)).utctimetuple()
    entry.enclosures = []
    return entry


def _feeds(monkeypatch, feeds):
    from types import SimpleNamespace
    fetched, imaged = [], []
    monkeypatch.setattr(feed_collector, 'NEWS_SOURCES', {name: name for name in feeds})
    def fetch(url):
        fetched.append(url)
        return url
    monkeypatch.setattr(feed_collector, 'fetch_text', fetch)
    monkeypatch.setattr(feed_collector.feedparser, 'parse', lambda text: SimpleNamespace(entries=feeds[text],bozo=False))
    def images(entry):
        imaged.append(entry['link'])
        return []
    monkeypatch.setattr(feed_collector, 'resolve_image_candidates', images)
    return fetched, imaged


def test_corporate_bitcoin_purchase_is_news_not_buying_guide():
    assert feed_collector._is_quality_title('Public company plans to buy Bitcoin for its corporate treasury')
    assert not feed_collector._is_quality_title('How to buy Bitcoin: the complete guide for new investors')
    assert not feed_collector._is_quality_title('Sponsored: a new Bitcoin platform announces its token sale')


def test_fetches_each_feed_once_and_only_images_selected(monkeypatch):
    entries=[_entry(f'Bitcoin institution number {i} announces a new project',f'https://example.com/{i}',hours=1+i) for i in range(5)]
    fetched,imaged=_feeds(monkeypatch,{'A':entries,'B':[]})
    result=feed_collector.collect_top_news(2, resolve_images=True)
    assert len(result)==2
    assert fetched==['A','B']
    assert len(imaged)==2


def test_dedupes_same_link_or_same_title_before_images(monkeypatch):
    title='Bitcoin treasury company announces important quarterly results'
    fetched,imaged=_feeds(monkeypatch,{'A':[
        _entry(title,'https://example.com/story?utm_source=rss#section'),
        _entry('Another long headline about the same treasury results','https://example.com/story'),
        _entry(title.upper(),'https://other.example/story')], 'B':[
        _entry('A separate Bitcoin regulatory development is announced','https://other.example/separate')]})
    result=feed_collector.collect_top_news(12, resolve_images=True)
    assert len(result)==2
    assert len(imaged)==2
    assert {item.source for item in result}=={'A','B'}
    assert result[0].link=='https://example.com/story'


def test_future_old_and_invalid_links_are_skipped(monkeypatch):
    title='Bitcoin regulatory development receives a public hearing'
    fetched,imaged=_feeds(monkeypatch,{'A':[
        _entry(title,'https://example.com/future',hours=-24),
        _entry(title,'https://example.com/old',hours=200),
        _entry(title,'javascript:alert(1)'),
        _entry(title,'https://example.com/current')]})
    result=feed_collector.collect_top_news(12, resolve_images=True)
    assert [item.link for item in result]==['https://example.com/current']
    assert imaged==['https://example.com/current']


def test_zero_target_does_not_fetch(monkeypatch):
    fetched,imaged=_feeds(monkeypatch,{'A':[]})
    assert feed_collector.collect_top_news(0)==[]
    assert fetched==imaged==[]


def test_recoverable_parser_warning_keeps_valid_entries(monkeypatch):
    from types import SimpleNamespace
    entries=[_entry('Bitcoin regulatory development receives a public hearing','https://example.com/story')]
    _feeds(monkeypatch,{'A':entries})
    monkeypatch.setattr(feed_collector.feedparser,'parse',lambda _:SimpleNamespace(entries=entries,bozo=True,bozo_exception='recoverable warning'))
    assert len(feed_collector.collect_top_news())==1


def test_default_collection_never_fetches_article_images(monkeypatch):
    _, imaged = _feeds(monkeypatch, {'A': [_entry('Bitcoin regulatory development receives a public hearing', 'https://example.com/story')]})
    result = feed_collector.collect_top_news()
    assert len(result) == 1
    assert imaged == []
    assert result[0].image_candidates == []


def test_freshness_does_not_expand_to_fill_page(monkeypatch):
    _feeds(monkeypatch, {'A': [_entry('Bitcoin protocol upgrade completes successfully', 'https://example.com/old', hours=49)]})
    assert feed_collector.collect_top_news(12) == []


def test_spare_places_are_filled_from_other_publishers(monkeypatch):
    _feeds(monkeypatch, {'A': [_entry(f'Bitcoin project number {i} completes its launch', f'https://example.com/{i}') for i in range(10)],
                        'B': [_entry('Ethereum network publishes a new security update', 'https://other.example/update')]})
    items = feed_collector.collect_top_news(12)
    assert len(items) == 11
    assert sum(i.source == 'A' for i in items) == 10
    assert sum(i.source == 'A' for i in items[:5]) == 4


def test_total_feed_failure_is_not_an_empty_success(monkeypatch):
    import pytest
    monkeypatch.setattr(feed_collector, 'fetch_text', lambda _: '')
    with pytest.raises(RuntimeError, match='No usable feeds'):
        feed_collector.collect_top_news()


def test_two_day_window_reports_newer_and_older_stories(monkeypatch):
    _feeds(monkeypatch, {'A': [
        _entry('Bitcoin protocol update announced this morning', 'https://example.com/a', hours=1),
        _entry('Ethereum researchers publish signature improvements', 'https://example.com/b', hours=36),
        _entry('An older blockchain development was announced', 'https://example.com/c', hours=49)]})
    report = {}
    result = feed_collector.collect_top_news(diagnostics=report)
    assert len(result) == 2
    stats = report['feeds'][0]
    assert stats['entries'] == 3 and stats['within_24h'] == 1 and stats['within_window'] == 2
    assert stats['rejected']['older_than_window'] == 1
    assert report['selected_by_source'] == {'A': 2}


def test_two_plus_seven_returns_all_nine(monkeypatch):
    _feeds(monkeypatch, {name: [_entry(f'{name} Bitcoin company {i} releases quarterly results', f'https://example.com/{name}/{i}') for i in range(count)] for name,count in [('A',2),('B',7)]})
    assert len(feed_collector.collect_top_news(12)) == 9


def test_diversity_first_when_all_sources_can_fill_page(monkeypatch):
    _feeds(monkeypatch, {name: [_entry(f'{name} Bitcoin company {i} releases quarterly results', f'https://example.com/{name}/{i}') for i in range(9)] for name in ['A','B','C']})
    result = feed_collector.collect_top_news(12)
    assert len(result) == 12
    assert {name:sum(i.source==name for i in result) for name in ['A','B','C']} == {'A':4,'B':4,'C':4}


def test_factual_price_analysis_allowed_but_prediction_guides_blocked():
    assert feed_collector._is_quality_title('Bitcoin price analysis after the Federal Reserve decision')
    assert not feed_collector._is_quality_title('Bitcoin price prediction: buy this token now')


def test_punctuation_variants_dedupe_but_changed_figures_do_not(monkeypatch):
    _feeds(monkeypatch, {'A': [
        _entry('Bitcoin ETF inflows: 300 million dollars', 'https://example.com/a'),
        _entry('Bitcoin ETF inflows — 300 million dollars', 'https://example.com/b'),
        _entry('Bitcoin ETF inflows: 400 million dollars', 'https://example.com/c')]})
    assert len(feed_collector.collect_top_news()) == 2
