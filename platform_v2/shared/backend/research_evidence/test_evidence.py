"""Isolated R2 acceptance tests. No exchange, production DB or runtime launch."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from .ledger import Ledger, canonical
from . import runtime as rt
from .backfill import fetch_closed_range


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path/'trading.sqlite3')


def rows(ledger,table):
    with ledger.connection() as db:
        return [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY id')]


@contextmanager
def active(ledger, system='spot'):
    attempt,cycle=ledger.start(run_id='test',system=system,symbol='BTCUSDT',timeframe='15m',started_ms=960000)
    ctx=rt.Attempt(ledger,'test',system,attempt,cycle)
    token=rt.ACTIVE.set(ctx)
    try:
        yield ctx
    finally:
        rt.ACTIVE.reset(token)


def test_first_decision_and_repeat_preserved(ledger):
    for score in (9,11):
        with active(ledger) as a:
            ref=ledger.blob({'inputs':[1,2]})
            ledger.decision(run_id='test',system='spot',attempt_id=a.attempt_id,
                cycle_key=a.cycle_key,payload={'score':score},input_refs=[ref],available_ms=960001)
    decisions=rows(ledger,'decision_observations')
    assert [json.loads(r['payload_json'])['record']['score'] for r in decisions]==[9,11]
    starts=rows(ledger,'cycle_attempt_events')
    assert json.loads(starts[1]['payload_json'])['retry_of']==starts[0]['attempt_id']
    assert json.loads(starts[1]['payload_json'])['attempt_sequence']==2
    with ledger.connection() as db:
        with pytest.raises(sqlite3.IntegrityError,match='append-only'):
            db.execute('UPDATE decision_observations SET kind="fake"')
        with pytest.raises(sqlite3.IntegrityError,match='append-only'):
            db.execute('DELETE FROM decision_observations')


def test_late_and_reconstruction_separate(ledger):
    with active(ledger) as a:
        ref=ledger.blob([])
        ledger.decision(run_id='test',system='spot',attempt_id=a.attempt_id,
            cycle_key=a.cycle_key,payload={},input_refs=[ref],available_ms=1800000,
            origin='RESEARCH_RECONSTRUCTED')
        assert ledger.detect_gaps(run_id='test',system='spot',symbol='BTCUSDT',timeframe='15m',
            activation_close_ms=899999,through_close_ms=899999)==1
    row=rows(ledger,'decision_observations')[0]
    assert row['kind']=='RESEARCH_RECONSTRUCTED'
    assert json.loads(row['payload_json'])['timeliness']=='LATE'
    assert json.loads(rows(ledger,'cycle_gap_events')[0]['payload_json'])['reason']=='UNKNOWN'


@pytest.mark.parametrize('after_decision',[False,True])
def test_hard_exit_durable_start_and_recovery(tmp_path, after_decision):
    path=tmp_path/'crash.sqlite3'
    script='''
import os,sys
from pathlib import Path
from platform_v2.shared.backend.research_evidence.ledger import Ledger
l=Ledger(Path(sys.argv[1]))
a,c=l.start(run_id='dead',system='spot',symbol='BTCUSDT',timeframe='15m',started_ms=960000)
if sys.argv[2]=='True':
 l.decision(run_id='dead',system='spot',attempt_id=a,cycle_key=c,payload={'score':9},input_refs=[l.blob([1])])
os._exit(17)
'''
    p=subprocess.run([sys.executable,'-c',script,str(path),str(after_decision)])
    assert p.returncode==17
    l=Ledger(path)
    assert len(rows(l,'cycle_attempt_events'))==1
    assert len(rows(l,'decision_observations'))==int(after_decision)
    with pytest.raises(ValueError):
        l.recover(dead_run_id='dead',recovery_run_id='new',system='spot',evidence={})
    assert l.recover(dead_run_id='dead',recovery_run_id='new',system='spot',
                     evidence={'process_exit_confirmed':True,'returncode':17})==1
    assert l.recover(dead_run_id='dead',recovery_run_id='new',system='spot',
                     evidence={'process_exit_confirmed':True,'returncode':17})==0
    assert rows(l,'cycle_attempt_events')[-1]['kind']=='ABANDONED'


def test_event_retry_idempotency_and_terminal_exclusivity(ledger):
    a,c=ledger.start(run_id='r',system='spot',symbol='BTCUSDT',timeframe='15m')
    args=dict(run_id='r',system='spot',attempt_id=a,cycle_key=c,kind='COMMITTED',payload={})
    ledger.terminal(**args);ledger.terminal(**args)
    assert len(rows(ledger,'cycle_attempt_events'))==2
    with pytest.raises(sqlite3.IntegrityError):
        ledger.terminal(**{**args,'kind':'FAILED'})


def test_empty_flow_distinct_from_network_error(ledger):
    with active(ledger):
        assert rt.observe_acquisition('https://example.test/aggTrades?limit=1000',lambda:[])==[]
        def fail(): raise OSError('offline')
        with pytest.raises(OSError):
            rt.observe_acquisition('https://example.test/aggTrades?limit=1000',fail)
    events=rows(ledger,'market_acquisition_events')
    assert [r['kind'] for r in events]==['REQUESTED','RESPONSE','REQUESTED','ERROR']
    assert json.loads(events[1]['payload_json'])['count']==0
    assert json.loads(events[3]['payload_json'])['count'] is None


@pytest.mark.parametrize('hours',[4,24])
def test_outage_backfill_pagination(ledger,hours):
    class Client:
        calls=0
        def get_json(self,url):
            self.calls+=1
            q=parse_qs(urlsplit(url).query)
            start,end=int(q['startTime'][0]),int(q['endTime'][0])
            page=[[t,'1','2','1','2','3',t+59999] for t in range(start,end+1,60000)]
            return rt.observe_acquisition(url,lambda:page)
    client=Client()
    with active(ledger):
        result=fetch_closed_range(client,'https://example.test/klines',symbol='BTCUSDT',timeframe='1m',
                                 start_open_ms=60000,end_open_ms=hours*60*60000)
    assert len(result)==hours*60
    assert client.calls==(hours*60+499)//500
    assert all(json.loads(r['payload_json'])['origin']=='BACKFILLED' for r in rows(ledger,'market_acquisition_events'))
    assert not rows(ledger,'decision_observations')


def test_backfill_does_not_claim_incomplete_page():
    client=Mock();client.get_json.return_value=[]
    with pytest.raises(ValueError,match='incomplete'):
        fetch_closed_range(client,'https://example.test',symbol='X',timeframe='1m',start_open_ms=60000,end_open_ms=120000)


def test_missing_revision_refused(ledger):
    with active(ledger) as a:
        with pytest.raises(ValueError,match='missing input'):
            ledger.decision(run_id='r',system='spot',attempt_id=a.attempt_id,cycle_key=a.cycle_key,payload={},input_refs=['missing'])
    assert not rows(ledger,'decision_observations')


def test_concurrent_writers_preserve_events(ledger):
    def write(i):
        return ledger.start(run_id='r',system='spot',symbol='BTCUSDT',timeframe='15m',started_ms=960000)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write,range(32)))
    values=[json.loads(r['payload_json'])['attempt_sequence'] for r in rows(ledger,'cycle_attempt_events')]
    assert sorted(values)==list(range(1,33))


def test_exact_market_revision_and_missing_chunk(ledger,tmp_path):
    from platform_v2.shared.backend.persistence.sqlite_market_data_store import read_market_series,replace_market_series
    args=dict(venue='binance',asset_class='crypto',market_type='spot',dataset='candles',symbol='BTCUSDT',timeframe='15m',db_path=tmp_path/'market.sqlite3')
    source=[{'timestamp':900000,'close':100}]
    replace_market_series(**args,rows=source)
    with active(ledger) as a:
        assert read_market_series(**args)==source
        old=a.input_refs[0]
        replace_market_series(**args,rows=[{'timestamp':900000,'close':200}])
        read_market_series(**args)
        assert a.input_refs[1]!=old
        assert ledger.load_blob(ledger.load_blob(old)['chunks'][0])==source
        bad=ledger.blob({'chunks':['missing'],'identity':[],'count':1})
        a.input_refs=[bad]
        rt.observe_decision('spot','signals',{'symbol':'BTCUSDT','timeframe':'15m','candle_close_time':'1970-01-01 00:14:59Z'})
        assert a.errors==['ValueError']
    assert not rows(ledger,'decision_observations')


@pytest.mark.parametrize('system',['spot','futures'])
def test_real_cycle_orchestration_neutrality_and_duplicate_guard(ledger,system):
    if system=='spot':
        from platform_v2.spot.services.ops.main_cycle.service import MainCycleService
        kwargs={'symbol':'BTCUSDT','timeframe':'15m','date_iso':'2026-09-26'}
    else:
        from platform_v2.futures.services.ops.main_cycle.service import MainCycleService
        kwargs={'profile':SimpleNamespace(symbol='BTCUSDT',timeframe='15m'),'date_iso':'2026-09-26'}
    def exercise(enabled):
        inputs=Mock();guard=Mock();execution=Mock();finalize=Mock()
        info=SimpleNamespace(key='BTCUSDT:15m:899999',state='ready',note='ok')
        inputs.prepare_cycle_inputs.return_value=SimpleNamespace(cycle_info=info,fetched_candle_paths=())
        @contextmanager
        def locked(): yield True
        guard.try_process_lock.side_effect=locked
        guard.read_cycle_marker.side_effect=[SimpleNamespace(already_processed=False),SimpleNamespace(already_processed=True,state='done')]
        result=SimpleNamespace(skipped=False,cycle_key=info.key,skip_reason=None)
        execution.run_ready_cycle.return_value=result
        finalize.finalize_result.side_effect=lambda **kw:kw['result']
        service=MainCycleService(inputs,guard,execution,finalize)
        with patch.dict(rt.RUNS,{(os.getpid(),system):(ledger,'r')} if enabled else {},clear=True):
            first=service.run(**kwargs)
            repeated=service.run(**kwargs)
        assert first is result and repeated.skipped
        assert execution.run_ready_cycle.call_count==1
        assert guard.write_cycle_marker.call_count==1
        return execution.mock_calls,guard.mock_calls,inputs.mock_calls
    assert exercise(False)==exercise(True)
    assert len([r for r in rows(ledger,'cycle_attempt_events') if r['kind']=='STARTED'])==2


def test_recorder_failure_does_not_retry_trading(ledger):
    class Service:
        calls=0
        @rt.recorded_cycle('spot')
        def run(self,**kwargs):
            self.calls+=1
            return 'unchanged'
    service=Service()
    with patch.dict(rt.RUNS,{(os.getpid(),'spot'):(ledger,'r')},clear=True),patch.object(ledger,'start',side_effect=OSError('full')):
        assert service.run()=='unchanged'
    assert service.calls==1


def test_payload_projection_hook_keeps_exact_values(ledger):
    from platform_v2.shared.backend.runtime_store.store import RuntimeStore
    store=RuntimeStore('spot')
    row={'timestamp_ms':1,'symbol':'BTCUSDT','timeframe':'15m','candle_close_time':'1970-01-01 00:14:59Z',
         'direction_component_scores':{'BUY':{'trend':2}},'direction_component_weights':{'BUY':{'trend':1}},'score':9}
    with active(ledger) as a,patch.object(RuntimeStore,'load_family_rows',return_value=[]),patch.object(RuntimeStore,'write_json') as write:
        a.capture_input(('test',),[{'close':100}])
        store.upsert_runtime_row(family_name='signals',date_iso='1970-01-01',row=row,match_keys=('timestamp_ms',))
        assert write.call_args.args[1]==[row]
    saved=json.loads(rows(ledger,'decision_observations')[0]['payload_json'])
    assert saved['record']==row and saved['evidence_complete']


def test_spot_raw_then_enriched_decision_preserves_first_evaluation(ledger):
    raw={'symbol':'BTCUSDT','timeframe':'15m','timestamp_ms':899999,
         'candle_close_time':None,'score':9}
    enriched={**raw,'candle_close_time':'1970-01-01 00:14:59','decision_time':'1970-01-01 00:16:00'}
    with active(ledger) as a:
        a.capture_input(('candles',),[{'close':100}])
        rt.observe_decision('spot','signals',raw)
        rt.observe_decision('spot','signals',enriched)
        assert not a.errors
    observations=rows(ledger,'decision_observations')
    assert len(observations)==2
    assert {r['cycle_key'] for r in observations}=={'BTCUSDT:15m:899999'}
    assert [json.loads(r['payload_json'])['record'] for r in observations]==[raw,enriched]
    with ledger.connection() as db:
        first=db.execute('SELECT payload_json FROM research_first_live_decisions').fetchone()[0]
    assert json.loads(first)['record']==raw


@pytest.mark.parametrize('stamp',[None,True,900000,'899999',899999.0])
def test_missing_or_invalid_raw_spot_candle_never_uses_expected_slot(ledger,stamp):
    with active(ledger) as a:
        rt.observe_decision('spot','signals',{'symbol':'BTCUSDT','timeframe':'15m','timestamp_ms':stamp})
        assert a.errors==['ValueError']
    assert not rows(ledger,'decision_observations')


def test_migration_additive_repeatable_and_health_readonly(tmp_path):
    from .health import inspect
    path=tmp_path/'db.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE existing_projection(value TEXT)')
        db.execute("INSERT INTO existing_projection VALUES ('preserve')")
    l=Ledger(path);Ledger(path)
    with l.connection() as db:
        assert db.execute('SELECT value FROM existing_projection').fetchall()[0][0]=='preserve'
        before=db.execute('PRAGMA schema_version').fetchone()[0]
    result=inspect(path)
    assert not result['ready_for_signoff']
    assert result['quick_check']==['ok']
    with l.connection() as db:
        assert db.execute('PRAGMA schema_version').fetchone()[0]==before


def test_crash_event_wrapper_before_and_after_decision(ledger):
    class Service:
        @rt.recorded_cycle('spot')
        def run(self,after=False):
            # STARTED is observable on a separate connection before any simulated IO.
            assert rows(ledger,'cycle_attempt_events')[-2]['kind']=='STARTED'
            if after:
                a=rt.ACTIVE.get()
                a.capture_input(('source',),[{'x':1}])
                rt.observe_decision('spot','signals',{'symbol':'BTCUSDT','timeframe':'15m','candle_close_time':'1970-01-01 00:14:59Z'})
            raise OSError('simulated failure')
    with patch.dict(rt.RUNS,{(os.getpid(),'spot'):(ledger,'r')},clear=True):
        for after in (False,True):
            with pytest.raises(OSError):
                Service().run(after=after)
    terminal=[r for r in rows(ledger,'cycle_attempt_events') if r['kind']=='FAILED']
    assert len(terminal)==2
    assert len(rows(ledger,'decision_observations'))==1
    assert all(json.loads(r['payload_json'])['side_effects']=='UNKNOWN_REQUIRES_RECONCILIATION' for r in terminal)


def test_first_view_excludes_reconstruction(ledger):
    with active(ledger) as a:
        args=dict(run_id='r',system='spot',attempt_id=a.attempt_id,cycle_key=a.cycle_key,input_refs=[ledger.blob([1])])
        ledger.decision(**args,payload={'n':0},origin='RESEARCH_RECONSTRUCTED')
        ledger.decision(**args,payload={'n':1})
        ledger.decision(**args,payload={'n':2})
    with ledger.connection() as db:
        first=db.execute('SELECT payload_json FROM research_first_live_decisions').fetchall()
    assert len(first)==1 and json.loads(first[0][0])['record']=={'n':1}


def test_futures_fallback_error_retained_without_changing_result(ledger):
    from platform_v2.futures.services.market.binance_futures_orderflow_service import BinanceFuturesOrderflowService
    target='platform_v2.futures.services.market.binance_futures_orderflow_service.urlopen'
    with active(ledger,'futures'),patch(target,side_effect=OSError('offline')):
        result=BinanceFuturesOrderflowService()._request_aggtrades(symbol='BTCUSDT',start_time=0,end_time=1000,limit=1000)
    assert result==[] # Existing behavior intentionally retained, acquisition says ERROR.
    assert rows(ledger,'market_acquisition_events')[-1]['kind']=='ERROR'


def test_no_recovery_for_live_process():
    from .recovery import exit_evidence
    import socket
    payload={'host':socket.gethostname(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
             'pid':os.getpid(),'process_start_ticks':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]}
    assert exit_evidence(payload) is None
    assert exit_evidence({**payload,'process_start_ticks':'not-current'})['process_exit_confirmed']


def test_gap_registry_does_not_fill_decisions(ledger):
    args=dict(run_id='r',system='spot',symbol='BTCUSDT',timeframe='15m',activation_close_ms=899999,through_close_ms=3599999)
    assert ledger.detect_gaps(**args)==4
    assert ledger.detect_gaps(**args)==0
    assert not rows(ledger,'decision_observations')


def test_legacy_post_side_effect_crash_remains_cutover_blocker(ledger):
    """Negative acceptance: recorder is NOT an exactly-once execution coordinator."""
    from platform_v2.spot.services.ops.main_cycle.service import MainCycleService
    inputs,guard,execution,finalize=Mock(),Mock(),Mock(),Mock()
    inputs.prepare_cycle_inputs.return_value=SimpleNamespace(
        cycle_info=SimpleNamespace(key='BTCUSDT:15m:899999',state='ready',note='ok'),fetched_candle_paths=())
    @contextmanager
    def lock(): yield True
    guard.try_process_lock.side_effect=lock
    guard.read_cycle_marker.return_value=SimpleNamespace(already_processed=False)
    simulated_effects=[]
    def partial(**kw):
        simulated_effects.append('side-effect-before-marker')
        raise OSError('after side-effect before marker')
    execution.run_ready_cycle.side_effect=partial
    with patch.dict(rt.RUNS,{(os.getpid(),'spot'):(ledger,'r')},clear=True):
        for _ in range(2):
            with pytest.raises(OSError):
                MainCycleService(inputs,guard,execution,finalize).run(date_iso='2026-09-26')
    assert len(simulated_effects)==2
    assert not guard.write_cycle_marker.called
    assert len([r for r in rows(ledger,'cycle_attempt_events') if r['kind']=='FAILED'])==2


def test_internal_gap_recovery(ledger,monkeypatch):
    from .backfill import recover_missing_tail
    monkeypatch.setenv('SSH_RESEARCH_BACKFILL','1')
    class Client:
        def get_json(self,url):
            q=parse_qs(urlsplit(url).query)
            start,end=int(q['startTime'][0]),int(q['endTime'][0])
            return [[t,'1','2','1','2','3',t+59999] for t in range(start,end+1,60000)]
    with active(ledger):
        result=recover_missing_tail(Client(),'https://example.test/klines',symbol='X',timeframe='1m',
            existing=[{'timestamp':60000},{'timestamp':180000}],current=[{'timestamp':240000}])
    assert [r[0] for r in result]==[120000]


def test_atomic_mode_does_not_fall_back_to_unsafe_execution(ledger,monkeypatch):
    monkeypatch.setenv('SSH_RESEARCH_ATOMIC_SIMULATION','1')
    class Service:
        @rt.recorded_cycle('spot')
        def run(self):raise AssertionError('must not execute')
    with patch.dict(rt.RUNS,{(os.getpid(),'spot'):(ledger,'r')},clear=True),patch.object(ledger,'start',side_effect=OSError('full')):
        with pytest.raises(RuntimeError,match='durable STARTED'):
            Service().run()
