from platform_v2.futures.domain.short_stop_policy import apply_short_stop_cap
from platform_v2.futures.domain.models.indicator_snapshot import IndicatorSnapshot
from platform_v2.futures.domain.models.signal import SignalSide
from platform_v2.futures.services.trading.futures_sl_tp_service import (
    StopLossTakeProfitService,
)


def test_short_stop_cap_changes_only_declared_atr_band() -> None:
    result = apply_short_stop_cap(
        side="SHORT",
        entry=100.0,
        stop_loss=103.0,
        atr=1.0,
        band_min_atr=2.5,
        band_max_atr=3.5,
        cap_atr=2.5,
    )

    assert result.applied
    assert result.stop_loss == 102.5
    assert result.baseline_stop_atr == 3.0


def test_short_stop_cap_leaves_long_and_outside_band_unchanged() -> None:
    long_result = apply_short_stop_cap(
        side="LONG",
        entry=100.0,
        stop_loss=97.0,
        atr=1.0,
        band_min_atr=2.5,
        band_max_atr=3.5,
        cap_atr=2.5,
    )
    short_result = apply_short_stop_cap(
        side="SHORT",
        entry=100.0,
        stop_loss=102.0,
        atr=1.0,
        band_min_atr=2.5,
        band_max_atr=3.5,
        cap_atr=2.5,
    )

    assert not long_result.applied
    assert long_result.stop_loss == 97.0
    assert not short_result.applied
    assert short_result.stop_loss == 102.0


def test_live_sl_tp_service_applies_cap_but_baseline_replay_can_disable_it() -> None:
    snapshot = IndicatorSnapshot(
        symbol="BTCUSDT",
        timeframe="15m",
        timestamp_text="test",
        price=100.0,
        atr=1.0,
        adx=25.0,
        swing_high=102.8,
        swing_low=90.0,
    )
    active = StopLossTakeProfitService().build_theoretical_setup(
        side=SignalSide.SELL,
        entry_price=100.0,
        snapshot=snapshot,
        confidence=0.5,
    )
    baseline = StopLossTakeProfitService(
        short_stop_cap_enabled=False,
    ).build_theoretical_setup(
        side=SignalSide.SELL,
        entry_price=100.0,
        snapshot=snapshot,
        confidence=0.5,
    )

    assert active is not None
    assert baseline is not None
    assert active.stop_loss == 102.5
    assert baseline.stop_loss > 103.0
    assert active.take_profit == baseline.take_profit
    assert active.rr_ratio > baseline.rr_ratio
    assert active.mode == "adaptive_v2_short_stop_cap_25"
