import json
import gzip
import hashlib
import sqlite3
from pathlib import Path

import pytest

from platform_v2.tools.research import signal_lab as lab


@pytest.mark.parametrize('path', [lab.LIVE, lab.LIVE / 'reports', lab.LIVE.parent])
def test_reject_live_output(path):
    with pytest.raises(ValueError):
        lab.outside_live(path)


@pytest.mark.parametrize('name', ['../baseline', '/tmp/test', 'Foo', ''])
def test_candidate_name_guard(tmp_path, name):
    with pytest.raises(ValueError):
        lab.candidate(tmp_path, name)


def test_compare_exact_labels_and_next_minute(tmp_path, monkeypatch):
    (tmp_path / 'data').mkdir()
    with sqlite3.connect(tmp_path / 'data/market.sqlite3') as db:
        db.execute('CREATE TABLE market_observations (venue,market_type,dataset,symbol,timeframe,event_time_ms,payload_json)')
        for t, price in [(60000, 100), (960000, 101)]:
            db.execute('INSERT INTO market_observations VALUES (?,?,?,?,?,?,?)',
                       ('binance', 'futures', 'candles', 'BTCUSDT', '1m', t,
                        json.dumps({'open': price, 'close_time': t + 59999})))
    monkeypatch.setattr(lab, 'verify', lambda p: {'end_ms': 2000000, 'horizons_minutes': [15, 60], 'scope': 'signal', 'validation': 'exploratory'})
    for name, side in [('baseline', 'LONG'), ('candidate', 'SHORT')]:
        path = tmp_path / 'runs' / name
        path.mkdir(parents=True)
        lab.write(path / 'result.json', {'parity_ok': True, 'actions': {side: 1},
                  'decisions': [{'observation_id': 1, 'available_ms': 59000, 'selected_direction': side}]})
        lab.write(tmp_path / 'protocol.json', {})
        lab.write(path / 'manifest.json', {'protocol_sha256': lab.digest(tmp_path / 'protocol.json'), 'files': {'result.json': lab.digest(path / 'result.json')}})
    report = lab.compare(tmp_path, 'candidate')
    assert report['changed_actions'] == 1
    assert report['horizons']['15']['baseline']['LONG']['mean_pct'] == pytest.approx(1)
    assert report['horizons']['15']['candidate']['SHORT']['mean_pct'] == pytest.approx(-1)
    assert report['horizons']['60']['missing_labels'] == 1


def test_empty_parity_cannot_compare(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, 'verify', lambda p: {})
    for name in ['baseline', 'candidate']:
        path = tmp_path / 'runs' / name
        path.mkdir(parents=True)
        lab.write(path / 'result.json', {'parity_ok': False})
        lab.write(tmp_path / 'protocol.json', {})
        lab.write(path / 'manifest.json', {'protocol_sha256': lab.digest(tmp_path / 'protocol.json'), 'files': {'result.json': lab.digest(path / 'result.json')}})
    with pytest.raises(ValueError, match='verified'):
        lab.compare(tmp_path, 'candidate')


def test_verify_detects_database_and_launcher_tampering(tmp_path):
    (tmp_path / 'source').mkdir()
    (tmp_path / 'data').mkdir()
    raw = b'{"format":1}'
    (tmp_path / 'source/source.json.gz').write_bytes(gzip.compress(raw))
    (tmp_path / 'source/run.py').write_text('# loader')
    (tmp_path / 'data/trading.sqlite3').write_bytes(b'frozen')
    lab.write(tmp_path / 'protocol.json', {'databases': {'trading': {'sha256': lab.digest(tmp_path / 'data/trading.sqlite3')}},
              'source_sha256': hashlib.sha256(raw).hexdigest(), 'runner_sha256': lab.digest(tmp_path / 'source/run.py')})
    lab.verify(tmp_path)
    (tmp_path / 'source/run.py').write_text('# different loader')
    with pytest.raises(ValueError, match='launcher'):
        lab.verify(tmp_path)
    (tmp_path / 'source/run.py').write_text('# loader')
    (tmp_path / 'data/trading.sqlite3').write_bytes(b'changed')
    with pytest.raises(ValueError, match='database'):
        lab.verify(tmp_path)


def test_compare_detects_result_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, 'verify', lambda p: {})
    lab.write(tmp_path / 'protocol.json', {})
    out = tmp_path / 'runs/baseline'
    out.mkdir(parents=True)
    lab.write(out / 'result.json', {'parity_ok': True})
    lab.write(out / 'manifest.json', {'protocol_sha256': lab.digest(tmp_path / 'protocol.json'), 'files': {'result.json': lab.digest(out / 'result.json')}})
    lab.write(out / 'result.json', {'parity_ok': False})
    with pytest.raises(ValueError, match='artifact'):
        lab.compare(tmp_path, 'candidate')
