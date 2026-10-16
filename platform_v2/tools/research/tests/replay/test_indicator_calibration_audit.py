from __future__ import annotations

from types import SimpleNamespace

from platform_v2.tools.research.replay.indicator_calibration_audit import (
    _cohort_stats,
    _feature_row,
)


def _snapshot() -> SimpleNamespace:
    return SimpleNamespace(
        price=110.0,
        rsi=60.0,
        adx=25.0,
        plus_di=30.0,
        minus_di=10.0,
        adx_slope=1.0,
        atr=10.0,
        atr_growth_20=0.1,
        atr_spike=False,
        ema50=100.0,
        ema200=90.0,
        ema50_slope=2.0,
        vwap=105.0,
        macd=4.0,
        macd_signal=2.0,
        swing_low=80.0,
        swing_high=140.0,
        bounce_confirmed=True,
    )


def test_short_features_are_normalized_to_short_direction() -> None:
    row = _feature_row(
        {"side": "SHORT", "net_pnl": 1.0, "date": "2026-07-01"},
        _snapshot(),
        SimpleNamespace(buyers=60.0, sellers=120.0, imbalance=-0.3),
    )

    features = row["features"]
    assert features["directional_di_delta"] == -20.0
    assert features["directional_ema50_distance_atr"] == -1.0
    assert features["directional_orderflow_ratio"] == 2.0
    assert features["directional_orderflow_imbalance"] == 0.3


def test_cohort_stability_requires_both_train_and_test() -> None:
    rows = [
        {"date": f"2026-07-{day:02d}", "net_pnl": 1.0}
        for day in range(1, 7)
    ]

    result = _cohort_stats(rows, "2026-07-04")

    assert result["stability"] == "positive"
