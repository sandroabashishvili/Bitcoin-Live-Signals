from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from platform_v2.shared.backend.market import MarketQuote
from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide
from platform_v2.spot.services.permission.signal_permission_runtime_service import SignalPermissionRuntimeService
from platform_v2.spot.services.signal.signal_runtime_service import SignalRuntimeResult


def runtime(monkeypatch, *, balance=3000., quote_error=False):
    signal = SignalDecision(1000, 'BTCUSDT', '15m', SignalSide.BUY, 69000., 10., 8.5,
        source_market='spot', profit_lock_enabled=True,
        strategy_version='spot-independent-direction-quality-v5', setup_confidence=10/14.6)
    context = SimpleNamespace(latest_snapshot=SimpleNamespace(atr=0.))
    source = Mock()
    source.run_with_context.return_value = SignalRuntimeResult(context, signal)
    portfolio = Mock()
    portfolio.build_state.return_value = SimpleNamespace(available_balance=balance,
        current_open_exposure=0., open_positions_count=0, last_entry_price=None)
    state = Mock()
    state.load_open_positions.return_value = []
    quote = Mock()
    if quote_error:
        quote.fetch.side_effect = RuntimeError('quote offline')
    else:
        quote.fetch.return_value = MarketQuote(symbol='BTCUSDT', market_type='spot',
            price=70000., observed_at_ms=2000, source='test_spot_quote')
    service = SignalPermissionRuntimeService(signal_runtime_service=source,
        portfolio_state_service=portfolio, position_state_service=state, quote_service=quote)
    monkeypatch.setattr(service, '_buy_entry_location_ok', lambda **kwargs: True)
    monkeypatch.setattr(service._position_runtime_service, '_next_position_id', lambda: 'SPOT-test')
    writes = {}
    for module, name in [
        ('permission.signal_permission_runtime_service', 'write_signal_record'),
        ('permission.signal_permission_runtime_service', 'write_order_record'),
        ('permission.denied_entry_runtime_service', 'write_denied_entry_record'),
        ('account.position_runtime_service', 'write_position_record'),
    ]:
        writes[name] = Mock()
        monkeypatch.setattr(f'platform_v2.spot.services.{module}.{name}', writes[name])
    return service, quote, writes


def test_paper_entry_uses_spot_quote_and_persists_source_and_management(monkeypatch):
    service, quote, writes = runtime(monkeypatch)
    result = service.run_for_symbol(symbol='BTCUSDT', timeframe='15m', date_iso='2026-09-10')
    quote.fetch.assert_called_once_with(symbol='BTCUSDT', market_type='spot')
    assert result.permission.is_allowed
    assert result.position.execution.entry_price == 70000.
    assert result.position.execution.position_size == 100.
    assert result.position.source_market == 'spot'
    assert result.position.source_strategy_version is None
    assert result.position.position_management['policy'] == 'long_profit_lock_70_25'
    assert result.signal.execution_quote_time_ms == 2000
    assert result.signal.execution_quote_source == 'test_spot_quote'
    assert writes['write_signal_record'].call_args.kwargs['signal'] == result.signal
    writes['write_position_record'].assert_called_once()


@pytest.mark.parametrize('mode', ['capital', 'quote'])
def test_spot_capital_and_quote_failure_prevent_any_entry(monkeypatch, mode):
    service, quote, writes = runtime(monkeypatch, balance=0. if mode == 'capital' else 3000.,
                                    quote_error=mode == 'quote')
    result = service.run_for_symbol(symbol='BTCUSDT', timeframe='15m', date_iso='2026-09-10')
    assert not result.permission.is_allowed
    assert result.position is None
    writes['write_order_record'].assert_not_called()
    writes['write_position_record'].assert_not_called()
    assert result.denied_entry is not None


def test_entry_quality_denial_prevents_order_and_is_persisted(monkeypatch):
    from dataclasses import replace
    service, quote, writes = runtime(monkeypatch)
    bundle = service._signal_runtime_service.run_with_context.return_value
    service._signal_runtime_service.run_with_context.return_value = replace(bundle,
        signal=replace(bundle.signal, entry_quality={'allowed':False,'reason':'entry_quality_block'}))
    result = service.run_for_symbol(symbol='BTCUSDT',timeframe='15m',date_iso='2026-09-10')
    assert result.permission.reason=='entry_quality_block'
    assert result.permission.checks.entry_quality is False
    writes['write_order_record'].assert_not_called()
    assert result.denied_entry.denial_reason.value=='entry_quality_block'


def test_position_slots_are_enforced_without_weak_position_block():
    from platform_v2.spot.services.permission.permission_decision_service import PermissionDecisionService
    signal = SignalDecision(1,'BTCUSDT','15m',SignalSide.BUY,100.,10.,8.5)
    service = PermissionDecisionService()
    assert service.evaluate(signal,100.,available_balance=3000.,weak_open_position_active=True).is_allowed
    assert service.evaluate(signal,100.,available_balance=3000.,open_positions_count=9).reason=='position_slots_block'


def test_exact_two_hour_cooldown_boundary_uses_fill_milliseconds(monkeypatch):
    service, _, _ = runtime(monkeypatch)
    service._position_state_service.load_open_positions.return_value = [SimpleNamespace(
        opened_at_ms=1000, opened_at='1970-01-01 00:00:01', unrealized_pnl=0.,
        execution=SimpleNamespace(entry_price=90.,position_size=100.))]
    signal=SignalDecision(1,'BTCUSDT','15m',SignalSide.BUY,100.,10.,8.5)
    flags=service._derive_permission_flags(date_iso='2026-09-10', signal=signal,
        live_entry_price=100., decision_timestamp_ms=7201000)
    assert not flags.cooldown_active


def test_weak_peer_cannot_force_close_other_positions():
    from platform_v2.spot.services.account.position_batch_update_service import PositionBatchUpdateService
    service=PositionBatchUpdateService()
    assert service._apply_minus_rule_force_closes(date_iso='2026-09-10',
        original_open_positions=[object()], already_updated_positions=[])==[]
