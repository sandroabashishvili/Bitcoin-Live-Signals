from types import SimpleNamespace as NS
import pytest
from platform_v2.tools.research.spot_backtest.pullback_audit import pullback_features, forward_change, aggregate


def fixtures():
    bars = [NS(close_time_ms=i*900000+899999, low_price=99., high_price=103., close_price=101.) for i in range(5)]
    snapshots = {b.close_time_ms:NS(ema9=98.,atr=2.,rsi=55.,adx=20.) for b in bars}
    snapshots[bars[-1].close_time_ms].ema9=100.
    bars[-1].close_price=102.
    return bars,snapshots


def test_own_historical_ema_contact_differs_from_current_ema_contact():
    bars,snapshots=fixtures()
    # Original detector's reference: prior lows <= CURRENT EMA9, despite no
    # contact with each bar's OWN EMA9. Audit records, not changes, this distinction.
    assert min(b.low_price for b in bars[-4:-1]) <= snapshots[bars[-1].close_time_ms].ema9
    flags=pullback_features(bars,snapshots)
    assert flags['no_prior_own_ema9_touch'] and flags['no_prior_down_close']
    assert not flags['close_recross_ema9']
    assert flags['distance_above_ema9_ATR']==1.


def test_recross_and_prior_down_close_are_not_the_same_as_bullish_current_bar():
    bars,snapshots=fixtures()
    bars[-2].close_price=99.
    snapshots[bars[-2].close_time_ms].ema9=100.
    flags=pullback_features(bars,snapshots)
    assert flags['close_recross_ema9'] and not flags['no_prior_down_close']


def test_forward_exact_horizon_no_missing_minutes_or_segment_crossing():
    stamps=[i*60000+59999 for i in range(60)]
    prices=dict.fromkeys(stamps,101.)
    assert forward_change(0,100.,1,stamps[-1],stamps,prices)==pytest.approx(1.)
    assert forward_change(0,100.,1,stamps[-1]-1,stamps,prices) is None
    assert forward_change(0,100.,1,stamps[-1],stamps[:30]+stamps[31:],prices) is None
    assert forward_change(0,100.,1,stamps[-1],stamps[1:],prices) is None
    with pytest.raises(ValueError):forward_change(0,100.,0,stamps[-1],stamps,prices)


def test_forward_diagnostic_can_be_positive_after_losing_trade():
    records=[{'status':'CLOSED','net_pnl':-.5,'exit_reason':'sl_hit',
        'forward_close_change_pct':{'1h':1.,'4h':None,'12h':-1.}},
        {'status':'OPEN','net_pnl':10.,'exit_reason':None,
        'forward_close_change_pct':{'1h':None,'4h':None,'12h':None}}]
    summary=aggregate(records)
    assert summary['closed_net_USDT']==-.5 and summary['open']==1
    assert summary['forward_NOT_trade_PnL']['1h']['positive']==1
    assert summary['forward_NOT_trade_PnL']['1h']['excluded']==1
    assert summary['forward_NOT_trade_PnL']['4h']['mean_pct'] is None
