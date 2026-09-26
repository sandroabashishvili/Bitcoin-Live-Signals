"""Research tooling command line."""

from __future__ import annotations

import argparse
from pathlib import Path

from platform_v2.tools.analytics_system.baseline import (
    BaselineDataRoots,
    DEFAULT_OUTPUT_ROOT,
    build_baseline,
    write_baseline,
)
from platform_v2.tools.research.paths import DEFAULT_SNAPSHOT_PARENT, ResearchDataRoots
from platform_v2.tools.research.historical_indicators import build_spot_indicator_history
from platform_v2.tools.research.snapshot import create_snapshot, verify_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe SmartSignalHub research workspace tools.")
    commands = parser.add_subparsers(dest="command", required=True)

    snapshot = commands.add_parser("snapshot", help="Export canonical SQLite data as hashed JSON for offline research.")
    snapshot.add_argument("--output-parent", type=Path, default=DEFAULT_SNAPSHOT_PARENT)

    verify = commands.add_parser("verify-snapshot", help="Verify snapshot JSON files and hashes.")
    verify.add_argument("snapshot", type=Path)

    baseline = commands.add_parser("baseline", help="Build a baseline from an existing snapshot.")
    baseline.add_argument("snapshot", type=Path)
    baseline.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)

    indicators = commands.add_parser(
        "build-spot-indicators",
        help="Build full-history Spot indicators from a frozen snapshot.",
    )
    indicators.add_argument("snapshot", type=Path)
    indicators.add_argument("--output-root", type=Path, required=True)
    indicators.add_argument("--symbol", default="BTCUSDT")
    indicators.add_argument("--timeframes", nargs="+", default=["5m", "15m", "4h"])
    indicators.add_argument(
        "--include-candidate-ema9",
        action="store_true",
        help="Add EMA9 for candidate analysis without changing live indicators.",
    )

    args = parser.parse_args()
    if args.command == "snapshot":
        path = create_snapshot(snapshot_parent=args.output_parent)
        errors = verify_snapshot(path)
        if errors:
            for error in errors:
                print(f"[ERROR] {error}")
            return 1
        print(f"[OK] research snapshot: {path}")
        print("[OK] verification: passed")
        return 0
    if args.command == "verify-snapshot":
        errors = verify_snapshot(args.snapshot)
        if errors:
            for error in errors:
                print(f"[ERROR] {error}")
            return 1
        print(f"[OK] snapshot verified: {args.snapshot.expanduser().resolve()}")
        return 0
    if args.command == "baseline":
        roots = ResearchDataRoots.from_snapshot(args.snapshot)
        report = build_baseline(BaselineDataRoots(roots.spot, roots.futures, roots.hedge))
        paths = write_baseline(report, args.output_root.expanduser().resolve())
        for path in paths:
            print(f"[OK] {path}")
        return 0
    if args.command == "build-spot-indicators":
        roots = ResearchDataRoots.from_snapshot(args.snapshot)
        paths = build_spot_indicator_history(
            spot_data_root=roots.spot,
            output_root=args.output_root.expanduser().resolve(),
            symbol=args.symbol,
            timeframes=args.timeframes,
            include_candidate_ema9=bool(args.include_candidate_ema9),
        )
        for path in paths:
            print(f"[OK] {path}")
        return 0
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
