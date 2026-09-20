"""File: cli.py
Folder: platform_v2/tools/analytics_system
Created date: 2026-06-03
Last updated date: 2026-06-03
Author: Codex
Purpose: Safe CLI wrapper for report-generating Spot/Futures analytics services.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from platform_v2.futures.services.analytics import (
    FuturesAggregateAuditReportService,
    FuturesEntryTimingSummaryService,
    FuturesGateEffectivenessReportService,
    FuturesIndicatorBuilderService,
    FuturesMarketPlanService,
    FuturesShortFailureReportService,
    FuturesTradeEntryAuditService,
    FuturesTuningAuditReportService,
)
from platform_v2.spot.services.analytics.indicator_builder_service import IndicatorBuilderService
from platform_v2.tools.analytics_system.baseline import (
    BaselineDataRoots,
    DEFAULT_OUTPUT_ROOT,
    build_baseline,
    write_baseline,
)


DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_TIMEFRAMES = ("5m", "15m", "4h")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run safe SmartSignalHub analytics reports without changing trading execution state."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_date_command(subparsers, "futures-gates", "Build Futures strategy/trade gate effectiveness reports.")
    _add_date_command(subparsers, "futures-entry-audit", "Build Futures closed-trade entry audit rows.")
    _add_date_command(subparsers, "futures-entry-timing", "Build Futures entry timing summary.")
    _add_date_command(subparsers, "futures-trade-audit", "Build Futures aggregate trade audit report.")
    _add_date_command(subparsers, "futures-short-failure", "Build Futures SHORT failure report.")
    _add_date_command(subparsers, "futures-tuning", "Build Futures tuning audit report.")

    market_plan = _add_date_command(subparsers, "futures-market-plan", "Build Futures market plan snapshot.")
    market_plan.add_argument("--symbol", default=DEFAULT_SYMBOL)
    market_plan.add_argument("--timeframe", default="15m")

    futures_indicators = subparsers.add_parser("futures-indicators", help="Build Futures indicator snapshots.")
    futures_indicators.add_argument("--symbol", default=DEFAULT_SYMBOL)
    futures_indicators.add_argument("--timeframes", nargs="+", default=list(DEFAULT_TIMEFRAMES))

    spot_indicators = subparsers.add_parser("spot-indicators", help="Build Spot indicator snapshots.")
    spot_indicators.add_argument("--symbol", default=DEFAULT_SYMBOL)
    spot_indicators.add_argument("--timeframes", nargs="+", default=list(DEFAULT_TIMEFRAMES))

    suite = _add_date_command(subparsers, "futures-audit-suite", "Build the standard Futures analytics audit suite.")
    suite.add_argument("--symbol", default=DEFAULT_SYMBOL)
    suite.add_argument("--timeframes", nargs="+", default=list(DEFAULT_TIMEFRAMES))

    baseline = subparsers.add_parser(
        "baseline",
        help="Build one read-only Spot/Futures/Hedge comparison baseline.",
    )
    live_roots = BaselineDataRoots.live()
    baseline.add_argument("--spot-data", type=Path, default=live_roots.spot)
    baseline.add_argument("--futures-data", type=Path, default=live_roots.futures)
    baseline.add_argument("--hedge-data", type=Path, default=live_roots.hedge)
    baseline.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    paths: list[Path] = []

    if args.command == "futures-gates":
        paths.extend(FuturesGateEffectivenessReportService().build_and_store(date_iso=args.date))
    elif args.command == "futures-entry-audit":
        paths.append(FuturesTradeEntryAuditService().build_and_store(date_iso=args.date))
    elif args.command == "futures-entry-timing":
        paths.append(FuturesEntryTimingSummaryService().build_and_store(date_iso=args.date))
    elif args.command == "futures-trade-audit":
        paths.append(FuturesAggregateAuditReportService().build_and_store(date_iso=args.date))
    elif args.command == "futures-short-failure":
        paths.append(FuturesShortFailureReportService().build_and_store(date_iso=args.date))
    elif args.command == "futures-tuning":
        paths.append(FuturesTuningAuditReportService().build_and_store(date_iso=args.date))
    elif args.command == "futures-market-plan":
        path = FuturesMarketPlanService().build_and_store(
            date_iso=args.date,
            symbol=args.symbol,
            timeframe=args.timeframe,
        )
        if path is not None:
            paths.append(path)
    elif args.command == "futures-indicators":
        paths.extend(FuturesIndicatorBuilderService().build_many(symbol=args.symbol, timeframes=args.timeframes))
    elif args.command == "spot-indicators":
        paths.extend(IndicatorBuilderService().build_many(symbol=args.symbol, timeframes=args.timeframes))
    elif args.command == "futures-audit-suite":
        paths.extend(_run_futures_audit_suite(date_iso=args.date, symbol=args.symbol, timeframes=args.timeframes))
    elif args.command == "baseline":
        report = build_baseline(
            BaselineDataRoots(
                spot=args.spot_data.expanduser().resolve(),
                futures=args.futures_data.expanduser().resolve(),
                hedge=args.hedge_data.expanduser().resolve(),
            )
        )
        paths.extend(write_baseline(report, args.output_root.expanduser().resolve()))
    else:
        raise ValueError(f"unsupported analytics command: {args.command}")

    _print_result(command=args.command, paths=paths)
    return 0


def _add_date_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("--date", required=True, help="Report date in YYYY-MM-DD format.")
    return parser


def _run_futures_audit_suite(*, date_iso: str, symbol: str, timeframes: list[str]) -> list[Path]:
    paths: list[Path] = []
    paths.extend(FuturesIndicatorBuilderService().build_many(symbol=symbol, timeframes=timeframes))
    market_plan = FuturesMarketPlanService().build_and_store(date_iso=date_iso, symbol=symbol, timeframe="15m")
    if market_plan is not None:
        paths.append(market_plan)
    paths.extend(FuturesGateEffectivenessReportService().build_and_store(date_iso=date_iso))
    paths.append(FuturesTradeEntryAuditService().build_and_store(date_iso=date_iso))
    paths.append(FuturesEntryTimingSummaryService().build_and_store(date_iso=date_iso))
    paths.append(FuturesAggregateAuditReportService().build_and_store(date_iso=date_iso))
    paths.append(FuturesShortFailureReportService().build_and_store(date_iso=date_iso))
    paths.append(FuturesTuningAuditReportService().build_and_store(date_iso=date_iso))
    return paths


def _print_result(*, command: str, paths: list[Path]) -> None:
    print(f"[OK] analytics command: {command}")
    if not paths:
        print("[OK] no files written")
        return
    print(f"[OK] files written: {len(paths)}")
    for path in paths:
        print(f"- {path}")
