"""Regression tests for shared adaptive SL/TP calculations."""

from platform_v2.shared.backend.trading import (
    SlTpInputs,
    compute_stop_loss,
    compute_take_profit,
)


def test_long_sl_tp_stays_on_correct_sides_of_entry() -> None:
    inputs = SlTpInputs(
        side="long",
        entry=100_000.0,
        atr=1_000.0,
        fee_buffer_pct=0.0006,
        swing_low=98_500.0,
        resistance_level=104_000.0,
        confidence=0.6,
    )

    stop = compute_stop_loss(inputs)
    take = compute_take_profit(inputs, risk=stop.risk)

    assert stop.stop_loss < inputs.entry < take.take_profit
    assert take.rr_ratio >= inputs.min_effective_rrr_after_clamp


def test_short_sl_tp_stays_on_correct_sides_of_entry() -> None:
    inputs = SlTpInputs(
        side="short",
        entry=100_000.0,
        atr=1_000.0,
        fee_buffer_pct=0.0006,
        swing_high=101_500.0,
        liquidity_zone=96_000.0,
        liquidity_tolerance=5_000.0,
        confidence=0.6,
    )

    stop = compute_stop_loss(inputs)
    take = compute_take_profit(inputs, risk=stop.risk)

    assert take.take_profit < inputs.entry < stop.stop_loss
    assert take.rr_ratio >= inputs.min_effective_rrr_after_clamp
