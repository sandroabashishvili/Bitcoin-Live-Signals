"""Shared Futures entry-timing classification.

The timing label describes both the current same-direction streak and the
actionable direction that preceded that streak.  A short pause (NO_SIGNAL)
must not turn a same-direction re-entry into a directional flip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


ACTIONABLE_DIRECTIONS = {"LONG", "SHORT"}
FRESH_OR_EARLY_TIMINGS = {
    "FRESH_FLIP",
    "FRESH_SIGNAL",
    "FRESH_REENTRY",
    "EARLY_CONTINUATION",
}


@dataclass(frozen=True)
class EntryTimingContext:
    timing_type: str
    direction_signal_age: int
    prior_actionable_side: str | None


def normalize_direction(direction: str) -> str:
    normalized = str(direction or "").upper()
    if normalized == "BUY":
        return "LONG"
    if normalized == "SELL":
        return "SHORT"
    return normalized


def classify_entry_timing(
    *,
    side: str,
    prior_sides: Iterable[str],
) -> EntryTimingContext:
    """Classify one current actionable direction from its prior side history."""

    normalized_side = normalize_direction(side)
    if normalized_side not in ACTIONABLE_DIRECTIONS:
        return EntryTimingContext("NO_SIGNAL", 0, None)

    history = [normalize_direction(value) for value in prior_sides]
    direction_age = 1
    boundary_index = len(history) - 1
    while boundary_index >= 0 and history[boundary_index] == normalized_side:
        direction_age += 1
        boundary_index -= 1

    prior_actionable_side = next(
        (
            history[index]
            for index in range(boundary_index, -1, -1)
            if history[index] in ACTIONABLE_DIRECTIONS
        ),
        None,
    )

    if direction_age <= 2:
        if prior_actionable_side is None:
            timing_type = "FRESH_SIGNAL"
        elif prior_actionable_side != normalized_side:
            timing_type = "FRESH_FLIP"
        else:
            timing_type = "FRESH_REENTRY"
    elif direction_age <= 6:
        timing_type = "EARLY_CONTINUATION"
    elif direction_age <= 12:
        timing_type = "LATE_EXTENSION"
    else:
        timing_type = "EXHAUSTED_MOVE"

    return EntryTimingContext(
        timing_type=timing_type,
        direction_signal_age=direction_age,
        prior_actionable_side=prior_actionable_side,
    )
