"""SEO-focused diagnostics checks for generated frontend pages."""

from __future__ import annotations

import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


FRONTEND_ROOT = V2_ROOT / "public_site"
PUBLISH_ROOT = V2_ROOT.parent / "publish" / "Bitcoin-Live-Signals"
TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_DESCRIPTION_PATTERN = re.compile(
    r'<meta\s+name="description"\s+content="([^"]*)"',
    re.IGNORECASE,
)
ROBOTS_META_PATTERN = re.compile(
    r'<meta\s+name="robots"\s+content="([^"]*)"',
    re.IGNORECASE,
)
CANONICAL_PATTERN = re.compile(
    r'<link\s+rel="canonical"\s+href="([^"]+)"',
    re.IGNORECASE,
)
OG_PATTERNS = {
    "og:title": re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"', re.IGNORECASE),
    "og:description": re.compile(r'<meta\s+property="og:description"\s+content="([^"]*)"', re.IGNORECASE),
    "og:url": re.compile(r'<meta\s+property="og:url"\s+content="([^"]*)"', re.IGNORECASE),
    "og:image": re.compile(r'<meta\s+property="og:image"\s+content="([^"]*)"', re.IGNORECASE),
}
TWITTER_PATTERNS = {
    "twitter:card": re.compile(r'<meta\s+name="twitter:card"\s+content="([^"]*)"', re.IGNORECASE),
    "twitter:title": re.compile(r'<meta\s+name="twitter:title"\s+content="([^"]*)"', re.IGNORECASE),
    "twitter:description": re.compile(r'<meta\s+name="twitter:description"\s+content="([^"]*)"', re.IGNORECASE),
    "twitter:image": re.compile(r'<meta\s+name="twitter:image"\s+content="([^"]*)"', re.IGNORECASE),
}
SITE_ROOT = "https://sandro-abashishvili.de/Bitcoin-Live-Signals"
SCHEMA_PATTERN = re.compile(r'<script\s+type="application/ld\+json">', re.IGNORECASE)
SITEMAP_LOC_PATTERN = re.compile(r"<loc>(.*?)</loc>", re.IGNORECASE)
TITLE_MIN_LEN = 20
TITLE_MAX_LEN = 65
DESCRIPTION_MIN_LEN = 70
DESCRIPTION_MAX_LEN = 170


def seo_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    html_pages = sorted(FRONTEND_ROOT.rglob("*.html"))

    findings.extend(site_file_findings())
    findings.extend(page_meta_findings(html_pages))
    findings.extend(duplicate_meta_findings(html_pages))
    findings.extend(meta_length_findings(html_pages))
    findings.extend(schema_findings(html_pages))
    findings.extend(sitemap_coverage_findings(html_pages))
    findings.extend(publish_site_findings())
    return findings


def site_file_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    robots_path = FRONTEND_ROOT / "robots.txt"
    sitemap_path = FRONTEND_ROOT / "sitemap.xml"

    if not robots_path.exists():
        add_finding(findings, "platform_v2/public_site", "missing_robots_txt", "robots.txt", "medium")
    if not sitemap_path.exists():
        add_finding(findings, "platform_v2/public_site", "missing_sitemap_xml", "sitemap.xml", "medium")

    return findings


