from __future__ import annotations

import argparse
from pathlib import Path

from .config import PublishConfig
from .git_ops import (
    clone_if_missing,
    commit_snapshot,
    current_branch,
    has_changes,
    push_snapshot,
    update_from_remote,
)
from .helpers import default_commit_message, utc_timestamp
from .logging_utils import tee_tool_output
from .sync import prune_removed_news_artifacts, cleanup_compat_dirs, rewrite_links_for_github_pages, sync_frontend
from .validation import validate_analytics_ids
from platform_v2.shared.frontend.components.py.site_config import GA_MEASUREMENT_ID
from platform_v2.tools.sitemap_system.generator import build_sitemap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Publish platform_v2 public site and dashboards to GitHub Pages repo.")
    parser.add_argument("--repo-root", default="~/SmartSignalHub/platform_v2", help="Path to platform_v2 root.")
    parser.add_argument("--pages-repo", default="~/SmartSignalHub/publish/Bitcoin-Live-Signals", help="Path to GitHub Pages repo.")
    parser.add_argument("--repo-url", default="git@github.com:sandroabashishvili/Bitcoin-Live-Signals.git", help="GitHub Pages repository URL.")
    parser.add_argument("--branch", default="main", help="Pages repo branch.")
    parser.add_argument("--dry-run", action="store_true", help="Preview sync without writing.")
    parser.add_argument("--full-sync", action="store_true", help="Use a full mirror sync; this is destructive and should be used only when explicitly needed.")
    parser.add_argument("--stats", action="store_true", help="Print a summary of which files changed during the publish run.")
    parser.add_argument("--no-commit", action="store_true", help="Sync only; do not create a git commit.")
    parser.add_argument("--no-push", action="store_true", help="Commit locally only; do not push.")
    parser.add_argument("--amend", action="store_true", help="Amend existing root commit rather than creating an incremental commit.")
    parser.add_argument("--message", default=None, help="Custom git commit message.")
    return parser


def parse_config() -> PublishConfig:
    args = build_parser().parse_args()
    return PublishConfig(
        repo_root=Path(args.repo_root).expanduser(),
        pages_repo=Path(args.pages_repo).expanduser(),
        repo_url=args.repo_url,
        branch=args.branch,
        dry_run=args.dry_run,
        full_sync=args.full_sync,
        stats=args.stats,
        commit=not args.no_commit,
        push=not args.no_push,
        commit_message=args.message,
        amend=args.amend,
    )


def main() -> None:
    config = parse_config()
    with tee_tool_output("github_publish_system.log"):
        _run_publish(config)


