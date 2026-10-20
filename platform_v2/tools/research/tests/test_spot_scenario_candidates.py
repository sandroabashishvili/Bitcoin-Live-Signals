from dataclasses import asdict, replace
from types import SimpleNamespace as NS
import pytest

from platform_v2.shared.backend.market.candle import Candle
from platform_v2.spot.domain.models.indicator_snapshot import IndicatorSnapshot
from platform_v2.tools.research.spot_backtest.candidates import detectors, scenario_votes, CandidateSignalService, SCENARIOS


def bar(i, opening=100., high=102., low=98., close=100., volume=10.):
    return Candle('BTCUSDT', '15m', i*900000, (i+1)*900000-1, opening, high, low, close, volume)


def snap(**kw):
    return IndicatorSnapshot('BTCUSDT', '15m', '2026-08-01 00:14:59', 101.,
        **({'atr': 1., 'ema9': 100., 'ema50': 99., 'ema50_slope': .1, 'adx': 20.,
            'rsi': 55., 'macd': 1., 'macd_signal': .5, 'atr_spike': False} | kw))


def context(bars, s=None):
    return NS(latest_snapshot=s or snap(), recent_candles=bars,
        latest_orderbook=NS(buyers=6., sellers=4.))


@pytest.mark.parametrize('name', SCENARIOS)
def test_each_scenario_has_a_positive_closed_bar_fixture(name):
    bars = [bar(i) for i in range(22)]
    if name == 'pullback':
        bars[-1] = bar(21, opening=100., close=101.)
    elif name == 'breakout':
        bars[-1] = bar(21, opening=101., high=104., close=103., volume=12.)
    elif name == 'reversal':
        bars[-11] = bar(11, opening=104., high=105., close=104.)
        bars[-2] = bar(20, low=97., close=99.)
        bars[-1] = bar(21, opening=99., high=104., close=103.)
    elif name == 'range_bounce':
        bars[-1] = bar(21, opening=98., high=100., low=98., close=99.)
    else:
        bars[-1] = bar(21, opening=98., high=101., low=97., close=99.)
    assert detectors(snap(), bars)[name]
    # None of these bullish setups may be triggered by a bearish decision bar.
    bars[-1] = replace(bars[-1], open_price=bars[-1].high_price)
    assert not detectors(snap(), bars)[name]


def test_insufficient_history_and_invalid_inputs_fail_closed():
    bars = [bar(i) for i in range(22)]
    assert not any(detectors(snap(), bars[:21]).values())
    assert not any(detectors(snap(atr=float('nan')), bars).values())
    assert not any(detectors(snap(atr=0.), bars).values())
    assert not any(detectors(snap(), bars[:-1]+[replace(bars[-1], volume=float('inf'))]).values())


def test_range_and_trend_regime_votes_are_different():
    c = context([bar(i) for i in range(22)], snap(adx=14.))
    _, votes = scenario_votes(c, dict.fromkeys(('5m', '15m', '4h'), c.latest_snapshot))
    assert votes['range_bounce']['regime']
    assert not votes['breakout']['regime']
    c.latest_snapshot = snap(adx=30.)
    _, votes = scenario_votes(c, dict.fromkeys(('5m', '15m', '4h'), c.latest_snapshot))
    assert not votes['range_bounce']['regime'] and votes['breakout']['regime']


def test_missing_timeframes_and_negative_flow_do_not_vote():
    c = context([bar(i) for i in range(22)])
    c.latest_orderbook = NS(buyers=1., sellers=-1.)
    _, votes = scenario_votes(c, {'15m': c.latest_snapshot})
    assert all(not v['mtf'] and not v['orderbook'] for v in votes.values())


@pytest.mark.parametrize('count,expected', [(3, False), (4, True), (6, True)])
def test_equal_vote_threshold_and_no_short_veto(count, expected):
    from platform_v2.spot.domain.models.signal import SignalDecision, GateSnapshot, SignalSide, TheoreticalSetup
    gates = dict(zip(('mtf', 'regime', 'trend', 'momentum', 'orderbook', 'structure'), [i<count for i in range(6)]))
    native = SignalDecision(timestamp_ms=899999, symbol='BTCUSDT', timeframe='15m', side=SignalSide.NO_SIGNAL,
        snapshot_price=101., score=7., threshold=8.5, gates=GateSnapshot(**gates), setup_confidence=.5,
        evaluated_direction='SHORT')
    candidate = CandidateSignalService('votes_existing_v1')
    candidate.native = NS(build_signal=lambda *a, **kw: native,
        _setups=NS(build_theoretical_setup=lambda **kw: TheoreticalSetup(101., 99., 105., 2., 'research')))
    signal = candidate.build_signal(context([bar(i) for i in range(22)]))
    assert (signal.side == SignalSide.BUY) == expected
    assert signal.score == count and signal.setup_confidence == .5
    assert signal.component_weights == dict.fromkeys(gates, 1.)


def test_union_overlaps_emit_one_decision_and_preserve_matches():
    from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide, TheoreticalSetup
    bars = [bar(i) for i in range(22)]
    bars[-1] = bar(21, opening=98., high=104., low=97., close=103., volume=20.)
    c = context(bars)
    native = SignalDecision(timestamp_ms=899999, symbol='BTCUSDT', timeframe='15m', side=SignalSide.NO_SIGNAL,
        snapshot_price=101., score=7., threshold=8.5, setup_confidence=.5)
    candidate = CandidateSignalService('scenarios_votes_v1')
    candidate.snapshots = dict.fromkeys(('5m', '15m', '4h'), c.latest_snapshot)
    candidate.native = NS(build_signal=lambda *a, **kw: native,
        _setups=NS(build_theoretical_setup=lambda **kw: TheoreticalSetup(101., 99., 105., 2., 'research')))
    signal = candidate.build_signal(c)
    assert signal.side == SignalSide.BUY
    assert len(candidate.last_diagnostics['qualified']) >= 2
    assert candidate.last_diagnostics['selected'] == 'pullback'


