"""Run the independent Futures loop on 15-minute boundaries."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from urllib.error import URLError

from platform_v2.futures.config import load_execution_profile
from platform_v2.futures.services.ops import (
    FuturesTelegramNotificationService,
    MainCycleService,
)
from platform_v2.futures_hedge.services.ops import HedgeTelegramNotificationService
from platform_v2.shared.terminal_output import print_futures_cycle, print_network_skip


POST_BOUNDARY_DELAY_SECONDS = 60


def _sleep_until_next_boundary() -> None:
    now = int(time.time())
    sleep_for = 900 - (now % 900) + POST_BOUNDARY_DELAY_SECONDS
    if sleep_for <= 0:
        sleep_for = 900 + POST_BOUNDARY_DELAY_SECONDS
    time.sleep(sleep_for)


def _run_one_cycle() -> None:
    profile = load_execution_profile()
    date_iso = datetime.now(tz=UTC).date().isoformat()
    cycle_service = MainCycleService()
    telegram_service = FuturesTelegramNotificationService()
    try:
        result = cycle_service.run(profile=profile, date_iso=date_iso, fetch_limit=500)
    except (TimeoutError, URLError) as exc:
        print_network_skip(scope="futures", error=exc)
        return
    if result.skipped or result.summary is None:
        print_futures_cycle(profile=profile, result=result)
        return

    summary = result.summary
    telegram_service.notify_cycle(
        profile=profile,
        summary=summary,
        date_iso=date_iso,
    )
    HedgeTelegramNotificationService().notify_cycle()
    print_futures_cycle(profile=profile, result=result)


def main() -> int:
    _run_one_cycle()
    while True:
        _sleep_until_next_boundary()
        _run_one_cycle()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0) from None
