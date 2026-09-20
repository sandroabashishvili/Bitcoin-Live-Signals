"""File: run_loop.py
Folder: platform_v2/spot/app
Created date: 2026-03-25
Last updated date: 2026-04-24
Author: Codex
Purpose: Run the V2 main cycle continuously on the 15-minute boundary.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from platform_v2.spot.config import settings
from platform_v2.spot.services.ops.main_cycle_service import MainCycleService
from platform_v2.spot.services.ops.main_cycle.models import MainCycleResult
from platform_v2.shared.terminal_output import print_network_skip, print_pages_updated, print_spot_cycle


POST_BOUNDARY_DELAY_SECONDS = 60


def _sleep_until_next_boundary() -> None:
    """Sleep until shortly after the next 15-minute boundary."""

    now = int(time.time())
    sleep_for = 900 - (now % 900) + POST_BOUNDARY_DELAY_SECONDS
    if sleep_for <= 0:
        sleep_for = 900 + POST_BOUNDARY_DELAY_SECONDS
    time.sleep(sleep_for)


def _run_one_cycle(service: MainCycleService) -> MainCycleResult | None:
    """Run one V2 cycle and print a short summary."""

    date_iso = datetime.now(tz=timezone.utc).date().isoformat()
    try:
        result = service.run(
            symbol=settings.DEFAULT_SYMBOL,
            timeframe=settings.DEFAULT_TIMEFRAME,
            date_iso=date_iso,
            position_size=settings.DEFAULT_POSITION_SIZE,
            starting_balance=settings.DEFAULT_STARTING_BALANCE,
            fetch_limit=settings.DEFAULT_FETCH_LIMIT,
        )
    except (TimeoutError, URLError) as exc:
        print_network_skip(scope="spot", error=exc)
        return None
    print_spot_cycle(result)
    return result


def _regenerate_frontend_pages() -> None:
    """Regenerate static frontend pages after a cycle."""

    try:
        from platform_v2.spot.dashboard.overview_spot.py.page_builder import OverviewPageService
        from platform_v2.spot.dashboard.portfolio.py.page_builder import PortfolioPageService
        from platform_v2.spot.dashboard.trade_outcomes.py.page_builder import TradeOutcomesPageService
        from platform_v2.spot.dashboard.strategy_edge.py.page_builder import StrategyEdgePageService
        from platform_v2.spot.dashboard.orderbook.py.page_builder import OrderbookPageService
    except Exception as exc:  # pragma: no cover - runtime-only guard
        print(f"[run_loop] Failed to import page builders: {exc}", file=sys.stderr, flush=True)
        return

    try:
        builders = (
            OverviewPageService(),
            PortfolioPageService(),
            TradeOutcomesPageService(),
            StrategyEdgePageService(),
            OrderbookPageService(),
        )
        updated_paths = [builder.build_and_store() for builder in builders]
        print_pages_updated(scope="spot", paths=updated_paths)
    except Exception as exc:  # pragma: no cover - runtime-only guard
        print(f"[run_loop] Failed to regenerate frontend pages: {exc}", file=sys.stderr, flush=True)


def main() -> int:
    """Run V2 continuously on the quarter-hour schedule."""

    service = MainCycleService()
    result = _run_one_cycle(service)
    if result is not None and not result.skipped:
        _regenerate_frontend_pages()

    while True:
        _sleep_until_next_boundary()
        result = _run_one_cycle(service)
        if result is not None and not result.skipped:
            _regenerate_frontend_pages()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0) from None
