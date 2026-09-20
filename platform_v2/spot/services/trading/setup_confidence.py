"""Canonical score-to-confidence conversion for Spot SL/TP setups."""

from __future__ import annotations

from platform_v2.spot.config import settings


def normalized_setup_confidence(score: float) -> float:
    """Map a Spot decision score to the bounded confidence used by SL/TP."""

    max_score = float(settings.SETUP_CONFIDENCE_MAX_SCORE)
    if max_score <= 0:
        raise ValueError("SETUP_CONFIDENCE_MAX_SCORE must be positive.")
    return min(1.0, max(0.0, float(score) / max_score))
