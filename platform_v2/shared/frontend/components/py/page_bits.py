"""Shared page head and hero helpers for static frontend builders."""

from __future__ import annotations

import html
from datetime import datetime

from .runtime_clock import render_runtime_clock_strip
from .site_config import GA_MEASUREMENT_ID
from platform_v2.shared.backend.runtime_store.spot import load_latest_document

_SITE_ROOT = "https://sandro-abashishvili.de/Bitcoin-Live-Signals"
_DEFAULT_SOCIAL_IMAGE = f"{_SITE_ROOT}/assets/site-social-og.png"
_SOCIAL_IMAGE_WIDTH = "1200"
_SOCIAL_IMAGE_HEIGHT = "630"
_SOCIAL_IMAGE_TYPE = "image/png"


def normalize_generated_html(value: str) -> str:
    """Remove generator-only trailing whitespace and keep one final newline."""
    return "\n".join(line.rstrip() for line in value.splitlines()).strip() + "\n"


def _clean_path(value: str) -> str:
    return value.replace("/index.html", "/")


def _clean_href(value: str) -> str:
    return value.replace("/index.html", "/")


def _load_latest_runtime_meta() -> tuple[str, str]:
    payload: object = load_latest_document("metrics")
    if not isinstance(payload, dict):
        return "—", "—"

    strategy_start = _format_strategy_start(payload.get("strategy_start"))
    elapsed = _format_elapsed(payload.get("elapsed"))
    return strategy_start, elapsed


