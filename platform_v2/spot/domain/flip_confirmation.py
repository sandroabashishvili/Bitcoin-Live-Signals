"""Spot-owned rules copied on 2026-09-10; no Futures runtime dependency."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from platform_v2.spot.domain.entry_timing import ACTIONABLE_DIRECTIONS, normalize_direction


@dataclass(frozen=True)
class FlipConfirmationDecision:
    allowed: bool
    status: str
    reason: str


class FlipConfirmationTracker:
    """Require configured direction flips to persist for one complete candle."""

    def __init__(
        self,
        *,
        required_sides: set[str],
        timeframe_ms: int,
    ) -> None:
        self._required_sides = {normalize_direction(side) for side in required_sides}
        self._timeframe_ms = int(timeframe_ms)
        self._confirmed_side: str | None = None
        self._pending_side: str | None = None
        self._pending_timestamp_ms: int | None = None

    def observe(self, *, side: str, timestamp_ms: int) -> FlipConfirmationDecision:
        normalized_side = normalize_direction(side)
        if normalized_side not in ACTIONABLE_DIRECTIONS:
            self._clear_pending()
            return FlipConfirmationDecision(True, "NO_SIGNAL", "no_actionable_direction")
        if self._confirmed_side is None:
            self._confirmed_side = normalized_side
            self._clear_pending()
            return FlipConfirmationDecision(True, "INITIAL_DIRECTION", "initial_direction")
        if normalized_side == self._confirmed_side:
            self._clear_pending()
            return FlipConfirmationDecision(True, "CONFIRMED_DIRECTION", "confirmed_direction")
        if normalized_side not in self._required_sides:
            self._confirmed_side = normalized_side
            self._clear_pending()
            return FlipConfirmationDecision(True, "UNFILTERED_FLIP", "side_not_configured")
        is_next_candle = (
            self._pending_side == normalized_side
            and self._pending_timestamp_ms is not None
            and int(timestamp_ms) - self._pending_timestamp_ms == self._timeframe_ms
        )
        if is_next_candle:
            self._confirmed_side = normalized_side
            self._clear_pending()
            return FlipConfirmationDecision(True, "CONFIRMED_FLIP", "flip_confirmed_next_candle")
        self._pending_side = normalized_side
        self._pending_timestamp_ms = int(timestamp_ms)
        return FlipConfirmationDecision(False, "PENDING_FLIP", "flip_confirmation_pending")

    def _clear_pending(self) -> None:
        self._pending_side = None
        self._pending_timestamp_ms = None


def evaluate_flip_confirmation(
    *,
    side: str,
    timestamp_ms: int,
    prior_signals: Iterable[dict[str, Any]],
    required_sides: set[str],
    timeframe_ms: int,
) -> FlipConfirmationDecision:
    """Rebuild confirmation state from persisted signals, then evaluate current side."""

    tracker = FlipConfirmationTracker(
        required_sides=required_sides,
        timeframe_ms=timeframe_ms,
    )
    for row in sorted(prior_signals, key=lambda item: int(item.get("timestamp_ms") or 0)):
        row_timestamp_ms = int(row.get("timestamp_ms") or 0)
        if row_timestamp_ms >= int(timestamp_ms):
            continue
        tracker.observe(
            side=str(row.get("side") or row.get("selected_direction") or "NO_SIGNAL"),
            timestamp_ms=row_timestamp_ms,
        )
    return tracker.observe(side=side, timestamp_ms=timestamp_ms)
