import json,sqlite3
import pytest
from platform_v2.tools.research.spot_backtest.dataset import parse_klines,segments,create_schema,insert_candle,add_public_flow,coverage
from platform_v2.tools.research.spot_backtest.engine import contiguous_tail,eligibility,validate_account_segments


def row(start=0):
    return {'timestamp':start,'close_time':start+899999,'open':100.,'high':102.,'low':99.,'close':101.,'volume':10.}


@pytest.mark.parametrize('factor',[1,1000])
def test_public_klines_ms_and_microseconds(factor):
    start=1735689600000;end=start+899999
    cells=[start*factor,100,102,99,101,10,(end+1)*factor-1,1000,20,7,700,0]
    candle,flow=parse_klines((','.join(map(str,cells))+'\n').encode())[0]
    assert candle==row(start)
    assert flow['buyers']==7 and flow['sellers']==3 and flow['raw_trade_count']==20


@pytest.mark.parametrize('cells',[
    '0,100,102,99,101,10,899999,1000,20,11,0,0',
    '0,100,102,99,101,10,899999,1000,20,nan,0,0',
    '1,100,102,99,101,10,900000,1000,20,7,0,0',
    '0,100,98,99,101,10,899999,1000,20,7,0,0',
    '0,100,102,99,101,10,1,1000,20,7,0,0',
])
def test_invalid_public_rows_rejected(cells):
    with pytest.raises(ValueError):parse_klines(cells.encode())


def test_conflicting_sources_recorded_without_overwrite():
    db=sqlite3.connect(':memory:');create_schema(db)
    insert_candle(db,'15m',row(),'new')
    insert_candle(db,'15m',row()|{'close':100.5},'old')
    assert json.loads(db.execute('SELECT payload FROM candles').fetchone()[0])['close']==101
    assert db.execute('SELECT count(*) FROM conflicts').fetchone()[0]==1


def test_public_flow_must_match_local_ohlcv():
    db=sqlite3.connect(':memory:');create_schema(db);insert_candle(db,'15m',row(),'local')
    flow={'window_end_ms':899999,'buyers':7,'sellers':3}
    result=add_public_flow(db,[(row()|{'volume':11},flow)],'public')
    assert result['conflicting_local_candles']==1 and db.execute('SELECT count(*) FROM flow').fetchone()[0]==0


def test_gaps_are_not_filled_and_warmup_does_not_cross_gap():
    assert segments([0,1,2,4,5],1)==[[0,1,2],[4,5]]
    assert contiguous_tail([0,1,2,4,5],5,1,3) is None
    assert contiguous_tail([0,1,2,4,5],5,1,2)==5


def test_coverage_records_exact_missing_intervals():
    db=sqlite3.connect(':memory:');create_schema(db)
    for start in (0,1800000):insert_candle(db,'15m',row(start),'local')
    assert coverage(db)['15m']['missing_intervals']==1


def test_eligibility_requires_closed_higher_tf_exact_quote_and_continuous_minutes():
    close=14399999
    warm={'5m':{close},'15m':{close},'4h':{close}}
    quote=close+60001;minutes=list(range(quote-16*60000+59999,quote,60000))
    assert eligibility(close,{close},warm,minutes,{quote}) is None
    assert eligibility(close,{close},warm,minutes,set())=='missing_entry_or_exit_minutes'
    assert eligibility(close,{close},warm,minutes[:3]+minutes[4:],{quote})=='missing_entry_or_exit_minutes'
    assert eligibility(close,set(),warm,minutes,{quote})=='missing_verified_flow'
    assert eligibility(close,{close},warm|{'4h':{close+14400000}},minutes,{quote})=='indicator_warmup_or_gap'


def test_native_indicators_do_not_change_when_future_bars_are_appended():
    from platform_v2.shared.backend.market.candle import Candle
    from platform_v2.spot.services.analytics.indicator_snapshot_builder import IndicatorSnapshotBuilder
    bars=[Candle('BTCUSDT','15m',i*900000,(i+1)*900000-1,100+i*.05,102+i*.05,99+i*.05,101+i*.05,10.) for i in range(210)]
    builder=IndicatorSnapshotBuilder()
    prefix=builder.build_rows(symbol='BTCUSDT',timeframe='15m',candles=bars[:200])
    full=builder.build_rows(symbol='BTCUSDT',timeframe='15m',candles=bars)
    assert prefix==full[:len(prefix)]


@pytest.mark.parametrize('groups', [[], [[1,2],[3]], [[1,2]], [[1,2,3,4]]])
def test_continuous_experiment_refuses_missing_cycles_or_account_resets(groups):
    with pytest.raises(ValueError,match='exactly one'):
        validate_account_segments(groups,{'expected_cycles':3})


def test_single_continuous_account_has_declared_cycle_count():
    validate_account_segments([[1,2,3]],{'expected_cycles':3})
    validate_account_segments([[1],[3]],None)  # Legacy segmented experiments remain explicit.
