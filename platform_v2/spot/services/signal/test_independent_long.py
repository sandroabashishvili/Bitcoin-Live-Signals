from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import subprocess
import sys

from platform_v2.spot.domain.models.indicator_snapshot import IndicatorSnapshot
from platform_v2.spot.domain.models.orderbook_snapshot import OrderbookSnapshot
from platform_v2.spot.domain.models.signal import SignalSide
from platform_v2.spot.services.signal.independent_long_signal_service import IndependentLongSignalService


def context():
    snap = IndicatorSnapshot('BTCUSDT', '15m', '2026-09-10 12:00:00', 100.,
        rsi=60., macd=2., macd_signal=1., ema50=99., ema200=98., ema50_slope=1.,
        adx=22., plus_di=24., minus_di=20., atr=1., atr_growth_20=0.,
        swing_low=98.8, swing_high=102., kijun=99., resistance_level=102.)
    return SimpleNamespace(symbol='BTCUSDT', timeframe='15m', latest_snapshot=snap,
        latest_candle=SimpleNamespace(close_time_ms=1000), mtf_signals={'5m':'BUY','15m':'BUY','4h':'BUY'},
        mtf_direction='BUY', latest_orderbook=OrderbookSnapshot('BTCUSDT','15m','',120.,100.,.1,.1,'bullish',1))


def test_computes_buy_from_spot_context_without_source_records():
    result = IndependentLongSignalService().build_signal(context())
    assert result.side == SignalSide.BUY
    assert result.source_market == 'spot' and result.source_strategy_version is None
    assert result.source_decision_time is None and result.execution_quote_price is None
    assert result.profit_lock_enabled and result.setup_confidence == min(1., result.score/14.6)


def test_spot_inputs_change_signal_and_never_create_short():
    service = IndependentLongSignalService()
    ctx = context()
    before = service.build_signal(ctx)
    ctx.latest_snapshot = IndicatorSnapshot('BTCUSDT','15m','',100.)
    ctx.mtf_signals = {}; ctx.latest_orderbook = None
    after = service.build_signal(ctx)
    assert before.score != after.score and after.side == SignalSide.NO_SIGNAL


def test_regime_is_not_a_mandatory_filter():
    ctx = context()
    ctx.latest_snapshot = replace(ctx.latest_snapshot, adx=10., plus_di=0., minus_di=20.)
    result = IndependentLongSignalService().build_signal(ctx)
    assert not result.gates.regime
    assert result.score >= result.threshold and result.side == SignalSide.BUY


def test_runtime_default_is_independent_and_persists_local_decision(monkeypatch):
    from platform_v2.spot.services.signal import signal_runtime_service as module
    market = Mock(); market.build_context.return_value = context()
    monkeypatch.setattr(module, 'load_family_rows_all', lambda *_: [])
    writer = Mock(); monkeypatch.setattr(module, 'write_signal_record', writer)
    result = module.SignalRuntimeService(market_context_service=market).run_with_context(
        symbol='BTCUSDT',timeframe='15m',date_iso='2026-09-10')
    assert result.signal.source_market == 'spot'
    writer.assert_called_once()


def test_spot_runtime_imports_with_futures_and_hedge_disabled():
    code = '''
import sys
class BlockOtherSystems:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('platform_v2.futures', 'platform_v2.futures_hedge')):
            raise AssertionError('Spot imported another trading system: '+fullname)
sys.meta_path.insert(0, BlockOtherSystems())
from platform_v2.spot.services.ops.main_cycle.service import MainCycleService
from platform_v2.spot.services.signal.signal_runtime_service import SignalRuntimeService
from platform_v2.spot.services.signal.independent_long_signal_service import IndependentLongSignalService
assert isinstance(SignalRuntimeService()._signal_decision_service, IndependentLongSignalService)
'''
    result = subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
