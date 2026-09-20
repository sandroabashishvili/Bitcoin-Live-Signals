"""Site analytics capability with local-source discovery."""

from __future__ import annotations

import re
from pathlib import Path

from platform_v2.tools.ai_assistant.runtime_readers import PLATFORM_ROOT, REPO_ROOT

from .contracts import CapabilityAnswer


CANDIDATE_SOURCES = (
    "platform_v2/runtime/logs",
    "platform_v2/runtime/artifacts/analytics",
    "platform_v2/public_site/runtime",
    "platform_v2/public_site/logs",
)
PUBLIC_SITE = PLATFORM_ROOT / "public_site"
PUBLISH_SITE = REPO_ROOT / "publish" / "Bitcoin-Live-Signals"
SITE_BASE_URL = "https://sandro-abashishvili.de/Bitcoin-Live-Signals"


def answer_site_analytics() -> CapabilityAnswer:
    existing = [str(REPO_ROOT / path) for path in CANDIDATE_SOURCES if (REPO_ROOT / path).exists()]
    public_audit = _public_site_audit()
    lines = [
        "Public site and analytics capability",
        "Visitor count cannot be answered yet from a trusted analytics source.",
    ]
    if existing:
        lines.append("Local candidate folders found:")
        lines.extend(f"- {path}" for path in existing)
    else:
        lines.append("No local analytics/access-log folder found in configured candidates.")
    lines.extend(
        [
            "Needed source examples: server access logs, Plausible export, Google Analytics export, or hosting analytics export.",
            "Until one is configured, this capability must not guess whether visitors were on the site.",
            "",
            "Local public-site audit:",
            *public_audit,
        ]
    )
    sources = tuple(path for path in (*existing, str(PUBLIC_SITE), str(PUBLISH_SITE)) if Path(path).exists())
    return CapabilityAnswer("site_analytics", "\n".join(lines), sources)


def _public_site_audit() -> list[str]:
    pages = (
        PUBLIC_SITE / "index.html",
        PUBLIC_SITE / "news" / "index.html",
        PUBLIC_SITE / "resources" / "index.html",
    )
    archive_pages = _dated_archive_pages()
    sitemap_urls = _sitemap_urls(PUBLIC_SITE / "sitemap.xml")
    publish_sitemap_urls = _sitemap_urls(PUBLISH_SITE / "sitemap.xml")
    lines = [
        f"Public site root: {PUBLIC_SITE}",
        f"Publish mirror: {PUBLISH_SITE}",
        f"Local sitemap URLs: {len(sitemap_urls)}",
        f"Publish sitemap URLs: {len(publish_sitemap_urls)}",
        f"News archive pages: {len(archive_pages)}",
        "Key page SEO checks:",
    ]
    issues: list[str] = []
    for page in pages:
        page_issues = _page_issues(page)
        if page_issues:
            issues.extend(page_issues)
        status = "ok" if not page_issues else f"{len(page_issues)} issue(s)"
        lines.append(f"- {page.relative_to(REPO_ROOT)}: {status}")
    archive_missing = _missing_sitemap_archive_pages(archive_pages, sitemap_urls)
    publish_missing = _missing_publish_pages((pages, archive_pages))
    if archive_missing:
        issues.extend(f"missing sitemap coverage: {path.relative_to(REPO_ROOT)}" for path in archive_missing[:8])
    if publish_missing:
        issues.extend(f"missing publish mirror page: {path.relative_to(REPO_ROOT)}" for path in publish_missing[:8])
    lines.append(f"Sitemap archive coverage issues: {len(archive_missing)}")
    lines.append(f"Publish mirror missing pages: {len(publish_missing)}")
    if issues:
        lines.append("Top issues:")
        lines.extend(f"- {issue}" for issue in issues[:10])
    else:
        lines.append("Verdict: local news/resources/sitemap/publish mirror checks are clean.")
    return lines


def _page_issues(path: Path) -> list[str]:
    if not path.exists():
        return [f"missing page: {path.relative_to(REPO_ROOT)}"]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [f"unreadable page: {path.relative_to(REPO_ROOT)}"]
    issues: list[str] = []
    title = _first_match(r"<title>(.*?)</title>", text)
    if not title:
        issues.append(f"missing title: {path.relative_to(REPO_ROOT)}")
    elif len(title.strip()) < 8:
        issues.append(f"short title: {path.relative_to(REPO_ROOT)}")
    if not re.search(r'<meta\s+name=["\']description["\']', text, flags=re.IGNORECASE):
        issues.append(f"missing meta description: {path.relative_to(REPO_ROOT)}")
    if not re.search(r'<link\s+rel=["\']canonical["\']', text, flags=re.IGNORECASE):
        issues.append(f"missing canonical: {path.relative_to(REPO_ROOT)}")
    return issues


def _sitemap_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(re.findall(r"<loc>(.*?)</loc>", text))


def _missing_sitemap_archive_pages(archive_pages: list[Path], sitemap_urls: set[str]) -> list[Path]:
    missing: list[Path] = []
    for page in archive_pages:
        url = f"{SITE_BASE_URL}/news/archive/{page.name}"
        if url not in sitemap_urls:
            missing.append(page)
    return missing


def _missing_publish_pages(groups: tuple[tuple[Path, ...], list[Path]]) -> list[Path]:
    local_pages = [*groups[0], *groups[1]]
    missing: list[Path] = []
    for page in local_pages:
        try:
            rel = page.relative_to(PUBLIC_SITE)
        except ValueError:
            continue
        if not (PUBLISH_SITE / rel).exists():
            missing.append(page)
    return missing


def _dated_archive_pages() -> list[Path]:
    folder = PUBLIC_SITE / "news" / "archive"
    if not folder.exists():
        return []
    return sorted(path for path in folder.glob("20??-??-??.html") if path.is_file())


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
