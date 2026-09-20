"""File: index_builder.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Rebuild the main V2 news page from generated daily news archive entries.
"""

from __future__ import annotations

from .card_media import render_card_media
from .source_policy import render_license

from datetime import datetime, timezone
import html
from pathlib import Path

from platform_v2.shared.frontend.components import (
    normalize_generated_html,
    render_content_hero,
    render_page_head,
    render_runtime_clock_script,
    render_site_footer,
    render_site_navigation,
)

from .config import V2NewsPipelineConfig
from .models import NewsItem
from .paths import news_index_html_path


class NewsIndexBuilder:
    """Build the main frontend news index from the current daily collection."""

    def build(
        self,
        day_iso: str,
        items: list[NewsItem],
        daily_archive_path: Path,
        config: V2NewsPipelineConfig,
        generated_at: str | None = None,
    ) -> Path:
        target_path = news_index_html_path(config)
        target_path.write_text(
            normalize_generated_html(self.render(day_iso, items, daily_archive_path, generated_at=generated_at)),
            encoding="utf-8",
        )
        return target_path

    def build_archive_index(
        self,
        *,
        latest_day_iso: str,
        latest_count: int,
        latest_sources: int,
        archive_dir: Path,
    ) -> Path:
        target_path = archive_dir / "index.html"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            normalize_generated_html(
                self.render_archive_index(
                    latest_day_iso=latest_day_iso,
                    latest_count=latest_count,
                    latest_sources=latest_sources,
                    archive_dir=archive_dir,
                )
            ),
            encoding="utf-8",
        )
        return target_path

    def render(self, day_iso: str, items: list[NewsItem], daily_archive_path: Path, *, generated_at: str | None = None) -> str:
        day_human = self._format_day(day_iso)
        generated_at = html.escape(generated_at or datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC"))
        archive_days = self._list_archive_days(daily_archive_path.parent)
        preview_cards = "\n".join(self._render_preview_card(item) for item in items) or self._render_empty_state()
        archive_links = "\n".join(self._render_archive_day_link(day) for day in archive_days[:8])
        latest_sources = len({item.source.strip() for item in items if item.source.strip()})
        description = (
            "Crypto and financial-market news covering exchanges, blockchain, funds, regulation and monetary policy, with dated headlines and original source links."
        )
        page_head = self._render_news_page_head(description)
        content_hero = self._render_news_content_hero()
        latest_panel = self._render_latest_batch_panel(preview_cards=preview_cards, generated_at=generated_at)
        archive_panel = self._render_recent_archive_panel(
            day_human=day_human,
            item_count=len(items),
            latest_sources=latest_sources,
            archive_days=archive_days,
            archive_links=archive_links,
        )
        return f"""<!DOCTYPE html>
<!-- ssh-generator: news.py.news_pipeline.index_builder.v2026-03-29a -->
<html lang="en">
  <head>
{page_head}
  </head>
  <body>
    <main class="page">
      <header class="page-chrome">
        {content_hero}
        {render_site_navigation(active_page="news")}
      </header>
      <section class="content-grid">
        {latest_panel}
        <article class="panel panel-wide news-support-panel calendar-panel">
          <h2>Economic calendar</h2>
          <p class="panel-intro">Upcoming inflation, employment and central-bank announcements — official schedules.</p>
          <div class="archive-day-grid">
            <a class="archive-day-card" href="https://www.bls.gov/schedule/" target="_blank" rel="noopener"><strong>Inflation &amp; employment</strong><span>BLS release calendar ↗</span></a>
            <a class="archive-day-card" href="https://www.bea.gov/news/schedule" target="_blank" rel="noopener"><strong>GDP &amp; personal income</strong><span>BEA release calendar ↗</span></a>
            <a class="archive-day-card" href="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm" target="_blank" rel="noopener"><strong>Federal Reserve meetings</strong><span>FOMC calendar ↗</span></a>
          </div>
        </article>
        {archive_panel}
      </section>
    </main>
    {render_site_footer(legal_prefix="../legal")}
    {render_runtime_clock_script()}
  </body>
</html>
"""

    @staticmethod
    def _render_news_content_hero() -> str:
        return render_content_hero(
            title="News And Context",
            href="../news/",
            intro="Exchanges, blockchain, funds, payments, security and the economic decisions shaping crypto — with original source links.",
            subline="Crypto and financial markets",
            note="",
            show_runtime=False,
        )

    @staticmethod
    def _render_news_page_head(description: str) -> str:
        return render_page_head(
            title="Bitcoin News And Market Context | SmartSignalHub",
            description=description,
            canonical_path="/news/index.html",
            css_href="./css/styles.css",
            og_type="website",
            schema_json_ld=f"""      {{
        "@context": "https://schema.org",
        "@graph": [
          {{
            "@type": "Organization",
            "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization",
            "name": "SmartSignalHub",
            "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/",
            "description": "Bitcoin market analysis, simulated spot and futures strategies, and curated financial news."
          }},
          {{
            "@type": "CollectionPage",
            "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/news/#collectionpage",
            "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/news/",
            "name": "Bitcoin News And Market Context | SmartSignalHub",
            "description": "{html.escape(description, quote=True)}",
            "isPartOf": {{
              "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization"
            }},
            "about": {{
              "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization"
            }}
          }}
        ]
      }}""",
        )

    @staticmethod
    def _render_latest_batch_panel(*, preview_cards: str, generated_at: str) -> str:
        return f"""
        <article class="panel panel-wide news-latest-panel">
          <p class="panel-intro">Updated: {generated_at}</p>
          <div class="news-grid">
            {preview_cards}
          </div>
        </article>"""

    def _render_recent_archive_panel(
        self,
        *,
        day_human: str,
        item_count: int,
        latest_sources: int,
        archive_days: list[str],
        archive_links: str,
    ) -> str:
        archive_cards = archive_links or self._render_archive_empty_state()
        return f"""
        <article class="panel panel-wide archive-panel news-support-panel">
          <div class="news-support-heading"><h2>Recent editions</h2><a class="news-archive-link" href="./archive/">View all editions →</a></div>
          <p class="panel-intro">Browse news from previous days.</p>
          <div class="archive-day-grid">
            {archive_cards}
          </div>
        </article>"""

    def _render_preview_card(self, item: NewsItem) -> str:
        image_html = render_card_media(
            title=item.title,
            link=item.link,
            source=item.source,
            image_path=item.image_local,
            asset_prefix="../",
        )
        return f"""
<article class="news-card news-card-compact">
  {image_html}
  <div class="news-card-body">
    <p class="news-card-meta">{html.escape(item.date_human)} · {html.escape(item.source)}</p>
    <h3 class="news-card-title">
      <a href="{html.escape(item.link, quote=True)}" target="_blank" rel="noopener">{html.escape(item.title)}</a>
    </h3>
    {render_license(item.source, "./")}
  </div>
</article>""".strip()

    def render_archive_index(
        self,
        *,
        latest_day_iso: str,
        latest_count: int,
        latest_sources: int,
        archive_dir: Path,
    ) -> str:
        latest_day_human = self._format_day(latest_day_iso)
        generated_at = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
        archive_days = self._list_archive_days(archive_dir)
        archive_links = "\n".join(self._render_archive_day_link(day, base_prefix=".") for day in archive_days) or self._render_archive_empty_state()
        description = (
            "Browse archived SmartSignalHub Bitcoin news batches, market context updates, and daily headline collections organized by date."
        )
        return f"""<!DOCTYPE html>
<!-- ssh-generator: news.py.news_pipeline.index_builder.v2026-03-31a -->
<html lang="en">
  <head>
{render_page_head(
    title="News Archive Index | SmartSignalHub",
    description=description,
    canonical_path="/news/archive/index.html",
    css_href="../css/styles.css",
    favicon_prefix="../../",
)}
  </head>
  <body>
    <main class="page">
      <header class="page-chrome">
        {render_content_hero(
            title="News Archive Index",
            href="../archive/",
            intro="Daily archive access for older SmartSignalHub news batches.",
            note="",
            show_runtime=False,
        )}
        {render_site_navigation(active_page="news", base_prefix="../..")}
      </header>
      <section class="content-grid">
        <article class="panel panel-wide archive-panel">
          <div class="panel-head"><h2>All Archive Days</h2></div>
          <p class="panel-intro">Latest day: {latest_day_human} · Stories: {latest_count} · Sources: {latest_sources} · Archive Days: {len(archive_days)} · <a class="inline-link" href="../">Back to News</a></p>
          <div class="archive-day-grid">
            {archive_links}
          </div>
        </article>
      </section>
    </main>
    {render_site_footer(legal_prefix="../../legal")}
    {render_runtime_clock_script()}
  </body>
</html>
"""

    def _render_empty_state(self) -> str:
        return """
<article class="news-card news-card-empty">
  <div class="news-card-body">
    <h3 class="news-card-title">No fresh stories</h3>
    <p class="news-card-summary">No eligible stories were found in the last 48 hours. Earlier editions remain in the archive.</p>
  </div>
</article>""".strip()

    @staticmethod
    def _render_archive_empty_state() -> str:
        return """
<div class="news-card news-card-empty">
  <div class="news-card-body">
    <h3 class="news-card-title">No Archive Days Yet</h3>
    <p class="news-card-summary">Generate the first news batch to unlock daily archive pages here.</p>
  </div>
</div>""".strip()

    @staticmethod
    def _list_archive_days(archive_dir: Path) -> list[str]:
        if not archive_dir.exists():
            return []
        day_files = sorted(
            (path.stem for path in archive_dir.glob("*.html") if path.is_file()),
            reverse=True,
        )
        return [day_iso for day_iso in day_files if day_iso and day_iso != "index"]

    def _render_archive_day_link(self, day_iso: str, *, base_prefix: str = "./archive") -> str:
        label = self._format_day(day_iso)
        return f"""
<a class="archive-day-card" href="{base_prefix}/{day_iso}.html">
  <span>Open Daily Archive</span>
  <strong>{label}</strong>
</a>""".strip()

    def _format_day(self, day_iso: str) -> str:
        try:
            return datetime.strptime(day_iso, "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
        except ValueError:
            return day_iso
