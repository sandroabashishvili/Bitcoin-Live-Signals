import json
from pathlib import Path

import pytest

from platform_v2.tools.research.portfolio_lab_support import MemoryRuntimeStore, PortfolioReplay, required_read, compare_fields
from platform_v2.tools.research import signal_lab


def test_private_persistence_upsert_and_dates(tmp_path):
    store = MemoryRuntimeStore(tmp_path)
    original = {'timestamp_ms': 1, 'side': 'LONG'}
    store.append_daily_row(family_name='signals', date_iso='day1', row=original)
    original['side'] = 'SHORT'
    assert store.load_family_rows_all(family_name='signals')[0]['side'] == 'LONG'
    store.upsert_daily_row(family_name='signals', date_iso='day1', row=original, match_keys=('timestamp_ms',))
    store.upsert_daily_row(family_name='signals', date_iso='day2', row=original, match_keys=('timestamp_ms',))
    assert len(store.load_family_rows_all(family_name='signals')) == 2
    assert store.load_family_rows(family_name='signals', date_iso='day1')[0]['side'] == 'SHORT'


def test_missing_captured_read_fails_without_live_fallback():
    with pytest.raises(ValueError, match='Missing'):
        required_read(lambda ref: None, {}, 'state')


def test_captured_return_unwrapped_exactly_once():
    reads = {('read', '{"family":"signals"}'): {'chunks': ['chunk']}}
    value = [{'timestamp_ms': 1}]
    assert required_read(lambda ref: [value], reads, 'read', family='signals') == value
    with pytest.raises(ValueError, match='one captured'):
        required_read(lambda ref: [value, value], reads, 'read', family='signals')


def test_permission_parity_compares_checks_not_just_allowance():
    assert compare_fields({'status': 'DENIED', 'checks': {'capital': False}},
                          {'status': 'DENIED', 'checks': {'capital': True}}, ('status', 'checks')) == ['checks']


@pytest.mark.parametrize('model,name', [('bad', 'baseline'), ('observed', 'candidate')])
def test_unsupported_model_or_observed_candidate(tmp_path, monkeypatch, model, name):
    monkeypatch.setattr(signal_lab, 'verify', lambda p: {})
    with pytest.raises(ValueError):
        signal_lab.portfolio_run(tmp_path, name=name, model=model)


def test_full_candidate_requires_verified_observed_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(signal_lab, 'verify', lambda p: {})
    monkeypatch.setattr(signal_lab, '_verify_run', lambda *args: None)
    path = tmp_path / 'portfolio_runs/baseline-observed'
    path.mkdir(parents=True)
    (path / 'portfolio.json').write_text(json.dumps({'historical_parity_ok': False}))
    (path / 'result.json').write_text(json.dumps({'limit': 0}))
    with pytest.raises(ValueError, match='historically verified'):
        signal_lab.portfolio_run(tmp_path, model='next-minute')


def test_changed_signal_changes_later_positions_and_permissions(tmp_path, monkeypatch):
    """Same production execution rules, different first signal, evolving accounts."""
    from types import SimpleNamespace
    from platform_v2.futures.config import load_execution_profile
    from platform_v2.futures.domain.models.signal import SignalDecision, SignalSide
    from platform_v2.futures.domain.models.position import ExecutionSetup
    from platform_v2.shared.backend.market import MarketQuote
    from platform_v2.futures.services.simulation.directional_futures_simulation_service import DirectionalFuturesSimulationService
    from platform_v2.futures.services.simulation import metrics_service, state_store, common
    from platform_v2.futures.services.simulation import directional_futures_simulation_service as simulation
    # Restore global clock patches after this synthetic adapter test.
    for module in (metrics_service, state_store, common, simulation):
        monkeypatch.setattr(module, 'utc_now_ms', module.utc_now_ms)
    monkeypatch.setattr(metrics_service, 'datetime', metrics_service.datetime)

    def make(first):
        replay = PortfolioReplay.__new__(PortfolioReplay)
        replay.clock = 1790575221206
        replay.profile = load_execution_profile()
        replay.indicator = {}
        replay.store = MemoryRuntimeStore(tmp_path)
        replay.engine = DirectionalFuturesSimulationService()
        replay.state = state_store.FuturesSimulationStateStore()._default_state()
        replay._install_adapters()
        replay.engine._market_context_service = SimpleNamespace(build_context=lambda **kw: object())
        replay.engine._build_execution_setup = lambda **kw: None if kw['decision'].selected_direction == 'NO_SIGNAL' else ExecutionSetup(
            entry_price=100, stop_loss=98, take_profit=104, rr_ratio=2, position_size=100, mode='synthetic')
        sides = iter((first, 'LONG'))
        replay.engine._build_signal_decision = lambda **kw: SignalDecision(
            timestamp_ms=kw['latest_ts'], symbol='BTCUSDT', timeframe='15m',
            side=SignalSide.BUY if (side := next(sides)) == 'LONG' else SignalSide.NO_SIGNAL,
            selected_direction=side, snapshot_price=100, score=10 if side == 'LONG' else 0, threshold=8.5)
        replay.engine._execution_quote = lambda **kw: (MarketQuote('BTCUSDT', 'futures', 100, replay.clock), None) if kw['signal_side'] == 'LONG' else (None, None)
        return replay

    base, test = make('LONG'), make('NO_SIGNAL')
    for replay in (base, test):
        for step in range(2):
            replay.clock = 1790575221206 + step * 900000
            t = 1790575199999 + step * 900000
            candles = [{'timestamp': t - (24 - i) * 900000 - 899999, 'close_time': t - (24 - i) * 900000,
                        'open': 100, 'high': 101, 'low': 99, 'close': 100} for i in range(25)]
            replay.store.candles = {'15m': candles, '1m': candles}
            replay.engine.run(profile=replay.profile, date_iso='2026-09-28')
    base_rows = base.store.load_family_rows_all(family_name='futures_signals')
    test_rows = test.store.load_family_rows_all(family_name='futures_signals')
    assert base_rows[0]['permission_status'] == 'ALLOWED'
    assert test_rows[0]['permission_status'] == 'DENIED'
    assert base_rows[1]['permission_status'] == 'DENIED'
    assert test_rows[1]['permission_status'] == 'ALLOWED'
    assert base.state['open_positions'][0]['opened_at_ms'] != test.state['open_positions'][0]['opened_at_ms']


def test_failed_worker_console_is_retained(tmp_path):
    import sys
    code = signal_lab.launch_recorded([sys.executable, '-c', 'print("synthetic replay failure"); raise SystemExit(2)'], tmp_path)
    assert code == 2
    assert (tmp_path / 'console.log').read_text().strip() == 'synthetic replay failure'
