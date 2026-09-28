import json
import sqlite3
import time
from unittest.mock import patch
from .checkpoint import create, NAMES
from .health import inspect
from .ledger import Ledger
from .monitor import run


def test_checkpoint_restore_and_missing_source(tmp_path):
    source=tmp_path/'source';source.mkdir()
    for name in NAMES:
        with sqlite3.connect(source/name) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE example(value)')
            db.execute('INSERT INTO example VALUES (42)')
    report=create(source,tmp_path/'backup')
    assert all(d['restore_verified'] and d['table_counts']['example']==1 for d in report['databases'])
    assert (tmp_path/'backup/manifest.json').exists()
    import pytest
    with pytest.raises(sqlite3.OperationalError):create(tmp_path/'absent',tmp_path/'failed')
    assert not (tmp_path/'failed/manifest.json').exists()


def test_health_recent_attempt_not_stale_and_drift_detected(tmp_path):
    ledger=Ledger(tmp_path/'db');now=int(time.time()*1000)
    expectations={'systems':{}}
    for system in ('spot','futures'):
        expected={'release_sha256':'a','config_sha256':'b','activation_close_ms':'899999','backfill':True}
        expectations['systems'][system]=expected
        ledger.append('research_runs',run_id=system,system=system,kind='STARTED',payload={**expected,'release_verified':True,'atomic_simulation':True})
        ledger.start(run_id=system,system=system,symbol='BTCUSDT',timeframe='15m',started_ms=now)
    report=inspect(ledger.path,expectations=expectations)
    assert not any('OPEN_ATTEMPTS' in issue or 'UNEXPECTED' in issue for issue in report['issues'])
    assert 'spot:DECISIONS_STALE_OR_ABSENT' in report['issues']
    expectations['systems']['spot']['release_sha256']='different'
    assert 'spot:UNEXPECTED_RELEASE_SHA256' in inspect(ledger.path,expectations=expectations)['issues']
    with patch('platform_v2.shared.backend.research_evidence.health.time.time',return_value=(now+1300000)/1000):
        assert 'spot:OPEN_ATTEMPTS_REVIEW' in inspect(ledger.path)['issues']


def test_monitor_failure_is_visible_and_does_not_touch_db(tmp_path):
    output=tmp_path/'logs'
    assert run(tmp_path/'db',tmp_path/'missing-expectations',tmp_path/'backup',output)==1
    assert not (tmp_path/'db').exists()
    result=json.loads((output/'latest.json').read_text())
    assert result['issues']==['MONITOR_FAILURE']
