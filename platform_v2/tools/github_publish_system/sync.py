from __future__ import annotations

import subprocess
from pathlib import Path
import shutil


def _summarize_rsync_output(output: str) -> tuple[int, list[str]]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    changed_files: list[str] = []
    for line in lines:
        if line.startswith("./"):
            changed_files.append(line)
        elif line.endswith("/"):
            continue
        elif line.startswith("sent ") or line.startswith("total size"):
            continue
        elif line and not line.startswith("building file list"):
            changed_files.append(line)
    return len(changed_files), changed_files


def run_rsync(*, source: Path, dest: Path, dry_run: bool, full_sync: bool) -> tuple[int, list[str]]:
    cmd = ["rsync", "-avm"]
    if full_sync:
        cmd.append("--delete")
    if dry_run:
        cmd.append("--dry-run")
    for pattern in FRONTEND_EXCLUDES:
        cmd.extend(["--exclude", pattern])
    cmd.extend([f"{source}/", f"{dest}/"])
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    count, changed_files = _summarize_rsync_output(result.stdout)
    return count, changed_files


FRONTEND_EXCLUDES = (
    "/README.md",
    "futures/",
    ".git/",
    "__pycache__/",
    "*.py",
    "*.pyc",
    "*.pyo",
    "py/",
    "__init__.py",
    ".DS_Store",
    "charts/frontend_charts.md",
    "assets/videos/",
)


def sync_frontend(*, source: Path, dest: Path, dry_run: bool, full_sync: bool = False, stats: bool = False) -> tuple[int, list[str]]:
    """Copy changed frontend files into the publish tree.

    By default this is a safe incremental sync. The opt-in full-sync mode uses
    rsync's delete behavior for a mirror-style publish.
    """
    if dry_run:
        if not dest.parent.exists():
            print(f"[dry-run] Would create target directory: {dest.parent}")
            return 0, []
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
    count, changed_files = run_rsync(source=source, dest=dest, dry_run=dry_run, full_sync=full_sync)
    if stats:
        print(f"[stats] updated files: {count}")
        if changed_files:
            print("[stats] changed paths:")
            for item in changed_files[:20]:
                print(f"  - {item}")
            if len(changed_files) > 20:
                print(f"  ... and {len(changed_files) - 20} more")
    return count, changed_files


def cleanup_compat_dirs(*, pages_repo: Path, dry_run: bool) -> None:
    """Remove temporary compatibility mirrors and non-web artifacts from publish repo."""

    targets = (
        pages_repo / "frontend",
        pages_repo / "futures" / "frontend",
        pages_repo / "public_site",
        pages_repo / "overview",
        pages_repo / "overview_spot",
        pages_repo / "portfolio",
        pages_repo / "trade_outcomes",
        pages_repo / "strategy_edge",
        pages_repo / "orderbook",
        pages_repo / "futures" / "overview_futures",
        pages_repo / "futures" / "portfolio_futures",
        pages_repo / "futures" / "trade_outcomes_futures",
        pages_repo / "futures" / "strategy_edge_futures",
        pages_repo / "futures" / "orderbook_futures",
        pages_repo / "futures_hedge" / "dashboard" / "dashboard",
    )
    for target in targets:
        if not target.exists():
            continue
        if dry_run:
            print(f"[dry-run] Would remove compatibility directory: {target}")
            continue
        shutil.rmtree(target, ignore_errors=True)

    # Keep GitHub Pages publish static-only: remove any leaked Python source files.
    for py_file in pages_repo.rglob("*.py"):
        if dry_run:
            print(f"[dry-run] Would remove non-web source file: {py_file}")
            continue
        py_file.unlink(missing_ok=True)

    # Keep a single canonical sitemap at repo root.
    root_sitemap = pages_repo / "sitemap.xml"
    for sitemap_file in pages_repo.rglob("sitemap.xml"):
        if sitemap_file == root_sitemap:
            continue
        if dry_run:
            print(f"[dry-run] Would remove nested sitemap: {sitemap_file}")
            continue
        sitemap_file.unlink(missing_ok=True)


