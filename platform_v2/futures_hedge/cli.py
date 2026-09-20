"""CLI for the independent Futures Hedge subsystem."""

from __future__ import annotations

import argparse
from pathlib import Path

from platform_v2.futures_hedge.dashboard.overview_hedge import FuturesHedgeOverviewPageService
from platform_v2.futures_hedge.services.replay import FuturesHedgeReplayService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Futures Hedge replay and dashboard commands."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("replay", help="Build the Futures Hedge replay artifact.")
    subparsers.add_parser("build-page", help="Build the Futures Hedge browser page from replay data.")
    subparsers.add_parser("refresh", help="Build replay and browser page together.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    paths: list[Path] = []

    if args.command == "replay":
        paths.append(FuturesHedgeReplayService().build_and_store())
    elif args.command == "build-page":
        paths.append(FuturesHedgeOverviewPageService().build_and_store())
    elif args.command == "refresh":
        paths.append(FuturesHedgeReplayService().build_and_store())
        paths.append(FuturesHedgeOverviewPageService().build_and_store())
    else:
        raise ValueError(f"unsupported futures hedge command: {args.command}")

    _print_result(command=args.command, paths=paths)
    return 0


def _print_result(*, command: str, paths: list[Path]) -> None:
    print(f"[OK] futures hedge command: {command}")
    if not paths:
        print("[OK] no files written")
        return
    print(f"[OK] files written: {len(paths)}")
    for path in paths:
        print(f"- {path}")


if __name__ == "__main__":
    raise SystemExit(main())
