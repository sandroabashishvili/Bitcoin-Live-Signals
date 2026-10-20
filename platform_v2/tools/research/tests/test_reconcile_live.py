import pytest
from platform_v2.tools.research.spot_backtest.reconcile_live import millis, position_stamp, closed_by, summary_positions, differing_components


def position(opened,closed=None,pnl=0.):
    return {'opened_at_ms':opened,'closed_at':str(closed) if closed is not None else None,
        'status':'CLOSED' if closed is not None else 'OPEN','net_pnl':pnl}


def test_cutoff_does_not_use_future_known_closures():
    before=position(100,200,1.)
    after=position(150,400,-2.)
    opened=position(180)
    assert closed_by(before,300)
    assert not closed_by(after,300)
    assert not closed_by(opened,300)
    s=summary_positions([before,after,opened,position(500,600,10.)],100,300)
    assert s=={'opened':3,'closed_by_cutoff':1,'open_at_cutoff':2,'closed_net_USDT':1.}


def test_ledger_second_precision_joins_actual_candle_last_millisecond():
    p={'signal_candle_close_time':'2026-09-13 19:29:59'}
    assert position_stamp(p)==millis('2026-09-13T19:29:59.999+00:00')
    assert position_stamp({}) is None


def test_component_mismatch_does_not_blame_other_components():
    a={'mtf':2.,'orderbook':2.5,'trend':2.3}
    b={'mtf':2.,'orderbook':0.,'trend':2.3}
    assert differing_components(a,b)==['orderbook']
    assert differing_components(a,a)==[]
    assert differing_components({'mtf':0.},{})==['mtf']
