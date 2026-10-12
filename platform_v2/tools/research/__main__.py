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

    lab_create = commands.add_parser('signal-lab-create', help='Freeze SQLite databases and pinned source for signal research.')
    lab_create.add_argument('workspace', type=Path)
    lab_create.add_argument('--trading-db', type=Path, required=True)
    lab_create.add_argument('--market-db', type=Path, required=True)
    lab_create.add_argument('--release', type=Path, required=True)
    lab_create.add_argument('--start-ms', type=int, required=True)
    lab_create.add_argument('--end-ms', type=int, required=True)
    lab_candidate = commands.add_parser('signal-lab-candidate', help='Create editable offline candidate files.')
    lab_candidate.add_argument('workspace', type=Path)
    lab_candidate.add_argument('name')
    lab_run = commands.add_parser('signal-lab-run', help='Reconstruct historical signal decisions using frozen code.')
    lab_run.add_argument('workspace', type=Path)
    lab_run.add_argument('--name', default='baseline')
    lab_run.add_argument('--component')
    lab_run.add_argument('--limit', type=int, default=0)
    lab_compare = commands.add_parser('signal-lab-compare', help='Compare fixed-horizon signal quality, without execution assumptions.')
    lab_compare.add_argument('workspace', type=Path)
    lab_compare.add_argument('name')
    portfolio_run = commands.add_parser('portfolio-lab-run', help='Run the full frozen Futures simulator on captured history.')
    portfolio_run.add_argument('workspace', type=Path)
    portfolio_run.add_argument('--name', default='baseline')
    portfolio_run.add_argument('--execution-model', choices=['observed', 'next-minute'], default='observed')
    portfolio_run.add_argument('--component')
    portfolio_run.add_argument('--limit', type=int, default=0)
    portfolio_compare = commands.add_parser('portfolio-lab-compare', help='Compare complete candidate/baseline account evolution.')
    portfolio_compare.add_argument('workspace', type=Path)
    portfolio_compare.add_argument('name')
    portfolio_verify = commands.add_parser('portfolio-lab-verify', help='Verify terminal account and trade events against the frozen archive.')
    portfolio_verify.add_argument('workspace', type=Path)

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
    if args.command.startswith('portfolio-lab-'):
        from platform_v2.tools.research import signal_lab
        if args.command == 'portfolio-lab-run':
            result = signal_lab.portfolio_run(args.workspace, args.name, args.execution_model, args.limit, args.component)
        elif args.command == 'portfolio-lab-compare':
            result = signal_lab.portfolio_compare(args.workspace, args.name)
        else:
            result = signal_lab.portfolio_verify(args.workspace)
        print('[OK]', result)
        return 0
    if args.command.startswith('signal-lab-'):
        from platform_v2.tools.research import signal_lab
        if args.command == 'signal-lab-create':
            result = signal_lab.create(args.workspace, args.trading_db, args.market_db, args.release, args.start_ms, args.end_ms)
        elif args.command == 'signal-lab-candidate':
            result = signal_lab.candidate(args.workspace, args.name)
        elif args.command == 'signal-lab-compare':
            report = signal_lab.compare(args.workspace, args.name)
            print('[OK] changed actions:', report['changed_actions'])
            result = args.workspace.resolve() / 'runs' / args.name / 'comparison.json'
        else:
            result = signal_lab.run(args.workspace, args.name, args.limit, args.component)
        print('[OK]', result)
        return 0
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
