from dataclasses import asdict
from types import SimpleNamespace
import pytest
from platform_v2.tools.research.spot_backtest.paired_support import select_cohort, RecordedDecisions
from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide


def test_missing_decision_keeps_exit_clock_without_fabricating_signal():
    window, common = select_cohort([1,900001,1800001], {'1':{},'1800001':{}},1,1800001)
    assert window == [1,900001,1800001]
    assert common == {1,1800001}


def test_window_keeps_indicator_warmup_outside_account_start():
    assert select_cohort([1,900001,1800001],{'900001':{},'1800001':{}},900001,1800001)[0] == [900001,1800001]


@pytest.mark.parametrize('stamps,records', [([1,1800001],{'1':{},'1800001':{}}),
    ([1,900001,1800001],{'1800001':{}})])
def test_refuse_gaps_or_unrecorded_start(stamps,records):
    with pytest.raises(ValueError):select_cohort(stamps,records,1,1800001)


def test_recorded_decision_drops_original_execution_metadata(monkeypatch):
    from platform_v2.spot.services.signal.entry_quality_service import SpotEntryQualityService
    calls=[]
    def evaluate(self,**kw):
        calls.append(kw)
        from dataclasses import dataclass
        @dataclass
        class Quality:
            allowed: bool = True
        return Quality()
    monkeypatch.setattr(SpotEntryQualityService,'evaluate',evaluate)
    original=SignalDecision(timestamp_ms=1,symbol='BTCUSDT',timeframe='15m',side=SignalSide.BUY,
        snapshot_price=100.,score=9.,threshold=8.,evaluated_direction='LONG',
        decision_time='later',execution_quote_price=105.,execution_quote_time_ms=123,
        execution_quote_source='actual',entry_quality={'allowed':False})
    context=SimpleNamespace(latest_candle=SimpleNamespace(close_time_ms=1),symbol='BTCUSDT',timeframe='15m')
    got=RecordedDecisions({'1':asdict(original)}).build_signal(context,prior_signals=[{'evaluated_direction':'SHORT'}])
    assert got.side==SignalSide.BUY and got.score==9.
    assert got.execution_quote_price is None and got.execution_quote_time_ms is None
    assert got.execution_quote_source is None and got.decision_time is None
    assert got.entry_quality=={'allowed':True}
    assert calls[0]['prior_signals']==[{'evaluated_direction':'SHORT','side':'SHORT'}]
    with pytest.raises(KeyError):RecordedDecisions({}).build_signal(context)


def test_execution_comparison_pairs_by_signal_not_position_number(tmp_path,monkeypatch):
    import json
    from platform_v2.tools.research.spot_backtest import paired_execution_audit as audit
    (tmp_path/'manifest.json').write_text(json.dumps({'files':{}}))
    stamp=1789325999999
    def position(price):
        return {'signal_candle_close_time':'2026-09-13 18:59:59', 'execution':{'entry_price':price}}
    def fake_load(root,name):
        result={'segments':[{'positions':[position(100. if name=='baseline' else 101.)],'exit_reasons':{'sl_hit':1}}]}
        rows=[{'timestamp_ms':stamp,'signal':{'side':'BUY'},'permission':{'status':'ALLOWED'}}]
        return result,rows
    monkeypatch.setattr(audit,'load',fake_load)
    audit.run(tmp_path)
    summary=json.loads((tmp_path/'execution_comparison/summary.json').read_text())
    assert summary['same_signal_entries']==1
    assert summary['shared_entries_with_different_price']==1
    pairs=json.loads((tmp_path/'execution_comparison/position_pairs.json').read_text())
    assert pairs[0]['entry_price_difference']==-1.


def test_execution_comparison_refuses_modified_evidence(tmp_path):
    import json
    from platform_v2.tools.research.spot_backtest.paired_execution_audit import run
    (tmp_path/'manifest.json').write_text(json.dumps({'files':{'summary.json':'not-the-hash'}}))
    (tmp_path/'summary.json').write_text('{}')
    with pytest.raises(ValueError,match='evidence changed'):run(tmp_path)
