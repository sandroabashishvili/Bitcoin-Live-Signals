from __future__ import annotations

from platform_v2.tools.github_publish_system.sync import rewrite_links_for_github_pages


def test_publish_link_rewrite_does_not_change_analytics_id(tmp_path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<script data-measurement-id="G-FUTURE123"></script>',
        encoding="utf-8",
    )

    rewrite_links_for_github_pages(pages_repo=tmp_path, dry_run=False)

    rendered = page.read_text(encoding="utf-8")
    assert 'data-measurement-id="G-FUTURE123"' in rendered
