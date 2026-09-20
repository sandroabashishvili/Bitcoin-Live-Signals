"""Runtime data families owned by the Futures Hedge subsystem."""

from __future__ import annotations


HEDGE_ENTRIES_FAMILY = "hedge_entries"
HEDGE_BASKET_SNAPSHOTS_FAMILY = "hedge_basket_snapshots"
HEDGE_RESET_EVENTS_FAMILY = "hedge_reset_events"
HEDGE_DAILY_SUMMARIES_FAMILY = "hedge_daily_summaries"
HEDGE_EQUITY_TIMELINE_FAMILY = "hedge_equity_timeline"

ALL_FAMILIES: tuple[str, ...] = (
    HEDGE_ENTRIES_FAMILY,
    HEDGE_BASKET_SNAPSHOTS_FAMILY,
    HEDGE_RESET_EVENTS_FAMILY,
    HEDGE_DAILY_SUMMARIES_FAMILY,
    HEDGE_EQUITY_TIMELINE_FAMILY,
)