def page_meta_findings(html_pages: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    for html_path in html_pages:
        text = html_path.read_text(encoding="utf-8")
        path_str = str(html_path.relative_to(V2_ROOT.parent))
        is_404_page = html_path.name == "404.html"
        is_redirect_page = '<meta http-equiv="refresh"' in text.lower()

        canonical = extract_first(CANONICAL_PATTERN, text)
        if not canonical and not is_404_page and not is_redirect_page:
            add_finding(findings, path_str, "missing_canonical_link", "missing canonical link", "medium")
        elif canonical and not is_redirect_page:
            expected = expected_canonical_url(html_path)
            if expected and canonical != expected:
                add_finding(findings, path_str, "canonical_mismatch", canonical, "medium")

        if not is_404_page and not is_redirect_page:
            missing_og = [name for name, pattern in OG_PATTERNS.items() if not extract_first(pattern, text)]
            if missing_og:
                add_finding(findings, path_str, "missing_og_core_tags", ", ".join(missing_og), "medium")

            missing_twitter = [name for name, pattern in TWITTER_PATTERNS.items() if not extract_first(pattern, text)]
            if missing_twitter:
                add_finding(findings, path_str, "missing_twitter_card_tags", ", ".join(missing_twitter), "medium")

        robots = (extract_first(ROBOTS_META_PATTERN, text) or "").lower()
        if "noindex" in robots and not is_404_page and not is_redirect_page:
            add_finding(findings, path_str, "has_noindex_meta", robots, "high")

    return findings


def duplicate_meta_findings(html_pages: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    titles: defaultdict[str, list[str]] = defaultdict(list)
    descriptions: defaultdict[str, list[str]] = defaultdict(list)

    for html_path in html_pages:
        if html_path.name == "404.html":
            continue
        text = html_path.read_text(encoding="utf-8")
        if '<meta http-equiv="refresh"' in text.lower():
            continue
        path_str = str(html_path.relative_to(V2_ROOT.parent))

        title = normalize_meta_value(extract_first(TITLE_PATTERN, text))
        description = normalize_meta_value(extract_first(META_DESCRIPTION_PATTERN, text))
        if title:
            titles[title].append(path_str)
        if description:
            descriptions[description].append(path_str)

    for title, paths in sorted(titles.items()):
        if len(paths) > 1:
            detail = " | ".join(paths)
            for path_str in paths:
                add_finding(findings, path_str, "duplicate_meta_title", detail, "medium")

    for description, paths in sorted(descriptions.items()):
        if len(paths) > 1:
            detail = " | ".join(paths)
            for path_str in paths:
                add_finding(findings, path_str, "duplicate_meta_description", detail, "medium")

    return findings


def meta_length_findings(html_pages: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    for html_path in html_pages:
        if html_path.name == "404.html":
            continue
        text = html_path.read_text(encoding="utf-8")
        path_str = str(html_path.relative_to(V2_ROOT.parent))
        is_redirect_page = '<meta http-equiv="refresh"' in text.lower()
        if is_redirect_page:
            continue

        title = normalize_meta_value(extract_first(TITLE_PATTERN, text))
        description = normalize_meta_value(extract_first(META_DESCRIPTION_PATTERN, text))

        if title and not (TITLE_MIN_LEN <= len(title) <= TITLE_MAX_LEN):
            add_finding(findings, path_str, "weak_title_length", f"{len(title)} chars", "low")
        if description and not (DESCRIPTION_MIN_LEN <= len(description) <= DESCRIPTION_MAX_LEN):
            add_finding(findings, path_str, "weak_description_length", f"{len(description)} chars", "low")
    return findings


def schema_findings(html_pages: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    required_schema_pages = {"overview_spot", "portfolio", "strategy_edge", "orderbook", "how_it_works", "news", "resources"}
    for html_path in html_pages:
        if html_path.name != "index.html":
            continue
        page_name = html_path.parent.name if html_path.parent != FRONTEND_ROOT else ""
        if page_name not in required_schema_pages:
            continue
        text = html_path.read_text(encoding="utf-8")
        if not SCHEMA_PATTERN.search(text):
            add_finding(
                findings,
                str(html_path.relative_to(V2_ROOT.parent)),
                "missing_schema_json_ld",
                "missing JSON-LD schema block",
                "low",
            )
    return findings


def sitemap_coverage_findings(html_pages: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    sitemap_path = FRONTEND_ROOT / "sitemap.xml"
    if not sitemap_path.exists():
        return findings

    sitemap_text = sitemap_path.read_text(encoding="utf-8")
    sitemap_urls = {normalize_meta_value(value) for value in SITEMAP_LOC_PATTERN.findall(sitemap_text)}

    for html_path in html_pages:
        if html_path.name == "404.html":
            continue
        text = html_path.read_text(encoding="utf-8")
        if '<meta http-equiv="refresh"' in text.lower():
            continue
        expected = expected_canonical_url(html_path)
        if expected and expected not in sitemap_urls:
            add_finding(
                findings,
                str(html_path.relative_to(V2_ROOT.parent)),
                "missing_sitemap_coverage",
                expected,
                "medium",
            )
    return findings


def publish_site_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    if not PUBLISH_ROOT.exists():
        return findings

    html_pages = sorted(PUBLISH_ROOT.rglob("*.html"))
    findings.extend(publish_required_file_findings())
    findings.extend(publish_sitemap_coverage_findings(html_pages))
    findings.extend(publish_canonical_findings(html_pages))
    findings.extend(publish_internal_link_findings(html_pages))
    return findings


def publish_canonical_findings(html_pages: list[Path]) -> list[FileFinding]:
    """Check the final deployed paths, including separately owned dashboards."""
    findings: list[FileFinding] = []
    for html_path in html_pages:
        if _is_skipped_publish_page(html_path):
            continue
        canonical = extract_first(CANONICAL_PATTERN, html_path.read_text(encoding="utf-8"))
        expected = expected_publish_url(html_path)
        if canonical != expected:
            add_finding(
                findings,
                str(html_path.relative_to(V2_ROOT.parent)),
                "publish_canonical_mismatch",
                f"canonical={canonical or 'missing'} expected={expected}",
                "medium",
            )
    return findings


def publish_required_file_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    if not (PUBLISH_ROOT / "robots.txt").exists():
        add_finding(findings, "publish/Bitcoin-Live-Signals", "publish_missing_robots_txt", "robots.txt", "medium")
    if not (PUBLISH_ROOT / "sitemap.xml").exists():
        add_finding(findings, "publish/Bitcoin-Live-Signals", "publish_missing_sitemap_xml", "sitemap.xml", "high")
    return findings


def publish_sitemap_coverage_findings(html_pages: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    sitemap_path = PUBLISH_ROOT / "sitemap.xml"
    if not sitemap_path.exists():
        return findings

    sitemap_text = sitemap_path.read_text(encoding="utf-8")
    sitemap_urls = {normalize_meta_value(value) for value in SITEMAP_LOC_PATTERN.findall(sitemap_text)}
    for html_path in html_pages:
        if _is_skipped_publish_page(html_path):
            continue
        expected = expected_publish_url(html_path)
        if expected and expected not in sitemap_urls:
            add_finding(
                findings,
                str(html_path.relative_to(V2_ROOT.parent)),
                "publish_missing_sitemap_coverage",
                expected,
                "medium",
            )
    return findings


def publish_internal_link_findings(html_pages: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    for html_path in html_pages:
        if _is_skipped_publish_page(html_path):
            continue
        parser = LinkParser()
        parser.feed(html_path.read_text(encoding="utf-8", errors="ignore"))
        path_str = str(html_path.relative_to(V2_ROOT.parent))
        for tag, attr, raw_url in parser.links:
            resolved = resolve_publish_link(html_path=html_path, raw_url=raw_url)
            if resolved is None:
                continue
            if resolved == "root_absolute":
                add_finding(findings, path_str, "publish_root_absolute_link", raw_url, "medium")
                continue
            if not resolved.exists():
                detail = f"{tag}[{attr}] {raw_url}"
                add_finding(findings, path_str, "publish_broken_internal_link", detail, "high")
    return findings


def _is_skipped_publish_page(html_path: Path) -> bool:
    if html_path.name == "404.html":
        return True
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return True
    return '<meta http-equiv="refresh"' in text.lower()


def expected_publish_url(html_path: Path) -> str:
    relative = html_path.relative_to(PUBLISH_ROOT)
    if relative.name == "index.html":
        if len(relative.parts) == 1:
            return f"{SITE_ROOT}/"
        return f"{SITE_ROOT}/{'/'.join(relative.parts[:-1])}/"
    return f"{SITE_ROOT}/{relative.as_posix()}"


def resolve_publish_link(*, html_path: Path, raw_url: str) -> Path | str | None:
    if not raw_url:
        return None
    url = raw_url.strip()
    lower_url = url.lower()
    if lower_url.startswith(("http://", "https://", "mailto:", "tel:", "data:", "javascript:")):
        return None
    if url.startswith("#"):
        return None

    clean_url = unquote(url.split("#", 1)[0].split("?", 1)[0])
    if not clean_url:
        return None
    if clean_url.startswith("/Bitcoin-Live-Signals/"):
        target = PUBLISH_ROOT / clean_url.removeprefix("/Bitcoin-Live-Signals/")
    elif clean_url.startswith("/"):
        return "root_absolute"
    else:
        target = html_path.parent / clean_url

    if clean_url.endswith("/") or target.is_dir():
        target = target / "index.html"
    elif target.suffix == "" and not target.exists():
        target = target / "index.html"
    return target.resolve()


class LinkParser(HTMLParser):
    LINK_ATTRS = {
        "a": "href",
        "link": "href",
        "script": "src",
        "img": "src",
        "source": "src",
    }

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = self.LINK_ATTRS.get(tag)
        if not attr:
            return
        attr_map = dict(attrs)
        value = attr_map.get(attr)
        if value:
            self.links.append((tag, attr, value))


def expected_canonical_url(html_path: Path) -> str:
    relative = html_path.relative_to(FRONTEND_ROOT)
    if relative.name == "index.html":
        if len(relative.parts) == 1:
            return f"{SITE_ROOT}/"
        return f"{SITE_ROOT}/{'/'.join(relative.parts[:-1])}/"
    if relative.name == "404.html":
        return f"{SITE_ROOT}/404.html"
    return f"{SITE_ROOT}/{relative.as_posix()}"


def extract_first(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def normalize_meta_value(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())
