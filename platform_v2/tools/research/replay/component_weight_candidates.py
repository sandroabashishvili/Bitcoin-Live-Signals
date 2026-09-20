"""Shared builders for one-component research weight candidates."""

from __future__ import annotations

from dataclasses import replace

from platform_v2.tools.research.replay.candidate_profiles import CandidateProfile


def scaled_weight_profile(
    *,
    baseline: CandidateProfile,
    component: str,
    multiplier: float,
) -> CandidateProfile:
    """Return a research profile with exactly one component weight scaled."""

    weights = dict(baseline.weights)
    weights[component] = round(float(weights[component]) * float(multiplier), 4)
    multiplier_id = str(multiplier).replace(".", "p")
    return replace(
        baseline,
        profile_id=f"{baseline.profile_id}_{component}_x{multiplier_id}",
        strategy_version=(
            f"research-{baseline.market}-{baseline.direction.lower()}-"
            f"{component}-x{multiplier_id}"
        ),
        weights=weights,
        status="weight_grid_candidate",
        rationale=f"Isolate {component} at {multiplier:g}x its baseline weight.",
    )
