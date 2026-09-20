from dataclasses import replace
from types import SimpleNamespace
import pytest
from platform_v2.public_site.news.py.news_pipeline.tests.test_feed_collector import _entry
from platform_v2.public_site.news.py.news_pipeline import feed_collector as collector
from platform_v2.public_site.news.py.news_pipeline.source_policy import SOURCE_POLICIES, validate_sources


def test_unknown_or_changed_feed_is_rejected():
    with pytest.raises(ValueError):
        validate_sources({"CoinDesk": "https://example.com/rss"})
    with pytest.raises(ValueError):
        validate_sources({"Federal Reserve Board": "https://example.com/rss"})
    validate_sources(collector.NEWS_SOURCES)


def test_only_reviewed_release_scope_is_allowed():
    policy = SOURCE_POLICIES["Federal Reserve Board"]
    assert policy.allows_link("https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm")
    assert not policy.allows_link("https://www.federalreserve.gov/econres/paper.htm")
    assert not policy.allows_link("https://evil.example/newsevents/pressreleases/monetary20260916a.htm")


def test_collector_rejects_external_and_rights_marked_entries(monkeypatch):
    prefix = "https://www.federalreserve.gov/newsevents/pressreleases/monetary"
    valid = _entry("Federal Reserve issues an updated FOMC statement", prefix+"20260916a.htm")
    reserved = _entry("Separate copyrighted institutional statement", prefix+"20260916b.htm")
    reserved["rights"] = "All rights reserved"
    external = _entry("An external statement must not inherit the license", "https://example.com/release")
    monkeypatch.setattr(collector, "fetch_text", lambda url: "feed")
    monkeypatch.setattr(collector.feedparser, "parse", lambda text: SimpleNamespace(entries=[valid,reserved,external],bozo=False))
    monkeypatch.setattr(collector, "resolve_image_candidates", lambda entry: pytest.fail("Images not licensed"))
    items = collector.collect_top_news(enforce_source_policy=True, resolve_images=True)
    assert [i.link for i in items] == [valid["link"]]
    assert items[0].summary == "Summary"
    assert items[0].image_candidates == []


def test_optech_newsletters_have_license_and_exclude_podcasts():
    from platform_v2.public_site.news.py.news_pipeline.source_policy import render_license
    policy = SOURCE_POLICIES['Bitcoin Optech']
    assert policy.allows_link('https://bitcoinops.org/en/newsletters/2026/09/18/')
    assert not policy.allows_link('https://bitcoinops.org/en/podcast/2026/09/18/')
    assert not policy.allows_link('https://bitcoinops.org/en/newsletters/../podcast/')
    assert '../licenses/bitcoin-optech-MIT.txt' in render_license('Bitcoin Optech', '../')
    assert render_license('Unknown', './') == ''


def test_sec_topic_filter_and_ecb_authored_material_exclusions():
    from platform_v2.public_site.news.py.news_pipeline.source_policy import permits_entry
    sec = SOURCE_POLICIES['SEC']
    assert sec.allows_link('https://www.sec.gov/newsroom/press-releases/2026-90-tokenized-stock')
    assert not sec.allows_link('https://www.sec.gov/Archives/edgar/company.htm')
    assert permits_entry('SEC', 'SEC announces tokenized stock exemption', '', {})
    assert not permits_entry('SEC', 'SEC announces staff appointment', '', {})
    ecb = SOURCE_POLICIES['European Central Bank']
    assert ecb.allows_link('https://www.ecb.europa.eu//press/pr/date/2026/html/ecb.example.en.html')
    assert not ecb.allows_link('https://www.ecb.europa.eu/press/inter/date/2026/html/interview.en.html')
    assert not permits_entry('European Central Bank', 'Study', '', {'author':'Named researcher'})
    assert permits_entry('European Central Bank', 'ECB monetary policy decisions', '', {})


def test_new_sources_have_scoped_destinations_and_topics():
    from platform_v2.public_site.news.py.news_pipeline.source_policy import permits_entry
    assert SOURCE_POLICIES['CFTC'].allows_link('https://www.cftc.gov/PressRoom/PressReleases/9300-26')
    assert not SOURCE_POLICIES['CFTC'].allows_link('https://www.cftc.gov/sites/default/files/third-party.pdf')
    assert permits_entry('CFTC','CFTC Staff Issues No-Action Position to Providers of Passive Software','',{})
    assert not permits_entry('CFTC','CFTC Announces Agricultural Conference','',{})
    assert permits_entry('U.S. Bureau of Economic Analysis','Personal Income and Outlays','',{})
    assert not permits_entry('U.S. Bureau of Economic Analysis','Arts and Cultural Production by State','',{})
    assert len(SOURCE_POLICIES['U.S. Bureau of Labor Statistics'].additional_feed_urls)==3


