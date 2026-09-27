"""Fault tests for real SQLite projection writers, not simulated durability."""
from pathlib import Path
import os
import sqlite3
import subprocess
import sys

import pytest
from .ledger import Ledger
from .execution import ProjectionStage, committed, AlreadyCommitted, ConcurrentProjectionChange
from platform_v2.shared.backend.persistence.sqlite_documents import mirror_document
from platform_v2.shared.backend.persistence.sqlite_runtime_state import read_runtime_state, write_runtime_state
from platform_v2.shared.backend.persistence.sqlite_document_queries import read_document


@pytest.fixture
def path(tmp_path):
    path=tmp_path/'trading.sqlite3'
    Ledger(path)
    return path


def effect(path, n=1):
    mirror_document(system='spot',family='orders',date_iso='2026-09-26',payload=[{'id':n}],db_path=path)
    write_runtime_state(system='spot',state_key='balance',payload={'balance':100-n},db_path=path)


def test_atomic_projection_and_repeat(path):
    with ProjectionStage(path,'spot','cycle','attempt') as stage:
        effect(path)
        assert read_runtime_state(system='spot',state_key='balance',db_path=path)=={'balance':99}
        db=sqlite3.connect(path)
        assert db.execute('SELECT count(*) FROM runtime_rows').fetchone()[0]==0
        db.close()
        stage.publish()
    assert committed(path,'spot','cycle')
    assert read_document(system='spot',family='orders',date_iso='2026-09-26',db_path=path)==[{'id':1}]
    with ProjectionStage(path,'spot','cycle','retry') as stage:
        effect(path,2)
        with pytest.raises(AlreadyCommitted): stage.publish()
    assert read_runtime_state(system='spot',state_key='balance',db_path=path)=={'balance':99}


@pytest.mark.parametrize('after',[False,True])
def test_hard_crash_before_after_publish(path,after):
    script='''
import os,sys
from pathlib import Path
from platform_v2.shared.backend.research_evidence.execution import ProjectionStage
from platform_v2.shared.backend.persistence.sqlite_runtime_state import write_runtime_state
from platform_v2.shared.backend.persistence.sqlite_documents import mirror_document
p=Path(sys.argv[1])
with ProjectionStage(p,'spot','cycle','a') as s:
 mirror_document(system='spot',family='orders',date_iso='2026-09-26',payload=[{'id':1}],db_path=p)
 write_runtime_state(system='spot',state_key='balance',payload={'balance':99},db_path=p)
 if sys.argv[2]=='True': s.publish()
 os._exit(19)
'''
    assert subprocess.run([sys.executable,'-c',script,str(path),str(after)]).returncode==19
    assert committed(path,'spot','cycle')==after
    assert read_runtime_state(system='spot',state_key='balance',db_path=path)==({'balance':99} if after else None)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM runtime_rows').fetchone()[0]==int(after)
        assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'


def test_concurrent_mutation_rejected(path):
    effect(path)
    with ProjectionStage(path,'spot','cycle','a') as stage:
        effect(path,2)
        with sqlite3.connect(path) as db:
            db.execute("UPDATE runtime_state SET payload_json='{}' WHERE system='spot'")
        with pytest.raises(ConcurrentProjectionChange): stage.publish()
    assert read_runtime_state(system='spot',state_key='balance',db_path=path)=={}
    assert not committed(path,'spot','cycle')


def test_evidence_remains_durable_when_projection_rolls_back(path):
    ledger=Ledger(path)
    with ProjectionStage(path,'spot','cycle','a'):
        effect(path)
        ledger.append('cycle_attempt_events',run_id='r',system='spot',kind='TEST',payload={'seen':True})
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM cycle_attempt_events').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM runtime_rows').fetchone()[0]==0


@pytest.mark.parametrize('system',['spot','futures'])
@pytest.mark.parametrize('failure',['before_publish','after_publish'])
def test_main_cycle_atomic_integration(path,system,failure,monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock
    from .runtime import ACTIVE,Attempt
    if system=='spot':
        from platform_v2.spot.services.ops.main_cycle.service import MainCycleService
        kwargs=dict(symbol='BTCUSDT',timeframe='15m',date_iso='2026-09-26')
    else:
        from platform_v2.futures.services.ops.main_cycle.service import MainCycleService
        kwargs=dict(profile=SimpleNamespace(symbol='BTCUSDT',timeframe='15m',mode='simulation'),date_iso='2026-09-26')
    ledger=Ledger(path)
    a,c=ledger.start(run_id='r',system=system,symbol='BTCUSDT',timeframe='15m')
    token=ACTIVE.set(Attempt(ledger,'r',system,a,c))
    monkeypatch.setenv('SSH_RESEARCH_ATOMIC_SIMULATION','1')
    inputs,guard,execution,finalize=Mock(),Mock(),Mock(),Mock()
    inputs.prepare_cycle_inputs.return_value=SimpleNamespace(cycle_info=SimpleNamespace(key='test-cycle',state='ready',note='ok'),fetched_candle_paths=())
    @contextmanager
    def lock():yield True
    guard.try_process_lock.side_effect=lock
    guard.read_cycle_marker.return_value=SimpleNamespace(already_processed=False)
    guard.write_cycle_marker.side_effect=lambda key:write_runtime_state(system=system,state_key='main_cycle_marker',payload={'cycle_key':key},db_path=path)
    finalize.finalize_result.side_effect=lambda **kw:kw['result']
    calls=[]
    def execute(**kw):
        calls.append(True)
        write_runtime_state(system=system,state_key='position',payload={'id':1},db_path=path)
        if failure=='before_publish':raise OSError('before publication')
        kw['commit_callback']()
        raise OSError('page render failure after publication')
    execution.run_ready_cycle.side_effect=execute
    service=MainCycleService(inputs,guard,execution,finalize)
    try:
        with pytest.raises(OSError): service.run(**kwargs)
        if failure=='after_publish':
            assert service.run(**kwargs).skipped
            assert len(calls)==1
            assert committed(path,system,'test-cycle')
        else:
            assert not committed(path,system,'test-cycle')
            assert read_runtime_state(system=system,state_key='position',db_path=path) is None
    finally:
        ACTIVE.reset(token)
