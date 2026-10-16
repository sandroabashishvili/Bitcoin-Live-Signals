import json
import pytest
from platform_v2.tools.research.orderflow_input_audit import aggregate,snapshot_matches,response_pairs


def test_trade_taker_volumes_and_duplicate_metrics():
    result=aggregate([{'q':'3','m':False,'T':100},{'q':'1','m':True,'T':200}])
    assert result['buyers']==3 and result['sellers']==1
    assert result['dominance_ratio']==result['imbalance']==.5
    assert result['first_trade_ms']==100 and result['last_trade_ms']==200
    assert snapshot_matches({'buyers':3,'sellers':1,'dominance_ratio':.5,'imbalance':.5,'period_count':2},result)


def test_match_requires_all_consumed_fields_not_only_ratio():
    result=aggregate([{'q':'3','m':False,'T':100},{'q':'1','m':True,'T':200}])
    assert not snapshot_matches({'buyers':6,'sellers':2,'dominance_ratio':.5,'imbalance':.5,'period_count':2},result)


def test_empty_capture_does_not_invent_trade_times():
    result=aggregate([])
    assert result['period_count']==0 and result['last_trade_ms'] is None


@pytest.mark.parametrize('quantity',['nan','inf','-1'])
def test_invalid_quantities_rejected(quantity):
    with pytest.raises(ValueError,match='Invalid'):aggregate([{'q':quantity,'m':False,'T':100}])


def test_response_link_uses_event_key_not_numeric_row_id_and_respects_cutoff():
    events=[(17,'request-key','REQUESTED',100,json.dumps({'endpoint':'https://api.binance.com/api/v3/aggTrades'})),
        (18,'response-key','RESPONSE',101,json.dumps({'request_id':'request-key','content_ref':'blob'}))]
    pairs=list(response_pairs(events,101))
    assert len(pairs)==1 and pairs[0][0]==18 and pairs[0][2]['content_ref']=='blob'
    assert list(response_pairs(events,100))==[]