def _format_strategy_start(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "—":
        return "—"
    for pattern in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.strftime("%Y-%m-%d UTC")
        except ValueError:
            continue
    return text


def _format_elapsed(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "—":
        return "—"
    if "," in text:
        days_part, remainder = text.split(",", 1)
        days_text = days_part.strip()
        time_text = remainder.strip().split(":", 2)
        if len(time_text) >= 2:
            hours_minutes = f"{time_text[0]}:{time_text[1]}"
            if days_text:
                return f"{days_text}, {hours_minutes}"
        return days_text or text
    return text


def _render_runtime_meta() -> str:
    strategy_start, elapsed = _load_latest_runtime_meta()
    return f"""
                <div class="hero-runtime-meta" aria-label="Strategy lifecycle">
                  <span class="hero-runtime-meta-item">
                    <span class="hero-runtime-meta-label">Strategy Start</span>
                    <strong class="hero-runtime-meta-value">{html.escape(strategy_start)}</strong>
                  </span>
                  <span class="hero-runtime-meta-item">
                    <span class="hero-runtime-meta-label">Elapsed</span>
                    <strong class="hero-runtime-meta-value">{html.escape(elapsed)}</strong>
                  </span>
                </div>"""


def render_page_head(
    *,
    title: str,
    description: str,
    canonical_path: str,
    css_href: str,
    extra_css_hrefs: tuple[str, ...] = (),
    favicon_prefix: str = "../",
    og_title: str | None = None,
    og_description: str | None = None,
    twitter_title: str | None = None,
    twitter_description: str | None = None,
    social_image_url: str | None = None,
    og_type: str = "website",
    twitter_card: str = "summary_large_image",
    schema_json_ld: str | None = None,
) -> str:
    canonical_url = f"{_SITE_ROOT}{_clean_path(canonical_path)}"
    resolved_og_title = og_title or title
    resolved_og_description = og_description or description
    resolved_twitter_title = twitter_title or resolved_og_title
    resolved_twitter_description = twitter_description or description
    resolved_social_image = social_image_url or _DEFAULT_SOCIAL_IMAGE
    schema_block = (
        f'\n    <script type="application/ld+json">\n{schema_json_ld}\n    </script>'
        if schema_json_ld
        else ""
    )
    extra_css = "".join(
        f'\n    <link rel="stylesheet" href="{html.escape(href, quote=True)}" />'
        for href in extra_css_hrefs
    )
    analytics_script = (
        f'\n    <script src="/Bitcoin-Live-Signals/shared/components/js/analytics-consent.js" '
        f'defer data-measurement-id="{GA_MEASUREMENT_ID}"></script>'
    )
    return f"""    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(title)}</title>
    <meta name="description" content="{html.escape(description, quote=True)}" />
    <meta name="robots" content="index,follow,max-image-preview:large" />
    <link rel="canonical" href="{html.escape(canonical_url, quote=True)}" />
    <meta name="theme-color" content="#09111a" />
    <meta property="og:site_name" content="SmartSignalHub" />
    <meta property="og:title" content="{html.escape(resolved_og_title, quote=True)}" />
    <meta property="og:description" content="{html.escape(resolved_og_description, quote=True)}" />
    <meta property="og:type" content="{html.escape(og_type, quote=True)}" />
    <meta property="og:url" content="{html.escape(canonical_url, quote=True)}" />
    <meta property="og:image" content="{html.escape(resolved_social_image, quote=True)}" />
    <meta property="og:image:secure_url" content="{html.escape(resolved_social_image, quote=True)}" />
    <meta property="og:image:alt" content="SmartSignalHub social preview" />
    <meta property="og:image:type" content="{_SOCIAL_IMAGE_TYPE}" />
    <meta property="og:image:width" content="{_SOCIAL_IMAGE_WIDTH}" />
    <meta property="og:image:height" content="{_SOCIAL_IMAGE_HEIGHT}" />
    <meta name="twitter:card" content="{html.escape(twitter_card, quote=True)}" />
    <meta name="twitter:title" content="{html.escape(resolved_twitter_title, quote=True)}" />
    <meta name="twitter:description" content="{html.escape(resolved_twitter_description, quote=True)}" />{schema_block}
    <meta name="twitter:image" content="{html.escape(resolved_social_image, quote=True)}" />
    <meta name="twitter:image:alt" content="SmartSignalHub social preview" />
{analytics_script}
    <link rel="icon" type="image/png" href="{html.escape(favicon_prefix, quote=True)}assets/site-favicon.png" />
    <link rel="icon" type="image/x-icon" href="{html.escape(favicon_prefix, quote=True)}assets/site-favicon.ico" />
    <link rel="stylesheet" href="{html.escape(css_href, quote=True)}" />{extra_css}"""


def render_content_hero(
    *,
    title: str,
    href: str,
    intro: str,
    subline: str | None = None,
    note: str = "Educational use only. Not financial advice.",
    hero_id: str | None = None,
    show_runtime: bool = True,
    show_subnav_toggle: bool | None = None,
    runtime_meta_html: str | None = None,
) -> str:
    id_attr = f' aria-labelledby="{html.escape(hero_id)}"' if hero_id else ""
    heading_id = f' id="{html.escape(hero_id)}"' if hero_id else ""
    resolved_subline = subline
    if resolved_subline is None and show_runtime:
        resolved_subline = "Mode: simulation | Spot Market"
    subline_html = (
        f'\n            <p class="hero-subline">{html.escape(resolved_subline)}</p>'
        if resolved_subline
        else ""
    )
    intro_html = (
        f'\n                  <p class="hero-intro">{html.escape(intro)}</p>'
        if intro
        else ""
    )
    note_html = (
        f'\n                    <p class="hero-note">{html.escape(note)}</p>'
        if note
        else ""
    )
    kicker_html = (
        f"""
                  <div class="hero-kicker">
                    {subline_html}
                    {note_html}
                  </div>"""
        if subline_html or note_html
        else ""
    )
    runtime_html = (
        f"""
                <div class="hero-runtime">
                  {render_runtime_clock_strip()}
                  {runtime_meta_html if runtime_meta_html is not None else _render_runtime_meta()}
                </div>"""
        if show_runtime
        else ""
    )
    resolved_show_subnav_toggle = show_runtime if show_subnav_toggle is None else show_subnav_toggle
    subnav_toggle_html = (
        '\n                  <button class="subnav-toggle" type="button" data-subnav-toggle aria-expanded="false" aria-label="Open navigation menu">☰</button>'
        if resolved_show_subnav_toggle
        else ""
    )
    compact_class = "" if show_runtime else " hero-content-compact"
    rendered = f"""
        <section class="hero hero-content{compact_class}"{id_attr}>
          <div>
            <div class="hero-body-row">
              <div class="hero-copy">
                <div class="hero-main">
                  {kicker_html}
                  {subnav_toggle_html}
                  <div class="hero-title-row">
                    <h1{heading_id}><a class="hero-title-link" href="{html.escape(_clean_href(href), quote=True)}">{html.escape(title)}</a></h1>
                  </div>
                  {intro_html}
                </div>
                {runtime_html}
              </div>
            </div>
          </div>
        </section>"""
    return "\n".join(line.rstrip() for line in rendered.splitlines())


def render_runtime_hero(
    *,
    title: str,
    href: str,
    intro: str,
    subline: str | None = None,
    note: str = "Educational use only. Not financial advice.",
) -> str:
    return render_content_hero(
        title=title,
        href=href,
        intro=intro,
        subline=subline,
        note=note,
    )
