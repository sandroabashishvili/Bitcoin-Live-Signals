"""Classify Futures trade entry timing from directional signal age."""

from __future__ import annotations

from platform_v2.futures.domain.entry_timing import EntryTimingContext, classify_entry_timing


class EntryTimingClassifier:
    @staticmethod
    def context(*, side: str, prior_sides: list[str]) -> EntryTimingContext:
        return classify_entry_timing(side=side, prior_sides=prior_sides)

    @staticmethod
    def classify(*, side: str, prior_sides: list[str]) -> str:
        return EntryTimingClassifier.context(side=side, prior_sides=prior_sides).timing_type
