from __future__ import annotations

import argparse
from pathlib import Path

from .generator import DEFAULT_BASE_URL, build_sitemap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild public-site sitemap.xml from public and dashboard HTML.")
    parser.add_argument(
        "--public-site-root",
        default=str(Path(__file__).resolve().parents[2] / "public_site"),
        help="Public site root containing static HTML files.",
    )
    parser.add_argument(
        "--spot-dashboard-root",
        default=str(Path(__file__).resolve().parents[2] / "spot" / "dashboard"),
        help="Spot dashboard root containing generated HTML files.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Public base URL used in sitemap loc entries.",
    )
    parser.add_argument(
        "--futures-dashboard-root",
        default=str(Path(__file__).resolve().parents[2] / "futures" / "dashboard"),
        help="Futures dashboard root containing generated HTML files.",
    )
    parser.add_argument(
        "--hedge-dashboard-root",
        default=str(Path(__file__).resolve().parents[2] / "futures_hedge" / "dashboard"),
        help="Futures Hedge dashboard root containing generated HTML files.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    public_site_root = Path(args.public_site_root).expanduser().resolve()
    spot_dashboard_root = Path(args.spot_dashboard_root).expanduser().resolve()
    futures_dashboard_root = Path(args.futures_dashboard_root).expanduser().resolve()
    hedge_dashboard_root = Path(args.hedge_dashboard_root).expanduser().resolve()
    result = build_sitemap(
        public_site_root=public_site_root,
        base_url=args.base_url,
        spot_dashboard_root=spot_dashboard_root,
        futures_dashboard_root=futures_dashboard_root,
        hedge_dashboard_root=hedge_dashboard_root,
    )
    print(f"Sitemap rebuilt: {result.url_count} URLs")
    print(f"Root sitemap: {result.sitemap_path}")
    print(f"Overview mirror: {result.mirror_path}")
    print(f"Futures mirror: {result.futures_mirror_path}")
