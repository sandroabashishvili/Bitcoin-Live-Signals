"""Futures timing: legacy LONG guard and price-confirmed mature SHORT entries."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any

from platform_v2.futures.config import settings
from platform_v2.futures.domain.entry_timing import (
    classify_entry_timing,
    normalize_direction,
)
from platform_v2.futures.domain.flip_confirmation import evaluate_flip_confirmation


@dataclass(frozen=True)
class EntryQualityDecision:
    allowed: bool
    timing_type: str
    direction_signal_age: int
    prior_actionable_side: str | None
    flip_confirmation_status: str
    reason: str


class FuturesEntryQualityService:
    """Classify current directional signal timing before entry permission opens a trade."""

    def __init__(
        self,
        *,
        blocked_timings: tuple[str, ...] = settings.ENTRY_QUALITY_BLOCKED_TIMINGS,
        flip_confirmation_required_sides: tuple[str, ...] = settings.FLIP_CONFIRMATION_REQUIRED_SIDES,
        flip_confirmation_timeframe_ms: int = settings.FLIP_CONFIRMATION_TIMEFRAME_MS,
    ) -> None:
        self._blocked_timings = {str(value).upper() for value in blocked_timings}
        self._flip_confirmation_required_sides = {
            normalize_direction(value) for value in flip_confirmation_required_sides
        }
        self._flip_confirmation_timeframe_ms = int(flip_confirmation_timeframe_ms)

    def evaluate(
        self,
        *,
        signal_side: str,
        timestamp_ms: int,
        prior_signals: list[dict[str, Any]],
        market_plan_permission: dict[str, Any] | None = None,
    ) -> EntryQualityDecision:
        side = self._normalize_direction(signal_side)
        if side not in {"LONG", "SHORT"}:
            return EntryQualityDecision(
                allowed=True,
                timing_type="NO_SIGNAL",
                direction_signal_age=0,
                prior_actionable_side=None,
                flip_confirmation_status="NO_SIGNAL",
                reason="no_actionable_direction",
            )

        prior_sides = [
            str(row.get("side") or row.get("selected_direction") or "")
            for row in sorted(
                prior_signals,
                key=lambda item: int(item.get("timestamp_ms") or 0),
            )
            if int(row.get("timestamp_ms") or 0) < timestamp_ms
        ]
        timing = classify_entry_timing(
            side=side,
            prior_sides=prior_sides,
        )
        # SHORT age is descriptive. Neutral candles do not make an old move fresh.
        # A missing candle breaks continuity and requires a fresh observed candle.
        history_gap = False
        if side == "SHORT":
            ordered = {int(row.get("timestamp_ms") or 0): row for row in prior_signals
                       if int(row.get("timestamp_ms") or 0) < timestamp_ms}
            contiguous = []
            expected = timestamp_ms
            for ts in sorted(ordered, reverse=True):
                if expected - ts > self._flip_confirmation_timeframe_ms:
                    history_gap = not contiguous
                    break
                contiguous.append(ordered[ts])
                expected = ts
            directions = [self._normalize_direction(str(row.get("side") or row.get("selected_direction") or ""))
                          for row in reversed(contiguous)]
            actionable = [value for value in directions if value in {"LONG", "SHORT"}]
            timing = classify_entry_timing(side=side, prior_sides=actionable)
            if directions and directions[-1] not in {"LONG", "SHORT"} and actionable and actionable[-1] == side and timing.direction_signal_age <= 2:
                timing = replace(timing, timing_type="FRESH_REENTRY", prior_actionable_side=side)
        direction_age = timing.direction_signal_age
        timing_type = timing.timing_type
        flip_confirmation = evaluate_flip_confirmation(
            side=side,
            timestamp_ms=timestamp_ms,
            prior_signals=prior_signals,
            required_sides=self._flip_confirmation_required_sides,
            timeframe_ms=self._flip_confirmation_timeframe_ms,
        )
        if history_gap:
            return EntryQualityDecision(False, "HISTORY_GAP", direction_age,
                                        timing.prior_actionable_side, "AWAITING_CONTIGUOUS_CANDLE",
                                        "entry_history_gap")
        if not flip_confirmation.allowed:
            return EntryQualityDecision(
                allowed=False,
                timing_type=timing_type,
                direction_signal_age=direction_age,
                prior_actionable_side=timing.prior_actionable_side,
                flip_confirmation_status=flip_confirmation.status,
                reason=flip_confirmation.reason,
            )
        if side == "SHORT" and timing_type in self._blocked_timings:
            # Existing market-plan location thresholds, not signal count, decide
            # whether a mature directional run has a usable price location.
            plan = market_plan_permission or {}
            location = plan.get("plan_location") or {}
            def finite(name):
                try:
                    return math.isfinite(float(location[name]))
                except (KeyError, TypeError, ValueError, OverflowError):
                    return False
            current = plan.get("plan_timestamp_ms") == timestamp_ms
            usable = (current and plan.get("allowed") is True
                      and plan.get("alignment") == "IN_ZONE"
                      and location.get("short_entry_state") == "CLEAN"
                      and all(finite(name) for name in ("ema9_distance_atr", "vwap_distance_atr", "distance_to_swing_low_atr")))
            return EntryQualityDecision(bool(usable), "MATURE_DIRECTION", direction_age,
                                        timing.prior_actionable_side, flip_confirmation.status,
                                        "mature_short_in_clean_zone" if usable else "short_entry_location_unconfirmed")
        if timing_type in self._blocked_timings:
            return EntryQualityDecision(
                allowed=False,
                timing_type=timing_type,
                direction_signal_age=direction_age,
                prior_actionable_side=timing.prior_actionable_side,
                flip_confirmation_status=flip_confirmation.status,
                reason="entry_quality_block",
            )
        return EntryQualityDecision(
            allowed=True,
            timing_type=timing_type,
            direction_signal_age=direction_age,
            prior_actionable_side=timing.prior_actionable_side,
            flip_confirmation_status=flip_confirmation.status,
            reason="allowed",
        )

    @staticmethod
    def _normalize_direction(direction: str) -> str:
        return normalize_direction(direction)
