from platform_v2.futures.services.simulation.entry_quality_service import (
    FuturesEntryQualityService,
)
from platform_v2.futures.services.permission.futures_permission_decision_service import (
    FuturesPermissionDecisionService,
)


def _row(timestamp_ms: int, side: str) -> dict[str, object]:
    return {"timestamp_ms": timestamp_ms, "side": side}


def test_live_service_does_not_call_same_side_reentry_a_flip() -> None:
    decision = FuturesEntryQualityService().evaluate(
        signal_side="SHORT",
        timestamp_ms=400,
        prior_signals=[
            _row(100, "SHORT"),
            _row(200, "NO_SIGNAL"),
            _row(300, "NO_SIGNAL"),
        ],
    )
    assert decision.allowed
    assert decision.timing_type == "FRESH_REENTRY"
    assert decision.prior_actionable_side == "SHORT"


def test_shadow_service_holds_first_short_flip_for_confirmation() -> None:
    decision = FuturesEntryQualityService(
        flip_confirmation_required_sides=("SHORT",),
    ).evaluate(
        signal_side="SHORT",
        timestamp_ms=300,
        prior_signals=[_row(100, "LONG"), _row(200, "NO_SIGNAL")],
    )
    assert not decision.allowed
    assert decision.timing_type == "FRESH_FLIP"
    assert decision.prior_actionable_side == "LONG"
    assert decision.flip_confirmation_status == "PENDING_FLIP"
    assert decision.reason == "flip_confirmation_pending"


def test_shadow_service_allows_short_flip_on_next_closed_candle() -> None:
    step = 15 * 60 * 1000
    decision = FuturesEntryQualityService(
        flip_confirmation_required_sides=("SHORT",),
    ).evaluate(
        signal_side="SHORT",
        timestamp_ms=2 * step,
        prior_signals=[_row(0, "LONG"), _row(step, "SHORT")],
    )
    assert decision.allowed
    assert decision.timing_type == "FRESH_FLIP"
    assert decision.flip_confirmation_status == "CONFIRMED_FLIP"


def test_live_service_does_not_delay_long_flip() -> None:
    decision = FuturesEntryQualityService().evaluate(
        signal_side="LONG",
        timestamp_ms=300,
        prior_signals=[_row(100, "SHORT"), _row(200, "NO_SIGNAL")],
    )
    assert decision.allowed
    assert decision.flip_confirmation_status == "UNFILTERED_FLIP"


def test_main_strategy_delays_first_short_flip() -> None:
    decision = FuturesEntryQualityService().evaluate(
        signal_side="SHORT",
        timestamp_ms=300,
        prior_signals=[_row(100, "LONG"), _row(200, "NO_SIGNAL")],
    )
    assert not decision.allowed
    assert decision.flip_confirmation_status == "PENDING_FLIP"
    assert decision.reason == "flip_confirmation_pending"


def test_permission_keeps_specific_flip_pending_reason() -> None:
    decision = FuturesPermissionDecisionService().evaluate(
        signal_side="SHORT",
        entry_price=100.0,
        stop_loss=110.0,
        leverage=5,
        order_notional_usdt=100.0,
        available_balance=1000.0,
        current_open_exposure=0.0,
        last_entry_price=None,
        entry_quality_ok=False,
        entry_quality_reason="flip_confirmation_pending",
    )
    assert not decision.allowed
    assert decision.reason == "flip_confirmation_pending"


def _clean_plan(ts):
    return {'allowed': True, 'alignment': 'IN_ZONE', 'plan_timestamp_ms': ts,
            'plan_location': {'short_entry_state': 'CLEAN', 'ema9_distance_atr': -0.2,
                              'vwap_distance_atr': -0.1, 'distance_to_swing_low_atr': 1.0}}


def test_mature_short_requires_current_clean_price_zone_not_age_alone():
    step = 900000
    history = [_row(i*step, 'SHORT') for i in range(13)]
    service = FuturesEntryQualityService()
    decision = service.evaluate(signal_side='SHORT', timestamp_ms=13*step,
                                prior_signals=history, market_plan_permission=_clean_plan(13*step))
    assert decision.allowed
    assert decision.timing_type == 'MATURE_DIRECTION'
    assert decision.direction_signal_age == 14
    for plan in ({}, _clean_plan(12*step), {**_clean_plan(13*step), 'allowed': False},
                 {**_clean_plan(13*step), 'plan_location': {'short_entry_state': 'CLEAN'}},
                 {**_clean_plan(13*step), 'plan_location': {**_clean_plan(13*step)['plan_location'], 'short_entry_state': 'EXTENDED_OR_SUPPORT'}}):
        assert not service.evaluate(signal_side='SHORT', timestamp_ms=13*step,
                                    prior_signals=history, market_plan_permission=plan).allowed


def test_neutral_candle_does_not_bypass_mature_short_protection():
    step = 900000
    history = [_row(i*step, 'SHORT') for i in range(13)] + [_row(13*step, 'NO_SIGNAL')]
    decision = FuturesEntryQualityService().evaluate(signal_side='SHORT',timestamp_ms=14*step,
                                                     prior_signals=history)
    assert not decision.allowed
    assert decision.direction_signal_age == 14
    assert decision.reason == 'short_entry_location_unconfirmed'


def test_gap_waits_one_observed_candle_and_discards_stale_age():
    step = 900000
    history = [_row(i*step, 'SHORT') for i in range(13)]
    service = FuturesEntryQualityService()
    decision = service.evaluate(signal_side='SHORT',timestamp_ms=30*step,prior_signals=history,
                                market_plan_permission=_clean_plan(30*step))
    assert not decision.allowed
    assert decision.reason == 'entry_history_gap'
    history.append(_row(30*step,'SHORT'))
    confirmed = service.evaluate(signal_side='SHORT',timestamp_ms=31*step,prior_signals=history)
    assert confirmed.allowed
    assert confirmed.direction_signal_age == 2


def test_mature_long_policy_is_unchanged():
    history = [_row(i*900000,'LONG') for i in range(13)]
    result=FuturesEntryQualityService().evaluate(signal_side='LONG',timestamp_ms=13*900000,prior_signals=history)
    assert not result.allowed
    assert result.reason == 'entry_quality_block'
