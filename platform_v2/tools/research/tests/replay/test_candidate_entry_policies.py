from platform_v2.tools.research.replay.candidate_entry_policies import evaluate_entry_policy
from platform_v2.tools.research.replay.candidate_profiles import PROFILES


def test_short_macd_conditional_threshold_only_blocks_declared_band() -> None:
    profile = PROFILES["futures_short_macd_0_02_threshold10_v1"]
    blocked = evaluate_entry_policy(
        profile=profile,
        side="SHORT",
        score=9.5,
        features={"directional_macd_spread_atr": 0.1},
    )
    allowed = evaluate_entry_policy(
        profile=profile,
        side="SHORT",
        score=10.0,
        features={"directional_macd_spread_atr": 0.1},
    )
    assert not blocked.allowed
    assert allowed.allowed


def test_short_macd_half_size_keeps_entry_allowed() -> None:
    result = evaluate_entry_policy(
        profile=PROFILES["futures_short_macd_0_02_half_size_v1"],
        side="SHORT",
        score=9.0,
        features={"directional_macd_spread_atr": 0.1},
    )
    assert result.allowed
    assert result.size_multiplier == 0.5


def test_short_macd_sizing_grid_is_explicit() -> None:
    for profile_id, expected in (
        ("futures_short_macd_0_02_size075_v1", 0.75),
        ("futures_short_macd_0_02_size025_v1", 0.25),
    ):
        result = evaluate_entry_policy(
            profile=PROFILES[profile_id],
            side="SHORT",
            score=9.0,
            features={"directional_macd_spread_atr": 0.1},
        )
        assert result.allowed
        assert result.size_multiplier == expected
