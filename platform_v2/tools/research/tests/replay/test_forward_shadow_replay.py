from platform_v2.tools.research.replay.forward_shadow_replay import DEFAULT_SPEC, load_spec, profile_pairs


def test_frozen_shadow_set_contains_baseline_and_three_arms() -> None:
    pairs = profile_pairs(load_spec(DEFAULT_SPEC))

    assert len(pairs) == 4
    assert pairs[0][0].profile_id == "futures_long_baseline_v1"
    assert pairs[0][1].profile_id == "futures_short_baseline_v1"
    assert pairs[2][1].profile_id == "futures_short_flip_stop_cap_25_v1"
    assert pairs[3][0].profile_id == "futures_long_macd_spread_02_05_neutral_v1"