def test_multiple_feeds_keep_one_publisher_and_fetch_once(monkeypatch):
    name='U.S. Bureau of Labor Statistics'
    policy=SOURCE_POLICIES[name]
    monkeypatch.setattr(collector,'NEWS_SOURCES',{name:policy.feed_url})
    calls=[]
    monkeypatch.setattr(collector,'fetch_text',lambda url: calls.append(url) or url)
    entry=_entry('Consumer prices increased in the latest month','https://www.bls.gov/news.release/archives/cpi_09192026.htm')
    monkeypatch.setattr(collector.feedparser,'parse',lambda text: SimpleNamespace(entries=[entry],bozo=False))
    items=collector.collect_top_news(enforce_source_policy=True)
    assert len(calls)==len(set(calls))==4
    assert len(items)==1 and items[0].source==name


def test_reviewed_but_disabled_source_cannot_publish():
    with pytest.raises(ValueError):
        validate_sources({'CFTC':SOURCE_POLICIES['CFTC'].feed_url})
    assert 'CFTC' not in collector.NEWS_SOURCES


def test_cryptonews_rejects_advertorial_hosts_and_promotional_categories():
    from platform_v2.public_site.news.py.news_pipeline.source_policy import permits_entry
    policy=SOURCE_POLICIES['Cryptonews']
    assert policy.allows_link('https://cryptonews.com/news/institutional-bitcoin-adoption/')
    assert not policy.allows_link('https://advertorial.cryptonews.com/press-releases/promotion/')
    assert not policy.allows_link('https://cryptonews.com/cryptocurrency/best-presales/')
    assert permits_entry('Cryptonews','Institutional Bitcoin adoption expands','',{'tags':[{'term':'Bitcoin News'}]})
    for tag in ['Press Releases','presales','Sponsored','Industry Talk']:
        assert not permits_entry('Cryptonews','A seemingly ordinary news headline','',{'tags':[{'term':tag}]})


def test_cryptonews_summary_retains_text_without_syndication_footer():
    entry=_entry('Institutional Bitcoin adoption expands worldwide','https://cryptonews.com/news/institutions/')
    entry['summary']='<p>Original short feed excerpt.</p><p>The post <a href="https://cryptonews.com/news/institutions/">Headline</a> appeared first on <a href="https://cryptonews.com">Cryptonews</a>.</p>'
    item=collector._normalize_feed_item(entry,'Cryptonews',resolve_images=False)
    assert item.summary=='Original short feed excerpt.'
    assert item.source=='Cryptonews'


def test_nist_scope_excludes_general_science_and_unrelated_security():
    from platform_v2.public_site.news.py.news_pipeline.source_policy import permits_entry
    assert SOURCE_POLICIES['NIST'].allows_link('https://www.nist.gov/news-events/news/2026/09/digital-signatures')
    assert not SOURCE_POLICIES['NIST'].allows_link('https://www.nist.gov/publications/third-party-paper')
    assert permits_entry('NIST', 'NIST finalizes post-quantum digital signature standard', '', {})
    assert not permits_entry('NIST', 'NIST funds cybersecurity workforce training', '', {})
    assert not permits_entry('NIST', 'NIST studies atomic clocks', '', {})
    assert not permits_entry('European Central Bank', 'ECB appoints new staff member', '', {})


def test_newsbtc_uses_explicit_rss_scope_without_advertorials():
    from platform_v2.public_site.news.py.news_pipeline.source_policy import permits_entry
    policy = SOURCE_POLICIES['NewsBTC']
    assert policy.allows_link('https://www.newsbtc.com/news/coinbase-banking-announcement/')
    assert not policy.allows_link('https://www.newsbtc.com/press-releases/promoted-token/')
    assert not policy.allows_link('https://other.example/news/coinbase-banking-announcement/')
    assert permits_entry('NewsBTC', 'Coinbase opens digital asset infrastructure for banks', '', {})
    assert not permits_entry('NewsBTC', 'An apparently normal headline about a token', '', {'tags':[{'term':'Sponsored'}]})
    assert not policy.allow_images


def test_fed_expansion_excludes_unrelated_appointments():
    from platform_v2.public_site.news.py.news_pipeline.source_policy import permits_entry
    p=SOURCE_POLICIES['Federal Reserve Board']
    assert 'https://www.federalreserve.gov/feeds/press_all.xml' in p.additional_feed_urls
    assert p.allows_link('https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260920a.htm')
    assert permits_entry('Federal Reserve Board','Board updates capital requirements for banks','',{})
    assert not permits_entry('Federal Reserve Board','Board appoints a new administrative officer','',{})
