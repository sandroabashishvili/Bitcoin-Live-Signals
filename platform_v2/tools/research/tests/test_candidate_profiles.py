from __future__ import annotations

from platform_v2.tools.research.replay.candidate_profiles import PROFILES, profiles_for


def test_candidate_profile_changes_only_declared_weight() -> None:
    baseline = PROFILES["futures_short_baseline_v1"]
    candidate = PROFILES["futures_short_momentum_zero_v1"]

    for name, value in baseline.weights.items():
        if name == "momentum":
            assert candidate.weights[name] == 0.0
        else:
            assert candidate.weights[name] == value


def test_profile_score_is_reproducible() -> None:
    profile = PROFILES["spot_baseline_v1"]
    components = {name: 1.0 for name in profile.weights}

    assert profile.score(components) == round(sum(profile.weights.values()), 2)


def test_profiles_are_direction_specific() -> None:
    short_profiles = profiles_for(market="futures", direction="SHORT")

    assert short_profiles
    assert all(profile.direction == "SHORT" for profile in short_profiles)


def test_short_joint_candidate_declares_timing_and_exit_only() -> None:
    baseline = PROFILES["futures_short_baseline_v1"]
    candidate = PROFILES["futures_short_flip_stop_cap_25_v1"]

    assert candidate.weights == baseline.weights
    assert candidate.threshold == baseline.threshold
    assert candidate.adjustment_ids == ()
    assert candidate.permission_policy_ids == ("true_flip_one_candle_confirmation",)
    assert candidate.exit_policy_ids == ("short_mid_stop_cap_25_atr",)
