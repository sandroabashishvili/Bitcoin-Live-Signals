"""File: daily_page_builder.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Build the daily V2 news archive page from normalized news items.
"""

from __future__ import annotations

from .card_media import render_card_media
from .source_policy import render_license

from dataclasses import replace
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

from .source_policy import SOURCE_POLICIES
from .config import V2NewsPipelineConfig
from .image_processor import download_and_resize
from .models import NewsItem
from .paths import daily_news_assets_dir, daily_news_html_path, news_frontend_dir
from .utils import safe_name


class DailyNewsPageBuilder:
    """Build one daily news archive page inside the V2 frontend tree."""

    def build(
        self,
        items: list[NewsItem],
        day_iso: str,
        config: V2NewsPipelineConfig,
    ) -> tuple[Path, list[NewsItem]]:
        render_ready_items = self._prepare_items(items, day_iso, config)
        target_path = daily_news_html_path(config, day_iso)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            normalize_generated_html(self.render(render_ready_items, day_iso)),
            encoding="utf-8",
        )
        return target_path, render_ready_items

    def _prepare_items(
        self,
        items: list[NewsItem],
        day_iso: str,
        config: V2NewsPipelineConfig,
    ) -> list[NewsItem]:
        prepared: list[NewsItem] = []

        for item in items:
            policy = SOURCE_POLICIES.get(item.source)
            if not (config.reuse_publisher_summaries and policy and policy.allow_summary and policy.allows_link(item.link)):
                item = replace(item, summary="")
            if not (config.reuse_publisher_images and policy and policy.allow_images and policy.allows_link(item.link)):
                # Clearing cached paths matters: download_images=False alone
                # still used to display previously downloaded publisher photos.
                item = replace(item, image=None, image_local=None, image_candidates=[])
            image_info = self._resolve_image_info(item, day_iso, config)
            if image_info is None:
                prepared.append(item)
            else:
                prepared.append(
                    replace(
                        item,
                        image=str(image_info["src_jpg"]),
                        image_local=str(image_info["src_jpg"]),
                    )
                )

            if len(prepared) >= config.max_news_items:
                break

        return prepared

    def _resolve_image_info(
        self,
        item: NewsItem,
        day_iso: str,
        config: V2NewsPipelineConfig,
    ) -> dict[str, object] | None:
        for candidate_url in item.image_candidates:
            cached_info = self._cached_image_info(candidate_url, day_iso, config)
            if cached_info is not None:
                return cached_info

        for candidate_url in item.image_candidates:
            if not config.download_images:
                break
            image_info = download_and_resize(candidate_url, day_iso, config)
            if image_info:
                return image_info

        return None

    def _cached_image_info(
        self,
        image_url: str,
        day_iso: str,
        config: V2NewsPipelineConfig,
    ) -> dict[str, object] | None:
        asset_dir = daily_news_assets_dir(config, day_iso)
        base_path = asset_dir / f"{safe_name(image_url)}_base.jpg"
        thumb_path = asset_dir / f"{safe_name(image_url)}_thumb.jpg"
        if not base_path.exists():
            return None

        frontend_root = news_frontend_dir(config).parent
        base_web_path = f"../{base_path.relative_to(frontend_root).as_posix()}"
        if thumb_path.exists():
            thumb_web_path = f"../{thumb_path.relative_to(frontend_root).as_posix()}"
            srcset = f"{thumb_web_path} {config.thumb_width}w, {base_web_path} {config.max_image_width}w"
        else:
            srcset = base_web_path

        return {
            "src_jpg": base_web_path,
            "srcset_jpg": srcset,
            "width": config.max_image_width,
            "height": 0,
            "thumb_width": config.thumb_width,
            "thumb_height": 0,
        }

    def render(self, items: list[NewsItem], day_iso: str) -> str:
        day_human = self._format_day(day_iso)
        generated_at = datetime.now(tz=timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
        cards_html = "\n".join(self._render_card(item) for item in items) or self._render_empty_state()
        description = (
            f"Bitcoin technology, digital-asset regulation and monetary-policy news highlights for {day_human}, with curated headlines, source links, and local V2 archive pages."
        )
        return f"""<!DOCTYPE html>
<!-- ssh-generator: news.py.news_pipeline.daily_page_builder.v2026-03-29a -->
<html lang="en">
  <head>
{render_page_head(
    title=f"Bitcoin News Highlights | {day_human} | SmartSignalHub",
    description=description,
    canonical_path=f"/news/archive/{day_iso}.html",
    css_href="../css/styles.css",
    favicon_prefix="../../",
    twitter_card="summary_large_image",
)}
  </head>
  <body>
    <main class="page">
      <section class="hero">
        {render_content_hero(
            title="Daily News Archive",
            href=f"./{day_iso}.html",
            intro=f"Curated Bitcoin and crypto headlines for {day_human}, stored as static V2 archive content.",
            note="",
            show_runtime=False,
        )}
      </section>
      {render_site_navigation(active_page="news", base_prefix="../..")}
      <section class="content-grid">
        <article class="panel panel-wide">
          <div class="panel-head"><h2>{day_human}</h2></div>
          <p class="panel-intro">Official source excerpts with publication dates and original links. No affiliation or endorsement.</p>
          <div class="news-grid">
            {cards_html}
          </div>
        </article>
      </section>
    </main>
    {render_site_footer(legal_prefix="../../legal")}
    {render_runtime_clock_script()}
  </body>
</html>
"""

    def _render_card(self, item: NewsItem) -> str:
        image_html = render_card_media(
            title=item.title,
            link=item.link,
            source=item.source,
            image_path=item.image_local,
            asset_prefix="../../",
        )

        return f"""
<article class="news-card">
  {image_html}
  <div class="news-card-body">
    <p class="news-card-meta">{html.escape(item.date_human)} · {html.escape(item.source)}</p>
    <h3 class="news-card-title">
      <a href="{html.escape(item.link, quote=True)}" target="_blank" rel="noopener">{html.escape(item.title)}</a>
    </h3>
    {render_license(item.source, "../")}
  </div>
</article>""".strip()

    def _render_empty_state(self) -> str:
        return """
<article class="news-card news-card-empty">
  <div class="news-card-body">
    <h3 class="news-card-title">No fresh stories</h3>
    <p class="news-card-summary">No eligible stories were found in the 48 hours preceding this collection.</p>
  </div>
</article>""".strip()

    def _format_day(self, day_iso: str) -> str:
        try:
            return datetime.strptime(day_iso, "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
        except ValueError:
            return day_iso
