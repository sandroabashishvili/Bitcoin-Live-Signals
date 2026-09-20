from platform_v2.tools.research.replay.candidate_profiles import PROFILES
from platform_v2.tools.research.replay.component_weight_candidates import (
    scaled_weight_profile,
)
from platform_v2.tools.research.replay.futures_weight_grid_replay import (
    profile_pairs,
)


def test_weight_profile_changes_only_requested_component() -> None:
    baseline = PROFILES["futures_short_baseline_v1"]
    candidate = scaled_weight_profile(
        baseline=baseline,
        component="momentum",
        multiplier=0.5,
    )
    for component, weight in baseline.weights.items():
        expected = weight * 0.5 if component == "momentum" else weight
        assert candidate.weights[component] == expected


def test_short_grid_keeps_long_baseline_fixed() -> None:
    pairs = profile_pairs(side="SHORT", multipliers=(0.5,))
    assert len(pairs) == 7
    assert all(long.profile_id == "futures_long_baseline_v1" for long, _short in pairs)


def test_grid_can_limit_components() -> None:
    pairs = profile_pairs(
        side="SHORT",
        multipliers=(0.7, 0.8),
        components=("orderbook",),
    )
    assert len(pairs) == 3
    assert pairs[1][1].weights["orderbook"] == 0.63
    assert pairs[2][1].weights["orderbook"] == 0.72
