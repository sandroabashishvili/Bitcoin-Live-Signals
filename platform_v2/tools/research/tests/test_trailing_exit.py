import json
import pytest
from platform_v2.tools.research.replay.trailing_exit import TrailingPolicy, new_state, advance


def bar(t, low, high, op=100):
    return dict(close_time=t, low=low, high=high, open=op)


@pytest.mark.parametrize('side,d',[('LONG',1),('SHORT',-1)])
def test_activation_is_next_bar_and_stop_never_widens(side,d):
    s=new_state(side=side,entry=100,stop=100-d*10,target=100+d*30)
    first=bar(59999,99,112) if d==1 else bar(59999,88,101)
    assert advance(s,first,atr=2,policy=TrailingPolicy()) is None
    assert s['stop']==(108 if d==1 else 92)
    saved=json.loads(json.dumps(s))
    assert advance(saved,first,atr=2,policy=TrailingPolicy()) is None
    second=bar(119999,109,113,110) if d==1 else bar(119999,87,91,90)
    assert advance(saved,second,atr=10,policy=TrailingPolicy()) is None
    assert saved['stop']==s['stop']
    third=bar(179999,105,110,109) if d==1 else bar(179999,90,95,91)
    assert advance(saved,third,atr=2,policy=TrailingPolicy())['outcome']=='TRAIL_STOP'


def test_stop_first_and_gap_execution():
    s=new_state(side='LONG',entry=100,stop=90,target=120)
    out=advance(s,bar(59999,80,125,85),atr=2,policy=TrailingPolicy())
    assert out['price']==85 and out['ambiguous']


@pytest.mark.parametrize('side,d',[('LONG',1),('SHORT',-1)])
def test_target_extension_bounded_and_never_undoes_hit(side,d):
    s=new_state(side=side,entry=100,stop=100-d*10,target=100+d*30)
    b=bar(899999,99,125) if d==1 else bar(899999,75,101)
    p=TrailingPolicy(atr_multiple=2,extend_target=True)
    advance(s,b,atr=10,policy=p,signal_close_ms=899999,direction_score=10)
    assert s['target']==100+d*45
    s=new_state(side=side,entry=100,stop=100-d*10,target=100+d*30)
    b=bar(899999,99,135) if d==1 else bar(899999,65,101)
    assert advance(s,b,atr=10,policy=p,signal_close_ms=899999,direction_score=10)['price']==100+d*30


def test_missing_bars_and_future_inputs_rejected():
    s=new_state(side='LONG',entry=100,stop=90,target=130)
    advance(s,bar(59999,99,101),atr=2,policy=TrailingPolicy())
    with pytest.raises(ValueError,match='Missing'):
        advance(s,bar(179999,99,101),atr=2,policy=TrailingPolicy())
    with pytest.raises(ValueError,match='Future'):
        advance(s,bar(119999,99,101),atr=2,policy=TrailingPolicy(),signal_close_ms=899999)
