"""Research-only conditional threshold and sizing policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platform_v2.tools.research.replay.candidate_profiles import CandidateProfile


@dataclass(frozen=True)
class EntryPolicyDecision:
    allowed: bool = True
    size_multiplier: float = 1.0
    reasons: tuple[str, ...] = ()


STATEFUL_ENTRY_POLICIES = {"true_flip_one_candle_confirmation"}


def flip_confirmation_sides(*, profiles: tuple[CandidateProfile, ...]) -> set[str]:
    return {
        str(profile.direction).upper()
        for profile in profiles
        if "true_flip_one_candle_confirmation" in profile.permission_policy_ids
    }


def evaluate_entry_policy(
    *,
    profile: CandidateProfile,
    side: str,
    score: float,
    features: dict[str, Any],
) -> EntryPolicyDecision:
    allowed = True
    size_multiplier = 1.0
    reasons: list[str] = []
    spread = _number(features.get("directional_macd_spread_atr"))
    in_weak_short_macd_band = (
        str(side).upper() == "SHORT"
        and spread is not None
        and 0.0 <= spread < 0.2
    )
    for policy_id in profile.permission_policy_ids:
        if policy_id in STATEFUL_ENTRY_POLICIES:
            continue
        if policy_id == "short_macd_0_02_min_score_10":
            if in_weak_short_macd_band and score < 10.0:
                allowed = False
                reasons.append("short_macd_0_02_score_below_10")
        elif policy_id == "short_macd_0_02_min_score_105":
            if in_weak_short_macd_band and score < 10.5:
                allowed = False
                reasons.append("short_macd_0_02_score_below_10_5")
        elif policy_id == "short_macd_0_02_half_size":
            if in_weak_short_macd_band:
                size_multiplier = min(size_multiplier, 0.5)
                reasons.append("short_macd_0_02_half_size")
        elif policy_id == "short_macd_0_02_size_075":
            if in_weak_short_macd_band:
                size_multiplier = min(size_multiplier, 0.75)
                reasons.append("short_macd_0_02_size_075")
        elif policy_id == "short_macd_0_02_size_025":
            if in_weak_short_macd_band:
                size_multiplier = min(size_multiplier, 0.25)
                reasons.append("short_macd_0_02_size_025")
        else:
            raise ValueError(f"Unknown candidate entry policy: {policy_id}")
    return EntryPolicyDecision(
        allowed=allowed,
        size_multiplier=size_multiplier,
        reasons=tuple(reasons),
    )


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