def _run_publish(config: PublishConfig) -> None:
    if not config.public_site_source.exists():
        raise SystemExit(f"[!] public site source not found: {config.public_site_source}")
    if not config.spot_dashboard_source.exists():
        raise SystemExit(f"[!] spot dashboard source not found: {config.spot_dashboard_source}")
    if not config.futures_dashboard_source.exists():
        raise SystemExit(f"[!] futures dashboard source not found: {config.futures_dashboard_source}")
    if not config.hedge_dashboard_source.exists():
        raise SystemExit(f"[!] futures hedge dashboard source not found: {config.hedge_dashboard_source}")
    if not config.shared_frontend_source.exists():
        raise SystemExit(f"[!] shared frontend source not found: {config.shared_frontend_source}")
    validate_analytics_ids(
        roots=(
            config.public_site_source,
            config.spot_dashboard_source,
            config.futures_dashboard_source,
            config.hedge_dashboard_source,
            config.shared_frontend_source,
        ),
        expected_id=GA_MEASUREMENT_ID,
    )
    clone_if_missing(config.pages_repo, config.repo_url, config.branch, dry_run=config.dry_run)
    if not config.pages_repo.exists():
        raise SystemExit(f"[!] pages repo not found: {config.pages_repo}")
    if not (config.pages_repo / ".git").exists():
        raise SystemExit(f"[!] target is not a git repo: {config.pages_repo}")
    branch = current_branch(config.pages_repo)
    if branch == "HEAD":
        raise SystemExit("[!] pages repo is in detached HEAD.")
    if branch != config.branch:
        raise SystemExit(f"[!] pages repo is on '{branch}', expected '{config.branch}'.")

    print(f"[{utc_timestamp()}] Updating pages repo from origin/{config.branch}")
    if not config.dry_run:
        update_from_remote(config.pages_repo, config.branch)

    total_updated = 0
    print(f"[{utc_timestamp()}] Syncing {config.public_site_source} -> {config.public_site_dest}")
    count, _ = sync_frontend(source=config.public_site_source, dest=config.public_site_dest, dry_run=config.dry_run, full_sync=config.full_sync, stats=config.stats)
    total_updated += count
    removed_news = prune_removed_news_artifacts(source=config.public_site_source, dest=config.public_site_dest, dry_run=config.dry_run)
    print(f"News artifacts removed (or planned): {removed_news}")
    print(f"[{utc_timestamp()}] Syncing {config.spot_dashboard_source} -> {config.spot_dashboard_dest}")
    count, _ = sync_frontend(
        source=config.spot_dashboard_source,
        dest=config.spot_dashboard_dest,
        dry_run=config.dry_run,
        full_sync=config.full_sync,
        stats=config.stats,
    )
    total_updated += count
    print(f"[{utc_timestamp()}] Syncing {config.futures_dashboard_source} -> {config.futures_dashboard_dest}")
    count, _ = sync_frontend(source=config.futures_dashboard_source, dest=config.futures_dashboard_dest, dry_run=config.dry_run, full_sync=config.full_sync, stats=config.stats)
    total_updated += count
    print(f"[{utc_timestamp()}] Syncing {config.hedge_dashboard_source} -> {config.hedge_dashboard_dest}")
    count, _ = sync_frontend(source=config.hedge_dashboard_source, dest=config.hedge_dashboard_dest, dry_run=config.dry_run, full_sync=config.full_sync, stats=config.stats)
    total_updated += count
    print(f"[{utc_timestamp()}] Syncing {config.shared_frontend_source} -> {config.shared_frontend_dest}")
    count, _ = sync_frontend(source=config.shared_frontend_source, dest=config.shared_frontend_dest, dry_run=config.dry_run, full_sync=config.full_sync, stats=config.stats)
    total_updated += count
    if config.stats:
        print(f"[{utc_timestamp()}] Publish summary: {total_updated} updated files across all sync stages")
    print(f"[{utc_timestamp()}] Rewriting publish links for GitHub Pages")
    rewrite_links_for_github_pages(pages_repo=config.pages_repo, dry_run=config.dry_run)
    print(f"[{utc_timestamp()}] Cleaning compatibility-only directories")
    cleanup_compat_dirs(pages_repo=config.pages_repo, dry_run=config.dry_run)
    validate_analytics_ids(roots=(config.pages_repo,), expected_id=GA_MEASUREMENT_ID)

    if config.dry_run:
        print(f"[{utc_timestamp()}] Dry run completed.")
        return

    sitemap_result = build_sitemap(public_site_root=config.pages_repo)
    print(f"[{utc_timestamp()}] Sitemap rebuilt ({sitemap_result.url_count} URLs)")

    if not has_changes(config.pages_repo):
        print(f"[{utc_timestamp()}] No GitHub Pages changes to publish.")
        return

    if not config.commit:
        print(f"[{utc_timestamp()}] Changes synced. Skipping commit by request.")
        return

    message = config.commit_message or default_commit_message()
    commit_snapshot(config.pages_repo, message, amend=config.amend)
    print(f"[{utc_timestamp()}] Website snapshot updated: {message}")

    if not config.push:
        print(f"[{utc_timestamp()}] Push skipped by request.")
        return

    push_snapshot(config.pages_repo, config.branch, force=config.amend)
    print(f"[{utc_timestamp()}] Pushed to origin/{config.branch}")
