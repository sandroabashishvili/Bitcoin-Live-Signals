from unittest.mock import Mock

from platform_v2.spot.services.signal.test_independent_long import context
from platform_v2.spot.services.signal.independent_long_signal_service import IndependentLongSignalService
from platform_v2.spot.domain.models.signal import SignalSide


def test_stronger_short_blocks_buy_without_opening_short():
    components = Mock()
    components.build_long_component_scores.return_value = dict(mtf=4., regime=2., trend=2., momentum=1., orderbook=0., structure=0.)
    components.build_short_component_scores.return_value = dict(mtf=4., regime=2., trend=4., momentum=4., orderbook=3., structure=3.)
    components.atr_spike_block.return_value = False
    d = IndependentLongSignalService(component_service=components).build_signal(context())
    assert d.score >= d.threshold
    assert d.direction_scores['short'] > d.direction_scores['long']
    assert d.side == SignalSide.NO_SIGNAL and d.evaluated_direction == 'SHORT'


def test_late_long_blocked_using_own_direction_history():
    ctx = context(); ctx.latest_candle.close_time_ms = 7*900000
    history = [{'timestamp_ms':i*900000, 'evaluated_direction':'LONG', 'side':'BUY'} for i in range(1,7)]
    d = IndependentLongSignalService().build_signal(ctx, prior_signals=history)
    assert d.side == SignalSide.BUY  # Raw setup retained; permission denies execution.
    assert d.entry_quality['allowed'] is False
    assert d.entry_quality['timing_type'] == 'LATE_EXTENSION'
    assert d.entry_quality['direction_signal_age'] == 7


def test_nontraded_short_is_retained_for_long_flip_classification():
    ctx = context(); ctx.latest_candle.close_time_ms = 900000
    d = IndependentLongSignalService().build_signal(ctx, prior_signals=[
        {'timestamp_ms':1,'evaluated_direction':'SHORT','side':'NO_SIGNAL'}])
    assert d.entry_quality['prior_actionable_side']=='SHORT'
    assert d.entry_quality['timing_type']=='FRESH_FLIP'


def test_current_or_future_history_cannot_age_signal():
    ctx = context()
    d = IndependentLongSignalService().build_signal(ctx, prior_signals=[
        {'timestamp_ms':ctx.latest_candle.close_time_ms+i,'evaluated_direction':'LONG'} for i in range(20)])
    assert d.entry_quality['direction_signal_age']==1


def test_score_preserves_reference_rounding_at_half_cent():
    assert IndependentLongSignalService._score_components(
        dict(mtf=1.,regime=2.,trend=3.,momentum=.5,orderbook=.85,structure=0.))==7.76
