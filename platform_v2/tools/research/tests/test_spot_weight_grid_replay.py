from platform_v2.tools.research.replay.spot_weight_grid_replay import (
    _candidate_row,
    spot_profiles,
)


def test_spot_grid_changes_only_requested_component() -> None:
    profiles = spot_profiles(
        multipliers=(0.5, 1.5),
        components=("momentum",),
    )
    baseline, half, one_and_half = profiles

    assert len(profiles) == 3
    assert half.weights["momentum"] == baseline.weights["momentum"] * 0.5
    assert one_and_half.weights["momentum"] == baseline.weights["momentum"] * 1.5
    assert half.weights["trend"] == baseline.weights["trend"]


def test_spot_candidate_week_counts_read_all_bucket_stats() -> None:
    baseline_profile = {
        "weights": {
            "mtf": 1.0,
            "regime": 1.0,
            "trend": 1.0,
            "momentum": 1.0,
            "orderbook": 1.0,
            "structure": 1.0,
        }
    }
    profile = {
        "profile_id": "candidate",
        "weights": {**baseline_profile["weights"], "regime": 1.2},
    }
    baseline_portfolio = {
        "closed_stats": {"net_pnl": -2.0},
        "chronological_train": {"net_pnl": -1.0},
        "chronological_test": {"net_pnl": -1.0},
    }
    payload = {
        "profile": profile,
        "actionable_signals": 2,
        "portfolio": {
            "opened_positions": 2,
            "closed_stats": {"net_pnl": 1.0, "max_sequential_drawdown": 0.5},
            "chronological_train": {"net_pnl": 0.4},
            "chronological_test": {"net_pnl": 0.6},
            "rolling_7d": [
                {"all": {"net_pnl": 0.4}},
                {"all": {"net_pnl": -0.2}},
            ],
        },
    }

    row = _candidate_row(
        profile=profile,
        payload=payload,
        baseline_profile=baseline_profile,
        baseline_portfolio=baseline_portfolio,
    )

    assert row["positive_weeks"] == 1
    assert row["negative_weeks"] == 1
