"""Archive and fully remove SmartSignalHub runtime state for a clean restart."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

from platform_v2.futures.config import settings as futures_settings
from platform_v2.futures_hedge.config import settings as hedge_settings
from platform_v2.shared.backend.persistence import clear_system_documents
from platform_v2.shared.backend.persistence.database_paths import DATABASE_ROOT
from platform_v2.spot.storage.paths import runtime_root as spot_runtime_root


SPOT_RUNTIME_ROOT = spot_runtime_root()
FUTURES_RUNTIME_ROOT = futures_settings.RUNTIME_ROOT
HEDGE_RUNTIME_ROOT = hedge_settings.RUNTIME_ROOT
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
ARCHIVE_ROOT = WORKSPACE_ROOT.parent / "runtime_archives"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Archive and remove runtime databases plus Spot/Futures/Hedge state. "
            "The next runtime start recreates only required storage."
        )
    )
    parser.add_argument("--runtime-root", default=str(SPOT_RUNTIME_ROOT), help="Spot runtime root.")
    parser.add_argument("--futures-runtime-root", default=str(FUTURES_RUNTIME_ROOT), help="Futures runtime root.")
    parser.add_argument("--hedge-runtime-root", default=str(HEDGE_RUNTIME_ROOT), help="Hedge runtime root.")
    parser.add_argument("--archive-root", default=str(ARCHIVE_ROOT), help="Runtime reset archive root.")
    parser.add_argument("--dry-run", action="store_true", help="Show archive moves without changing files.")
    parser.add_argument(
        "--spot-only",
        action="store_true",
        help="Archive only Spot runtime and remove Spot documents from the trading database.",
    )
    return parser


def _build_archive_dir(archive_root: Path) -> Path:
    stamp = datetime.now(tz=timezone.utc).strftime("reset_%Y-%m-%d_%H-%M-%S_%f")
    return archive_root / stamp


def _validate_optional_directory(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise SystemExit(f"[!] reset target is not a directory: {path}")


def _archive_directory(source: Path, destination: Path, *, dry_run: bool) -> bool:
    if not source.exists():
        return False
    if dry_run:
        print(f"[dry-run] archive {source} -> {destination}")
        return True
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return True


def _full_reset_targets(
    *, database_root: Path, spot_root: Path, futures_root: Path, hedge_root: Path
) -> tuple[tuple[str, Path], ...]:
    return (
        ("database", database_root),
        ("spot", spot_root),
        ("futures", futures_root),
        ("hedge", hedge_root),
    )


def _run_full_reset(
    *,
    database_root: Path,
    spot_root: Path,
    futures_root: Path,
    hedge_root: Path,
    archive_dir: Path,
    dry_run: bool,
) -> list[str]:
    archived: list[str] = []
    for label, source in _full_reset_targets(
        database_root=database_root,
        spot_root=spot_root,
        futures_root=futures_root,
        hedge_root=hedge_root,
    ):
        if _archive_directory(source, archive_dir / label, dry_run=dry_run):
            archived.append(label)
    return archived


def _run_spot_only_reset(*, spot_root: Path, archive_dir: Path, dry_run: bool) -> list[str]:
    archived: list[str] = []
    if _archive_directory(spot_root, archive_dir / "spot", dry_run=dry_run):
        archived.append("spot")
    if not dry_run:
        clear_system_documents(system="spot")
    return archived


def _rebuild_dashboard_pages_from_clean_state() -> list[Path]:
    """Replace embedded pre-reset dashboard payloads without creating runtime data."""

    from platform_v2.futures.config import load_execution_profile
    from platform_v2.futures.dashboard import (
        OrderbookFuturesPageService,
        OverviewFuturesPageBuilder,
        PortfolioFuturesPageService,
        StrategyEdgeFuturesPageService,
        TradeOutcomesFuturesPageService,
    )
    from platform_v2.futures_hedge.dashboard.overview_hedge import FuturesHedgeOverviewPageService
    from platform_v2.spot.dashboard.orderbook import OrderbookPageService
    from platform_v2.spot.dashboard.overview_spot import OverviewPageService
    from platform_v2.spot.dashboard.portfolio import PortfolioPageService
    from platform_v2.spot.dashboard.strategy_edge import StrategyEdgePageService
    from platform_v2.spot.dashboard.trade_outcomes import TradeOutcomesPageService

    profile = load_execution_profile()
    return [
        OverviewPageService().build_and_store(),
        PortfolioPageService().build_and_store(),
        TradeOutcomesPageService().build_and_store(),
        StrategyEdgePageService().build_and_store(),
        OrderbookPageService().build_and_store(),
        OverviewFuturesPageBuilder().build_and_store(profile=profile),
        PortfolioFuturesPageService().build_and_store(),
        TradeOutcomesFuturesPageService().build_and_store(),
        StrategyEdgeFuturesPageService().build_and_store(),
        OrderbookFuturesPageService().build_and_store(),
        FuturesHedgeOverviewPageService().build_and_store(),
    ]


def main() -> int:
    args = _build_parser().parse_args()
    spot_root = Path(args.runtime_root).expanduser().resolve()
    futures_root = Path(args.futures_runtime_root).expanduser().resolve()
    hedge_root = Path(args.hedge_runtime_root).expanduser().resolve()
    archive_root = Path(args.archive_root).expanduser().resolve()
    targets = (spot_root,) if args.spot_only else (DATABASE_ROOT, spot_root, futures_root, hedge_root)
    for target in targets:
        _validate_optional_directory(target)

    archive_dir = _build_archive_dir(archive_root)
    if args.spot_only:
        archived = _run_spot_only_reset(
            spot_root=spot_root,
            archive_dir=archive_dir,
            dry_run=args.dry_run,
        )
    else:
        archived = _run_full_reset(
            database_root=DATABASE_ROOT,
            spot_root=spot_root,
            futures_root=futures_root,
            hedge_root=hedge_root,
            archive_dir=archive_dir,
            dry_run=args.dry_run,
        )

    if args.dry_run:
        print(f"[OK] dry run complete; targets: {', '.join(archived) or 'none'}")
        return 0
    if archived:
        print(f"[OK] runtime archived to: {archive_dir}")
        print(f"[OK] removed runtime roots: {', '.join(archived)}")
    else:
        print("[OK] runtime is already empty; nothing to reset")
    rebuilt_pages = _rebuild_dashboard_pages_from_clean_state()
    print(f"[OK] rebuilt clean dashboard pages: {len(rebuilt_pages)}")
    print("[OK] next runtime start will recreate databases and mutable state; JSON remains on demand")
    return 0
