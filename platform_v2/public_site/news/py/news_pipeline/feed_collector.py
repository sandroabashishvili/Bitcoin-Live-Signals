"""File: feed_collector.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Collect and normalize crypto news items for the V2 frontend-owned news pipeline.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import html
import logging
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser

from .models import NewsItem
from .http_client import fetch_text
from .utils import clean_html


logger = logging.getLogger(__name__)

from .source_policy import SOURCE_POLICIES, permits_entry

NEWS_SOURCES = {name: policy.feed_url for name, policy in SOURCE_POLICIES.items() if policy.enabled}
NEWS_WINDOW_HOURS = 48
PREFERRED_ITEMS_PER_SOURCE = 4
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_NAMES = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "rss"}
BLOCKED_TITLE_FRAGMENTS = (
    "price prediction",
    "live price",
    "calculator",
    "convert ",
    " to usd",
    " to eur",
    " to gbp",
    " to try",
    "best crypto",
    "how to buy",
    "sponsored",
    "promotion",
    "promo",
    "press release",
    "partner content",
    "guest post",
)
MIN_TITLE_LENGTH = 28


def pick_first_img_from_html(article_html: str, base_url: str) -> str | None:
    """Extract the first meaningful image URL from article HTML."""

    meta_patterns = [
        r'<meta[^>]+property=["\']og:image:secure_url["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ]

    for pattern in meta_patterns:
        match = re.search(pattern, article_html, re.I)
        if not match:
            continue
        candidate = html.unescape(match.group(1).strip())
        if candidate.startswith("//"):
            return "https:" + candidate
        if candidate.startswith("/"):
            return urljoin(base_url, candidate)
        if candidate.startswith("http"):
            return candidate

    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        article_html,
        re.I | re.S,
    ):
        block = match.group(1)
        json_ld_match = re.search(r'"image"\s*:\s*(\[.*?\]|".*?")', block, re.I | re.S)
        if not json_ld_match:
            continue
        image_match = re.search(r'https?://[^"\]\s]+', json_ld_match.group(1))
        if image_match:
            return image_match.group(0)

    image_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', article_html, re.I)
    for image_url in image_urls:
        candidate = image_url.strip()
        if not candidate:
            continue
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        elif candidate.startswith("/"):
            candidate = urljoin(base_url, candidate)
        elif not candidate.startswith("http"):
            candidate = urljoin(base_url, candidate)

        lower_candidate = candidate.lower()
        if any(fragment in lower_candidate for fragment in ("sprite", "logo", "icon", "avatar", "blank", "placeholder", "data:image")):
            continue
        return candidate

    return None


def resolve_image_candidates(entry: Any) -> list[str]:
    """Resolve ordered image candidates from feed metadata or article HTML."""

    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(url: str | None) -> None:
        normalized_url = (url or "").strip()
        if not normalized_url.startswith("http"):
            return
        if normalized_url in seen:
            return
        seen.add(normalized_url)
        candidates.append(normalized_url)

    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list):
        for media_item in media:
            if isinstance(media_item, dict):
                add_candidate(str(media_item.get("url") or ""))

    for enclosure in getattr(entry, "enclosures", []) or []:
        if isinstance(enclosure, dict):
            add_candidate(str(enclosure.get("href") or enclosure.get("url") or ""))

    article_link = str(entry.get("link") or "").strip()
    if article_link.startswith("http"):
        article_html = fetch_text(article_link)
        add_candidate(pick_first_img_from_html(article_html, article_link))

    return candidates


def _extract_publication_datetime(entry: Any) -> datetime | None:
    """Extract publication datetime from a feed entry."""

    published_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not published_struct:
        return None
    return datetime(*published_struct[:6], tzinfo=timezone.utc)


def _clean_title(title: str) -> str:
    cleaned_title = html.unescape(title or "")
    cleaned_title = re.sub(r"\s+", " ", cleaned_title).strip()
    return cleaned_title.replace("’", "'")


def _is_quality_title(title: str) -> bool:
    normalized_title = title.lower().strip()
    if len(normalized_title) < MIN_TITLE_LENGTH:
        return False
    if normalized_title.count("|") >= 2:
        return False
    if normalized_title.count(" - ") >= 3:
        return False
    return not any(fragment in normalized_title for fragment in BLOCKED_TITLE_FRAGMENTS)


def _clean_article_link(link: str) -> str:
    """Remove tracking parameters from article URLs."""

    if not link.startswith("http"):
        return link

    split_result = urlsplit(link)
    kept_query_items: list[tuple[str, str]] = []
    for key, value in parse_qsl(split_result.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key.startswith(TRACKING_QUERY_PREFIXES):
            continue
        if lower_key in TRACKING_QUERY_NAMES:
            continue
        kept_query_items.append((key, value))

    return urlunsplit(
        (
            split_result.scheme,
            split_result.netloc,
            split_result.path,
            urlencode(kept_query_items, doseq=True),
            "",
        )
    )


def _normalize_feed_item(entry: Any, source_name: str, *, resolve_images: bool = True) -> NewsItem | None:
    """Convert a feed entry into normalized news item data."""

    publication_time = _extract_publication_datetime(entry)
    if not publication_time:
        return None

    raw_title = entry.get("title") or "Untitled"
    title_value = raw_title[0] if isinstance(raw_title, list) and raw_title else raw_title
    title = _clean_title(str(title_value).strip())
    if not _is_quality_title(title):
        return None

    raw_link = entry.get("link") or "#"
    link_value = raw_link[0] if isinstance(raw_link, list) and raw_link else raw_link
    link = _clean_article_link(str(link_value).strip())

    summary_raw = entry.get("summary") or entry.get("description") or title
    # Remove only the RSS syndication footer; attribution remains in every card.
    if source_name == "Cryptonews":
        summary_raw = re.sub(r"<p>The post .*? appeared first on .*?</p>\s*$", "", str(summary_raw), flags=re.S | re.I)
    summary = clean_html(str(summary_raw)).strip() or title
    image_candidates = resolve_image_candidates(entry) if resolve_images else []

    return NewsItem(
        title=title,
        link=link,
        summary=summary,
        image=image_candidates[0] if image_candidates else None,
        image_candidates=image_candidates,
        source=source_name,
        date=publication_time.strftime("%Y-%m-%d"),
        date_human=publication_time.strftime("%b %d, %Y").replace(" 0", " "),
        pub_ts=int(publication_time.timestamp()),
    )


def _interleave_sources(sorted_items: list[NewsItem], target_count: int) -> list[NewsItem]:
    """Reorder items to reduce long same-source streaks."""

    source_buckets: dict[str, list[NewsItem]] = defaultdict(list)
    source_order: list[str] = []

    for item in sorted_items:
        if item.source not in source_buckets:
            source_order.append(item.source)
        source_buckets[item.source].append(item)

    diversified_items: list[NewsItem] = []
    while len(diversified_items) < target_count and any(
        sum(i.source == name for i in diversified_items) < PREFERRED_ITEMS_PER_SOURCE and source_buckets[name]
        for name in source_order
    ):
        appended_any = False
        for source_name in source_order:
            bucket = source_buckets[source_name]
            if not bucket or sum(i.source == source_name for i in diversified_items) >= PREFERRED_ITEMS_PER_SOURCE:
                continue
            diversified_items.append(bucket.pop(0))
            appended_any = True
            if len(diversified_items) >= target_count:
                break
        if not appended_any:
            break

    remaining = sorted((item for bucket in source_buckets.values() for item in bucket),
                       key=lambda item: item.pub_ts, reverse=True)
    diversified_items.extend(remaining[:max(0, target_count - len(diversified_items))])
    return diversified_items


def collect_top_news(target_count: int = 12, *, resolve_images: bool = False, enforce_source_policy: bool = False, diagnostics: dict | None = None) -> list[NewsItem]:
    """Fetch each feed once; select/deduplicate before article image requests."""
    if target_count <= 0:
        return []
    now = datetime.now(tz=timezone.utc)
    oldest = now - timedelta(hours=NEWS_WINDOW_HOURS)
    candidates: list[tuple[NewsItem, Any]] = []
    usable_feeds = 0
    report = diagnostics if diagnostics is not None else {}
    report.update(collected_at=now.isoformat(), window_hours=NEWS_WINDOW_HOURS, feeds=[])
    feeds = list(NEWS_SOURCES.items())
    if enforce_source_policy:
        from .source_policy import validate_sources
        validate_sources(NEWS_SOURCES)
        feeds += [(name, url) for name in NEWS_SOURCES for url in SOURCE_POLICIES[name].additional_feed_urls]
    for source_name, feed_url in feeds:
        stats = {"source": source_name, "url": feed_url, "status": "failed", "entries": 0,
                 "within_24h": 0, "within_window": 0, "eligible": 0, "rejected": Counter()}
        report["feeds"].append(stats)
        # Use the same explicit HTTP timeout as article requests.
        raw_feed = fetch_text(feed_url)
        if not raw_feed:
            logger.warning("No feed content from %s", source_name)
            continue
        feed = feedparser.parse(raw_feed)
        if getattr(feed, "bozo", False):
            logger.warning("Feed parse warning for %s: %s", source_name,
                           getattr(feed, "bozo_exception", None))
            # Some valid entries survive a recoverable feed parser warning.
        if feed.entries or (not getattr(feed, "bozo", False) and getattr(feed, "version", "")):
            usable_feeds += 1
            stats["status"] = "ok"
        stats["entries"] = len(feed.entries)
        for entry in feed.entries:
            try:
                published = _extract_publication_datetime(entry)
                if not published:
                    stats["rejected"]["missing_date"] += 1
                    continue
                if published > now + timedelta(minutes=5):
                    stats["rejected"]["future_date"] += 1
                    continue
                if published < oldest:
                    stats["rejected"]["older_than_window"] += 1
                    continue
                stats["within_window"] += 1
                if published >= now - timedelta(hours=24):
                    stats["within_24h"] += 1
                item = _normalize_feed_item(entry, source_name, resolve_images=False)
            except (ValueError, TypeError, OverflowError):
                stats["rejected"]["invalid_entry"] += 1
                logger.warning("Invalid feed entry skipped from %s", source_name)
                continue
            if item is None:
                stats["rejected"]["title_filter"] += 1
                continue
            parsed = urlsplit(item.link)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                stats["rejected"]["invalid_link"] += 1
                continue
            if enforce_source_policy:
                policy = SOURCE_POLICIES.get(source_name)
                if policy is None or feed_url not in (policy.feed_url, *policy.additional_feed_urls) or not policy.allows_link(item.link):
                    stats["rejected"]["unreviewed_link"] += 1
                    continue
                if not permits_entry(source_name, item.title, item.summary, entry):
                    stats["rejected"]["topic_author_or_category"] += 1
                    continue
                # Honor explicit exceptions rather than treating public-domain as universal.
                notice = str(entry.get("rights", "")) + str(entry.get("copyright", ""))
                if notice.strip():
                    stats["rejected"]["separate_rights"] += 1
                    logger.warning("Entry with separate rights notice skipped: %s", item.link)
                    continue
                item = replace(item, summary=(item.summary[:600] if policy.allow_summary else ""), license_url=("https://sandro-abashishvili.de/Bitcoin-Live-Signals/news/" + policy.license_path) if policy.license_path else None)
            stats["eligible"] += 1
            candidates.append((item, entry))

    if not usable_feeds:
        raise RuntimeError("No usable feeds returned; collection failed, not an empty news day.")

    candidates.sort(key=lambda pair: pair[0].pub_ts, reverse=True)
    unique: list[NewsItem] = []
    entries: dict[str, Any] = {}
    seen_titles: set[str] = set()
    seen_links: set[str] = set()
    for item, entry in candidates:
        title_key = " ".join(re.findall(r"\w+", item.title.casefold()))
        parsed = urlsplit(item.link)
        # Host names are insensitive; URL paths and query values are not.
        link_key = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))
        if title_key in seen_titles or link_key in seen_links:
            continue
        seen_titles.add(title_key)
        seen_links.add(link_key)
        unique.append(item)
        entries[item.link] = entry

    selected = _interleave_sources(unique, target_count)
    report["eligible_by_source"] = dict(Counter(i.source for i, _ in candidates))
    report["unique_by_source"] = dict(Counter(i.source for i in unique))
    report["selected_by_source"] = dict(Counter(i.source for i in selected))
    result = []
    for item in selected:
        images_allowed = resolve_images and (not enforce_source_policy or SOURCE_POLICIES[item.source].allow_images)
        images = resolve_image_candidates(entries[item.link]) if images_allowed else []
        result.append(replace(item, image_candidates=images, image=images[0] if images else None))
    logger.info("News selection: candidates=%d unique=%d selected=%d lookback_hours=%d",
                len(candidates), len(unique), len(result), NEWS_WINDOW_HOURS)
    return result
