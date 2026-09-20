from platform_v2.tools.research.replay.candidate_exit_policies import adjust_exit_levels
from platform_v2.tools.research.replay.candidate_profiles import PROFILES


def test_short_mid_stop_candidates_change_only_declared_band() -> None:
    cap = adjust_exit_levels(
        profile=PROFILES["futures_short_mid_stop_cap_25_v1"],
        side="SHORT",
        entry=100.0,
        stop_loss=103.0,
        take_profit=94.0,
        atr=1.0,
    )
    floor = adjust_exit_levels(
        profile=PROFILES["futures_short_mid_stop_floor_35_v1"],
        side="SHORT",
        entry=100.0,
        stop_loss=103.0,
        take_profit=94.0,
        atr=1.0,
    )

    assert cap.stop_loss == 102.5
    assert floor.stop_loss == 103.5
    assert cap.take_profit == floor.take_profit == 94.0


def test_short_rr_candidate_moves_only_target() -> None:
    result = adjust_exit_levels(
        profile=PROFILES["futures_short_rr_20_22_target_18_v1"],
        side="SHORT",
        entry=100.0,
        stop_loss=102.0,
        take_profit=95.8,
        atr=1.0,
    )

    assert result.stop_loss == 102.0
    assert result.take_profit == 96.4
    assert result.applied_policy == "short_rr_20_22_target_18"


def test_exit_candidate_does_not_change_long() -> None:
    result = adjust_exit_levels(
        profile=PROFILES["futures_short_mid_stop_cap_25_v1"],
        side="LONG",
        entry=100.0,
        stop_loss=97.0,
        take_profit=106.0,
        atr=1.0,
    )

    assert result.stop_loss == 97.0
    assert result.take_profit == 106.0
    assert result.applied_policy is None
