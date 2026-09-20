from types import SimpleNamespace

from platform_v2.tools.research.replay.candidate_profiles import PROFILES
from platform_v2.tools.research.replay.indicator_candidate_adjustments import adjusted_components


def _snapshot(**overrides):
    values = {
        "rsi": 60.0,
        "macd": 10.0,
        "macd_signal": 8.0,
        "atr": 10.0,
        "price": 100.0,
        "swing_high": 120.0,
        "adx": 25.0,
        "plus_di": 10.0,
        "minus_di": 20.0,
        "atr_growth_20": 0.1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_long_rsi_adjustment_removes_only_rsi_reward() -> None:
    result = adjusted_components(
        profile=PROFILES["futures_long_rsi_58_65_neutral_v1"],
        components={"momentum": 2.2, "trend": 3.0},
        snapshot=_snapshot(),
    )
    assert result == {"momentum": 0.8, "trend": 3.0}


def test_long_rsi_momentum_can_be_fully_delegated_to_mtf() -> None:
    result = adjusted_components(
        profile=PROFILES["futures_long_rsi_momentum_disabled_v1"],
        components={"momentum": 2.2, "mtf": 3.0},
        snapshot=_snapshot(rsi=60.0),
    )
    assert result == {"momentum": 0.8, "mtf": 3.0}


def test_long_rsi_pullback_map_replaces_late_reward() -> None:
    late = adjusted_components(
        profile=PROFILES["futures_long_rsi_momentum_pullback_v1"],
        components={"momentum": 2.2},
        snapshot=_snapshot(rsi=60.0),
    )
    early = adjusted_components(
        profile=PROFILES["futures_long_rsi_momentum_pullback_v1"],
        components={"momentum": 0.8},
        snapshot=_snapshot(rsi=45.0),
    )
    assert late["momentum"] == 1.0
    assert early["momentum"] == 1.6


def test_long_half_reward_adjustments_preserve_half_of_each_reward() -> None:
    rsi_result = adjusted_components(
        profile=PROFILES["futures_long_rsi_58_65_half_reward_v1"],
        components={"momentum": 2.2},
        snapshot=_snapshot(),
    )
    macd_result = adjusted_components(
        profile=PROFILES["futures_long_macd_alignment_half_reward_v1"],
        components={"momentum": 2.2},
        snapshot=_snapshot(),
    )
    assert rsi_result["momentum"] == 1.5
    assert macd_result["momentum"] == 1.8


def test_short_macd_adjustment_matches_zero_to_point_two_atr_band() -> None:
    result = adjusted_components(
        profile=PROFILES["futures_short_macd_0_02_neutral_v1"],
        components={"momentum": 2.3},
        snapshot=_snapshot(macd=9.0, macd_signal=10.0),
    )
    assert result["momentum"] == 1.4


def test_long_macd_adjustment_matches_point_two_to_point_five_atr_band() -> None:
    profile = PROFILES["futures_long_macd_spread_02_05_neutral_v1"]
    inside = adjusted_components(
        profile=profile,
        components={"momentum": 2.2},
        snapshot=_snapshot(macd=13.0, macd_signal=10.0, atr=10.0),
    )
    outside = adjusted_components(
        profile=profile,
        components={"momentum": 2.2},
        snapshot=_snapshot(macd=11.0, macd_signal=10.0, atr=10.0),
    )
    assert inside["momentum"] == 1.4
    assert outside["momentum"] == 2.2


def test_short_top3_adjustment_changes_three_declared_components() -> None:
    result = adjusted_components(
        profile=PROFILES["futures_short_top3_neutral_v1"],
        components={"momentum": 2.3, "structure": 2.1, "trend": 4.0},
        snapshot=_snapshot(macd=9.0, macd_signal=10.0),
    )
    assert result == {"momentum": 1.4, "structure": 0.8, "trend": 3.0}


def test_adjustment_does_not_fire_outside_declared_band() -> None:
    result = adjusted_components(
        profile=PROFILES["futures_short_structure_15_25_neutral_v1"],
        components={"structure": 2.1},
        snapshot=_snapshot(swing_high=130.0),
    )
    assert result["structure"] == 2.1


def test_conditional_macd_adjustments_require_their_context() -> None:
    atr_candidate = PROFILES["futures_long_macd_neutral_atr_growth_v1"]
    rsi_candidate = PROFILES["futures_long_macd_neutral_rsi58_v1"]
    assert adjusted_components(
        profile=atr_candidate,
        components={"momentum": 2.2},
        snapshot=_snapshot(atr_growth_20=0.04),
    )["momentum"] == 2.2
    assert adjusted_components(
        profile=atr_candidate,
        components={"momentum": 2.2},
        snapshot=_snapshot(atr_growth_20=0.05),
    )["momentum"] == 1.4
    assert adjusted_components(
        profile=rsi_candidate,
        components={"momentum": 2.2},
        snapshot=_snapshot(rsi=57.9),
    )["momentum"] == 2.2
    assert adjusted_components(
        profile=rsi_candidate,
        components={"momentum": 2.2},
        snapshot=_snapshot(rsi=58.0),
    )["momentum"] == 1.4


def test_conditional_macd_rsi_threshold_candidates_are_distinct() -> None:
    rsi55 = PROFILES["futures_long_macd_neutral_rsi55_v1"]
    rsi60 = PROFILES["futures_long_macd_neutral_rsi60_v1"]
    rsi65 = PROFILES["futures_long_macd_neutral_rsi65_v1"]
    snapshot = _snapshot(rsi=60.0)

    assert adjusted_components(
        profile=rsi55,
        components={"momentum": 2.2},
        snapshot=snapshot,
    )["momentum"] == 1.4
    assert adjusted_components(
        profile=rsi60,
        components={"momentum": 2.2},
        snapshot=snapshot,
    )["momentum"] == 1.4
    assert adjusted_components(
        profile=rsi65,
        components={"momentum": 2.2},
        snapshot=snapshot,
    )["momentum"] == 2.2
