from dataclasses import asdict, replace
import json

from platform_v2.shared.backend.market.candle import Candle
from platform_v2.spot.domain.models.position import ExecutionSetup, PositionRecord, PositionStatus, ExitReason
from platform_v2.spot.domain.models.signal import SignalSide
from platform_v2.spot.services.account.profit_lock import build_profit_lock
from platform_v2.spot.services.account.position_update_service import PositionUpdateService
from platform_v2.spot.services.account.position_state_service import PositionStateService


def position(managed=True):
    setup = ExecutionSetup(100., 90., 120., 2., 100.)
    return PositionRecord('test', 'BTCUSDT', '15m', SignalSide.BUY, PositionStatus.OPEN,
        setup, '2026-09-10 00:00:00', opened_at_ms=0,
        strategy_version='spot-independent-direction-quality-v5',
        position_management=build_profit_lock(setup) if managed else None)


def candle(index, low, high, close):
    return Candle('BTCUSDT', '1m', index*60000, (index+1)*60000-1, 100., high, low, close, 10.)


def test_activation_applies_next_candle_and_survives_serialization_restart():
    update = PositionUpdateService()
    activation = candle(0, 99., 115., 110.)
    armed = update.update_from_candles(position(), [activation])
    assert armed.is_open and armed.position_management['protection_active']
    parsed = PositionStateService._parse_position_row(json.loads(json.dumps(asdict(armed))))
    assert parsed == armed
    # Re-reading the activation candle must not retroactively trigger protection.
    assert update.update_from_candles(parsed, [activation]) == parsed
    closed = update.update_from_candles(parsed, [activation, candle(1, 104., 121., 110.)])
    assert closed.exit_reason == ExitReason.PROFIT_LOCK_HIT
    assert closed.exit_price == 105. and closed.net_pnl == 4.9
    assert not closed.was_force_closed


def test_original_stop_wins_activation_and_target_same_candle():
    result = PositionUpdateService().update_from_candles(position(), [candle(0, 89., 125., 110.)])
    assert result.exit_reason == ExitReason.SL_HIT and result.exit_price == 90.


def test_legacy_positions_keep_fixed_exits():
    update = PositionUpdateService()
    result = update.update_from_candles(position(False), [candle(0, 99., 115., 110.), candle(1, 104., 121., 110.)])
    assert result.exit_reason == ExitReason.TP_HIT


def test_batch_and_incremental_processing_match():
    update = PositionUpdateService()
    candles = [candle(0, 99., 110., 108.), candle(1, 107., 115., 110.), candle(2, 104., 118., 106.)]
    batch = update.update_from_candles(position(), candles)
    incremental = position()
    for bar in candles:
        incremental = update.update_from_candle(incremental, bar)
    assert incremental == batch


def test_gate_accounting_does_not_count_profit_lock_as_sl():
    from platform_v2.spot.services.analytics.strategy_effectiveness.outcome import closed_trade_outcome_key
    result = replace(position(), exit_reason=ExitReason.PROFIT_LOCK_HIT)
    assert closed_trade_outcome_key(result) == 'lock'


def test_gate_table_counts_and_renders_lock_separately():
    from platform_v2.spot.services.analytics.strategy_effectiveness.service import StrategyEffectivenessService
    from platform_v2.spot.dashboard.trade_outcomes.py.renderer import TradeOutcomesPageRenderer
    from platform_v2.spot.services.metrics_system.strategy_content import StrategyPageContentService
    p = replace(position(), status=PositionStatus.CLOSED, exit_reason=ExitReason.PROFIT_LOCK_HIT,
                signal_candle_close_time='2026-09-10 00:14:59', net_pnl=4.9)
    from datetime import datetime, timezone
    stamp = int(datetime(2026,9,10,0,14,59,999000,tzinfo=timezone.utc).timestamp()*1000)
    signal = {'timestamp_ms':stamp, 'symbol':'BTCUSDT', 'timeframe':'15m', 'side':'BUY', 'gates':{'trend':True}}
    payload = StrategyEffectivenessService().build_closed_trade_logic_evaluation(signal_rows=[signal],closed_positions=[p])
    trend = next(row for row in payload['primary_rows'] if row['gate']=='TREND')
    assert trend['lock']==1 and trend['sl']==0 and trend['win_rate']==100.
    assert payload['primary_totals']['lock']==1
    section = StrategyPageContentService.build_trade_outcomes_logic_tables_section(payload)
    rendered = TradeOutcomesPageRenderer()._render_logic_table(
        title='Primary', subtitle='', headers=section['headers'], rows=payload['primary_rows'])
    assert '<th>Lock</th>' in rendered


def test_metrics_keep_old_and_new_versions_separate(monkeypatch):
    from unittest.mock import Mock
    from platform_v2.spot.services.metrics_system.summary_service import MetricsSummaryService
    from platform_v2.spot.services.metrics_system import summary_service as module
    old = replace(position(False), strategy_version='unknown', status=PositionStatus.CLOSED,
                  closed_at='60000', pnl=-1., net_pnl=-1.1, exit_reason=ExitReason.SL_HIT)
    new = replace(position(), status=PositionStatus.CLOSED, closed_at='120000',
                  pnl=5., net_pnl=4.9, exit_reason=ExitReason.PROFIT_LOCK_HIT)
    state = Mock()
    state.load_latest_positions.return_value = [old, new]
    monkeypatch.setattr(module, 'load_family_rows', lambda *args: [])
    monkeypatch.setattr(module, 'load_family_rows_all', lambda *args: [])
    summary = MetricsSummaryService(state).build_summary(date_iso='2026-09-10')
    assert summary['current_strategy_closed_positions'] == 1
    assert summary['current_strategy_net_pnl'] == 4.9
    assert summary['total_net_pnl'] == 3.8
    assert summary['profit_lock_hits'] == 1 and summary['sl_hits'] == 1
