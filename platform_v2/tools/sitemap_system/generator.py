from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_BASE_URL = "https://sandro-abashishvili.de/Bitcoin-Live-Signals"

_EXCLUDED_PATHS = {
    "404.html",
    "sitemap.xml",
    "robots.txt",
    "guide/index.html",
    "overview/sitemap.xml",
}


@dataclass(frozen=True)
class SitemapBuildResult:
    url_count: int
    sitemap_path: Path
    mirror_path: Path | None
    futures_mirror_path: Path | None


def _file_lastmod(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")


def build_sitemap(
    *,
    public_site_root: Path,
    base_url: str = DEFAULT_BASE_URL,
    spot_dashboard_root: Path | None = None,
    futures_dashboard_root: Path | None = None,
    hedge_dashboard_root: Path | None = None,
) -> SitemapBuildResult:
    resolved_base_url = base_url.rstrip("/")
    entries: list[tuple[str, str]] = _collect_urls(html_root=public_site_root, base_url=resolved_base_url)
    if spot_dashboard_root is not None and spot_dashboard_root.exists():
        entries.extend(_collect_spot_urls(spot_dashboard_root=spot_dashboard_root, base_url=resolved_base_url))
    if futures_dashboard_root is not None and futures_dashboard_root.exists():
        entries.extend(_collect_futures_urls(futures_dashboard_root=futures_dashboard_root, base_url=resolved_base_url))
    if hedge_dashboard_root is not None and hedge_dashboard_root.exists():
        entries.extend(_collect_hedge_urls(hedge_dashboard_root=hedge_dashboard_root, base_url=resolved_base_url))

    merged: dict[str, str] = {}
    for url, lastmod in entries:
        existing = merged.get(url)
        if existing is None or lastmod > existing:
            merged[url] = lastmod
    ordered_entries = sorted(merged.items(), key=lambda item: item[0])
    xml_text = _render_sitemap(ordered_entries)

    sitemap_path = public_site_root / "sitemap.xml"
    sitemap_path.write_text(xml_text, encoding="utf-8")
    stale_mirror_path = public_site_root / "overview" / "sitemap.xml"
    if stale_mirror_path.exists():
        stale_mirror_path.unlink()

    return SitemapBuildResult(
        url_count=len(ordered_entries),
        sitemap_path=sitemap_path,
        mirror_path=None,
        futures_mirror_path=None,
    )


def _collect_urls(*, html_root: Path, base_url: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for html_path in sorted(html_root.rglob("*.html")):
        rel_path = html_path.relative_to(html_root).as_posix()
        if rel_path in _EXCLUDED_PATHS:
            continue
        if rel_path.startswith("assets/"):
            continue
        entries.append((_html_path_to_url(rel_path=rel_path, base_url=base_url), _file_lastmod(html_path)))
    return entries


def _collect_futures_urls(*, futures_dashboard_root: Path, base_url: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for html_path in sorted(futures_dashboard_root.rglob("*.html")):
        rel_path = html_path.relative_to(futures_dashboard_root).as_posix()
        lastmod = _file_lastmod(html_path)
        if rel_path.endswith("/index.html"):
            clean_path = rel_path[: -len("index.html")]
            entries.append((f"{base_url}/futures/dashboard/{clean_path}".rstrip("/") + "/", lastmod))
        elif rel_path == "index.html":
            entries.append((f"{base_url}/futures/dashboard/", lastmod))
        elif rel_path.endswith("index.html"):
            clean_path = rel_path[: -len("index.html")]
            entries.append((f"{base_url}/futures/dashboard/{clean_path}".rstrip("/") + "/", lastmod))
        else:
            entries.append((f"{base_url}/futures/dashboard/{rel_path}", lastmod))
    return entries


def _collect_spot_urls(*, spot_dashboard_root: Path, base_url: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for html_path in sorted(spot_dashboard_root.rglob("*.html")):
        rel_path = html_path.relative_to(spot_dashboard_root).as_posix()
        lastmod = _file_lastmod(html_path)
        if rel_path.endswith("/index.html"):
            clean_path = rel_path[: -len("index.html")]
            entries.append((f"{base_url}/spot/dashboard/{clean_path}".rstrip("/") + "/", lastmod))
        elif rel_path == "index.html":
            entries.append((f"{base_url}/spot/dashboard/", lastmod))
        elif rel_path.endswith("index.html"):
            clean_path = rel_path[: -len("index.html")]
            entries.append((f"{base_url}/spot/dashboard/{clean_path}".rstrip("/") + "/", lastmod))
        else:
            entries.append((f"{base_url}/spot/dashboard/{rel_path}", lastmod))
    return entries


def _collect_hedge_urls(*, hedge_dashboard_root: Path, base_url: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for html_path in sorted(hedge_dashboard_root.rglob("*.html")):
        rel_path = html_path.relative_to(hedge_dashboard_root).as_posix()
        lastmod = _file_lastmod(html_path)
        if rel_path.endswith("/index.html"):
            clean_path = rel_path[: -len("index.html")]
            entries.append((f"{base_url}/futures_hedge/dashboard/{clean_path}".rstrip("/") + "/", lastmod))
        elif rel_path == "index.html":
            entries.append((f"{base_url}/futures_hedge/dashboard/", lastmod))
        elif rel_path.endswith("index.html"):
            clean_path = rel_path[: -len("index.html")]
            entries.append((f"{base_url}/futures_hedge/dashboard/{clean_path}".rstrip("/") + "/", lastmod))
        else:
            entries.append((f"{base_url}/futures_hedge/dashboard/{rel_path}", lastmod))
    return entries


def _html_path_to_url(*, rel_path: str, base_url: str) -> str:
    if rel_path.endswith("/index.html"):
        clean_path = rel_path[: -len("index.html")]
        return f"{base_url}/{clean_path}".rstrip("/") + "/"
    if rel_path == "index.html":
        return f"{base_url}/"
    if rel_path.endswith("index.html"):
        clean_path = rel_path[: -len("index.html")]
        return f"{base_url}/{clean_path}".rstrip("/") + "/"
    return f"{base_url}/{rel_path}"


def _render_sitemap(entries: list[tuple[str, str]]) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, lastmod in entries:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{url}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"
