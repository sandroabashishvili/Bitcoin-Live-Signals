from dataclasses import dataclass
from pathlib import Path
import pytest
from platform_v2.tools.research.spot_lab_support import SpotStore,millis,plain,historical_fill_time
from platform_v2.tools.research import spot_lab


def test_spot_documents_keep_daily_versions_and_copy_values(tmp_path):
    store=SpotStore(tmp_path)
    row={'position_id':'SPOT-000001','status':'OPEN'}
    store.write('positions','2026-09-28',row,'position_id')
    row['status']='CLOSED'
    store.write('positions','2026-09-29',row,'position_id')
    assert store.documents('positions')[0][1][0]['status']=='OPEN'
    assert store.documents('positions')[1][1][0]['status']=='CLOSED'
    store.write('positions','2026-09-29',{'position_id':'SPOT-000001','status':'CLOSED','net_pnl':1},'position_id')
    assert len(store.all('positions'))==2


def test_naive_capture_time_is_explicitly_utc():
    assert millis('2026-09-28 13:31:47')==millis('2026-09-28T13:31:47Z')


def test_dataclass_write_is_json_normalized(tmp_path):
    @dataclass
    class Signal:
        timestamp_ms:int=1
        reasons:tuple=('test',)
    store=SpotStore(tmp_path)
    store.write('signals','2026-09-28',Signal(),'timestamp_ms')
    assert store.all('signals')[0]['reasons']==['test']


def test_observed_fill_has_its_own_exact_timestamp():
    row={'request':{'symbol':'BTCUSDT','timeframe':'15m'},'fill':{'fill_price':100.,'filled_at_ms':12345}}
    assert historical_fill_time([row],'BTCUSDT','15m',100.,12000,11999)==12345
    assert historical_fill_time([row],'BTCUSDT','15m',101.,12000,11999)==11999
    with pytest.raises(ValueError,match='Ambiguous'):
        historical_fill_time([row,row],'BTCUSDT','15m',100.,12000,11999)


@pytest.mark.parametrize('model,name',[('bad','baseline'),('observed','symmetric_all')])
def test_spot_candidates_do_not_use_observed_counterfactual_quotes(tmp_path,monkeypatch,model,name):
    monkeypatch.setattr(spot_lab.lab,'verify',lambda root:{})
    if model=='observed':
        monkeypatch.setattr(spot_lab.lab,'_verify_run',lambda *a:None)
    with pytest.raises(ValueError):spot_lab.run(tmp_path,name,model)