def rewrite_links_for_github_pages(*, pages_repo: Path, dry_run: bool) -> None:
    """Rewrite local-runtime links and enforce the current public domain."""

    replacements = (
        (
            "https://sandroabashishvili.github.io/Bitcoin-Live-Signals",
            "https://sandro-abashishvili.de/Bitcoin-Live-Signals",
        ),
        ("../spot/dashboard/", "/Bitcoin-Live-Signals/spot/dashboard/"),
        ("../../spot/dashboard/", "/Bitcoin-Live-Signals/spot/dashboard/"),
        ("../../../spot/dashboard/", "/Bitcoin-Live-Signals/spot/dashboard/"),
        ("../../../../spot/dashboard/", "/Bitcoin-Live-Signals/spot/dashboard/"),
        ("../../futures/dashboard/", "/Bitcoin-Live-Signals/futures/dashboard/"),
        ("../futures/dashboard/", "/Bitcoin-Live-Signals/futures/dashboard/"),
        ("../../../futures/dashboard/", "/Bitcoin-Live-Signals/futures/dashboard/"),
        ("../../../../futures/dashboard/", "/Bitcoin-Live-Signals/futures/dashboard/"),
        ("../futures_hedge/dashboard/", "/Bitcoin-Live-Signals/futures_hedge/dashboard/"),
        ("../../futures_hedge/dashboard/", "/Bitcoin-Live-Signals/futures_hedge/dashboard/"),
        ("../../../futures_hedge/dashboard/", "/Bitcoin-Live-Signals/futures_hedge/dashboard/"),
        ("../../../../futures_hedge/dashboard/", "/Bitcoin-Live-Signals/futures_hedge/dashboard/"),
        ("../shared/frontend/components/", "/Bitcoin-Live-Signals/shared/components/"),
        ("../../shared/frontend/components/", "/Bitcoin-Live-Signals/shared/components/"),
        ("../../../shared/frontend/components/", "/Bitcoin-Live-Signals/shared/components/"),
        ("../../../../shared/frontend/components/", "/Bitcoin-Live-Signals/shared/components/"),
        ("../shared/frontend/charts/", "/Bitcoin-Live-Signals/shared/charts/"),
        ("../../shared/frontend/charts/", "/Bitcoin-Live-Signals/shared/charts/"),
        ("../../../shared/frontend/charts/", "/Bitcoin-Live-Signals/shared/charts/"),
        ("../../../../shared/frontend/charts/", "/Bitcoin-Live-Signals/shared/charts/"),
        ("../shared/frontend/explanation_system/", "/Bitcoin-Live-Signals/shared/explanation_system/"),
        ("../../shared/frontend/explanation_system/", "/Bitcoin-Live-Signals/shared/explanation_system/"),
        ("../../../shared/frontend/explanation_system/", "/Bitcoin-Live-Signals/shared/explanation_system/"),
        ("../../../../shared/frontend/explanation_system/", "/Bitcoin-Live-Signals/shared/explanation_system/"),
        ("../../../public_site/", "/Bitcoin-Live-Signals/"),
        ("../../../../public_site/", "/Bitcoin-Live-Signals/"),
        ("../../public_site/", "/Bitcoin-Live-Signals/"),
        ("../public_site/", "/Bitcoin-Live-Signals/"),
        ("/platform_v2/public_site/", "/Bitcoin-Live-Signals/"),
        ("/platform_v2/spot/dashboard/", "/Bitcoin-Live-Signals/spot/dashboard/"),
        ("/platform_v2/futures/dashboard/", "/Bitcoin-Live-Signals/futures/dashboard/"),
        ("/platform_v2/futures_hedge/dashboard/", "/Bitcoin-Live-Signals/futures_hedge/dashboard/"),
        ("../../futures/dashboard/overview_futures/", "/Bitcoin-Live-Signals/futures/dashboard/overview_futures/"),
        ("../overview_futures/", "/Bitcoin-Live-Signals/futures/dashboard/overview_futures/"),
        ("../../overview_spot/", "/Bitcoin-Live-Signals/spot/dashboard/overview_spot/"),
        ("../overview_spot/", "/Bitcoin-Live-Signals/spot/dashboard/overview_spot/"),
    )
    # Rewrite both HTML and CSS because some futures stylesheets use
    # absolute /platform_v2/... @import paths.
    targets = sorted(
        path
        for path in pages_repo.rglob("*")
        if path.is_file() and path.suffix.lower() in {".html", ".css", ".js"}
    )
    for html_path in targets:
        try:
            original = html_path.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = original
        for source, target in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
            updated = updated.replace(source, target)
        updated = updated.replace("..//Bitcoin-Live-Signals/", "/Bitcoin-Live-Signals/")
        updated = updated.replace("../..//Bitcoin-Live-Signals/", "/Bitcoin-Live-Signals/")
        updated = updated.replace(
            "/Bitcoin-Live-Signals//Bitcoin-Live-Signals/",
            "/Bitcoin-Live-Signals/",
        )
        if updated == original:
            continue
        if dry_run:
            print(f"[dry-run] Would rewrite links in: {html_path}")
            continue
        html_path.write_text(updated, encoding="utf-8")


def prune_removed_news_artifacts(*, source: Path, dest: Path, dry_run: bool = False) -> int:
    """Mirror deletions only for generated news artifacts, never the whole site."""
    if not (source / 'news/index.html').is_file():
        raise ValueError('Refusing news cleanup without a replacement news index')
    candidates = list((dest / 'news/archive').glob('????-??-??.html'))
    candidates += list((dest / 'news/data').glob('news_items_????-??-??.json'))
    candidates += [p for p in (dest / 'assets/news').rglob('*') if p.is_file()]
    stale = [p for p in candidates if not (source / p.relative_to(dest)).is_file()]
    if not dry_run:
        for path in stale:
            path.unlink()
    return len(stale)
