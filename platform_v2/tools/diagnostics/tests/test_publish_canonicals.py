from pathlib import Path

from platform_v2.tools.diagnostics.checks import seo_checks


def test_dashboard_canonical_is_checked_at_published_path(monkeypatch, tmp_path: Path):
    root = tmp_path / 'publish' / 'Bitcoin-Live-Signals'
    page = root / 'spot/dashboard/portfolio/index.html'
    page.parent.mkdir(parents=True)
    monkeypatch.setattr(seo_checks, 'PUBLISH_ROOT', root)
    monkeypatch.setattr(seo_checks, 'V2_ROOT', tmp_path / 'platform_v2')
    page.write_text('<link rel="canonical" href="https://sandro-abashishvili.de/Bitcoin-Live-Signals/portfolio/">')
    assert [f.issue for f in seo_checks.publish_canonical_findings([page])] == ['publish_canonical_mismatch']
    page.write_text('<link rel="canonical" href="https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/portfolio/">')
    assert seo_checks.publish_canonical_findings([page]) == []


def test_redirect_is_not_required_to_be_self_canonical(monkeypatch, tmp_path: Path):
    page = tmp_path / 'index.html'
    page.write_text('<meta http-equiv="refresh" content="0;url=/new/">')
    monkeypatch.setattr(seo_checks, 'PUBLISH_ROOT', tmp_path)
    assert seo_checks.publish_canonical_findings([page]) == []
