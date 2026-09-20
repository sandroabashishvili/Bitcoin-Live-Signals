from platform_v2.tools.research.replay.portfolio_replay_features import (
    exit_geometry_features,
)


def test_exit_geometry_is_direction_neutral() -> None:
    long = exit_geometry_features(
        entry=100.0,
        stop_loss=98.0,
        take_profit=104.0,
        atr=2.0,
    )
    short = exit_geometry_features(
        entry=100.0,
        stop_loss=102.0,
        take_profit=96.0,
        atr=2.0,
    )

    assert long == short
    assert long == {
        "stop_distance_atr": 1.0,
        "target_distance_atr": 2.0,
        "effective_rr": 2.0,
    }


def test_exit_geometry_handles_missing_atr_without_losing_rr() -> None:
    result = exit_geometry_features(
        entry=100.0,
        stop_loss=98.0,
        take_profit=103.0,
        atr=None,
    )

    assert result["stop_distance_atr"] is None
    assert result["target_distance_atr"] is None
    assert result["effective_rr"] == 1.5
