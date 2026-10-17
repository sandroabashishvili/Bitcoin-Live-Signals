from copy import deepcopy
import pytest
from platform_v2.tools.research.spot_backtest.recover_gap import START, EXPECTED, validate_recovery
from platform_v2.tools.research.spot_backtest.dataset import parse_klines


def fixtures():
    day=START//86400000*86400000
    public=[({'timestamp':stamp,'close_time':stamp+59999,'open':100.,'high':102.,
        'low':99.,'close':101.,'volume':10.},{}) for stamp in range(day,day+86400000,60000)]
    existing={r['timestamp']:dict(r) for r,_ in public if r['timestamp'] not in EXPECTED}
    higher={bucket:{'open':100.,'high':102.,'low':99.,'close':101.,'volume':150.}
        for bucket in {stamp//900000*900000 for stamp in EXPECTED}}
    return existing,public,higher


def test_recovery_adds_exact_missing_minutes_and_checks_overlap_and_15m():
    existing,public,higher=fixtures()
    before=deepcopy(existing)
    added,meta=validate_recovery(existing,public,higher)
    assert {r['timestamp'] for r in added}==EXPECTED
    assert len(added)==21 and meta['overlap_1m_candles_checked']==1419
    assert len(meta['higher_timeframe_crosschecks'])==2
    assert existing==before


@pytest.mark.parametrize('kind', ['conflict','higher_conflict','additional_gap','filled_gap','duplicate','missing_provider'])
def test_recovery_refuses_ambiguous_or_conflicting_inputs(kind):
    existing,public,higher=fixtures()
    if kind=='conflict':existing[min(existing)]['close']=100.5
    elif kind=='higher_conflict':higher[min(higher)]['high']=103.
    elif kind=='additional_gap':existing.pop(min(existing))
    elif kind=='filled_gap':existing[START]=next(dict(row) for row,_ in public if row['timestamp']==START)
    elif kind=='duplicate':public.append(public[0])
    elif kind=='missing_provider':public.pop(0)
    with pytest.raises(ValueError):validate_recovery(existing,public,higher)


@pytest.mark.parametrize('factor',[1,1000])
def test_public_1m_parser_normalizes_microsecond_timestamps(factor):
    cells=[START*factor,100,102,99,101,10,(START+60000)*factor-1,1000,20,7,700,0]
    candle,_=parse_klines(','.join(map(str,cells)).encode(),tf='1m')[0]
    assert candle['timestamp']==START and candle['close_time']==START+59999