def test_native_setup_failure_still_blocks_candidate_buy():
    from platform_v2.spot.domain.models.signal import SignalDecision, GateSnapshot, SignalSide
    native = SignalDecision(timestamp_ms=899999, symbol='BTCUSDT', timeframe='15m', side=SignalSide.NO_SIGNAL,
        snapshot_price=101., score=7., threshold=8.5, gates=GateSnapshot(True, True, True, True, True, True), setup_confidence=.5)
    candidate = CandidateSignalService('votes_existing_v1')
    candidate.native = NS(build_signal=lambda *a, **kw: native, _setups=NS(build_theoretical_setup=lambda **kw: None))
    assert candidate.build_signal(context([bar(i) for i in range(22)])).side == SignalSide.NO_SIGNAL


def test_episode_count_is_not_candle_or_position_count_and_resets_at_gaps():
    from platform_v2.tools.research.spot_backtest.compare import episodes
    rows = [{'segment': seg, 'signal': {'side': side}} for seg, side in
        [(1, 'NO_SIGNAL'), (1, 'BUY'), (1, 'BUY'), (1, 'NO_SIGNAL'), (1, 'BUY'), (2, 'BUY')]]
    assert len(episodes(rows)) == 3
    assert sum(r['signal']['side'] == 'BUY' for r in rows) == 4


@pytest.mark.parametrize('active', SCENARIOS)
@pytest.mark.parametrize('detected,passed,expected', [(True, 4, True), (True, 3, False), (False, 6, False)])
def test_isolated_scenarios_cannot_fall_back_to_another_scenario(monkeypatch, active, detected, passed, expected):
    from platform_v2.tools.research.spot_backtest import candidates
    from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide, TheoreticalSetup
    keys = ('mtf', 'regime', 'trend', 'momentum', 'orderbook', 'structure')
    found = dict.fromkeys(SCENARIOS, True) | {active: detected}
    votes = {name: dict.fromkeys(keys, True) for name in SCENARIOS}
    votes[active] = {key: i<passed for i, key in enumerate(keys)}
    monkeypatch.setattr(candidates, 'scenario_votes', lambda *args: (found, votes))
    native = SignalDecision(timestamp_ms=899999, symbol='BTCUSDT', timeframe='15m', side=SignalSide.NO_SIGNAL,
        snapshot_price=101., score=7., threshold=8.5, setup_confidence=.5)
    candidate = CandidateSignalService('scenario_'+active+'_v1')
    candidate.native = NS(build_signal=lambda *a, **kw: native,
        _setups=NS(build_theoretical_setup=lambda **kw: TheoreticalSetup(101., 99., 105., 2., 'research')))
    signal = candidate.build_signal(context([bar(i) for i in range(22)]))
    assert (signal.side == SignalSide.BUY) == expected
    assert candidate.last_diagnostics['active_scenarios'] == [active]
    assert candidate.last_diagnostics['selected'] == (active if expected else None)
    assert signal.setup_confidence == native.setup_confidence
    assert asdict(signal.gates) == votes[active]


def test_unknown_candidate_is_not_silently_run_as_union():
    with pytest.raises(ValueError, match='Unknown research candidate'):
        CandidateSignalService('scenario_typo_v1')


def isolated_trace(active='breakout'):
    votes = dict.fromkeys(('mtf', 'regime', 'trend', 'momentum', 'orderbook', 'structure'), True)
    anchor = {'segment':1, 'timestamp_ms':899999, 'quote_ms':960000,
        'signal':{'side':'BUY', 'setup_confidence':.5},
        'candidate':{'detected':{active:True}, 'scenario_votes':{active:votes}, 'qualified':[active],
            'native_long_score':8., 'native_direction':'LONG'}}
    from copy import deepcopy
    isolated = deepcopy(anchor)
    isolated['candidate'].update(active_scenarios=[active], selected=active, raw_buy=True, votes=votes)
    return isolated, anchor


def test_isolation_report_accepts_unchanged_trace():
    from platform_v2.tools.research.spot_backtest.isolate_compare import validate_isolation
    row, anchor = isolated_trace()
    validate_isolation([row], [anchor], 'breakout')


@pytest.mark.parametrize('change', ('cohort', 'votes', 'mask', 'selection', 'confidence', 'side', 'count'))
def test_isolation_report_rejects_changed_inputs_or_signal_semantics(change):
    from platform_v2.tools.research.spot_backtest.isolate_compare import validate_isolation
    row, anchor = isolated_trace()
    if change == 'cohort': row['timestamp_ms'] += 900000
    elif change == 'votes': row['candidate']['scenario_votes']['breakout']['mtf'] = False
    elif change == 'mask': row['candidate']['active_scenarios'] = ['pullback']
    elif change == 'selection': row['candidate']['selected'] = 'pullback'
    elif change == 'confidence': row['signal']['setup_confidence'] = .9
    elif change == 'side': row['signal']['side'] = 'NO_SIGNAL'
    with pytest.raises(ValueError):
        validate_isolation([] if change == 'count' else [row], [anchor], 'breakout')
