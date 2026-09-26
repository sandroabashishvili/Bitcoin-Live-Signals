"""Provenance validation on synthetic files; no live replay or database access."""
import hashlib
import json
from pathlib import Path

import pytest

from platform_v2.tools.research import recorded_run as recorder


@pytest.fixture
def frozen(tmp_path):
    root = tmp_path / 'input'
    root.mkdir()
    data = root / 'signals.json'
    data.write_text(json.dumps([{'timestamp_ms': 100}, {'timestamp_ms': 200}]))
    (root / 'manifest.json').write_text(json.dumps({'files': [
        {'path': 'signals.json', 'sha256': hashlib.sha256(data.read_bytes()).hexdigest()}
    ]}))
    return root


def test_identity_reports_observed_coverage(frozen):
    result = recorder.snapshot_identity(frozen)
    assert result['coverage']['signals.json'] == {
        'timestamp_field': 'timestamp_ms', 'count': 2, 'min': 100, 'max': 200}


def test_tampering_is_rejected(frozen):
    (frozen / 'signals.json').write_text('[]')
    with pytest.raises(ValueError, match='hash mismatch'):
        recorder.snapshot_identity(frozen)


def test_unlisted_input_is_rejected(frozen):
    (frozen / 'extra.json').write_text('[]')
    with pytest.raises(ValueError, match='unlisted'):
        recorder.snapshot_identity(frozen)


def test_manifest_cannot_escape_snapshot(frozen):
    (frozen / 'manifest.json').write_text(json.dumps({'files': [{'path': '../escape.json', 'sha256': ''}]}))
    with pytest.raises(ValueError, match='escapes'):
        recorder.snapshot_identity(frozen)


def test_output_cannot_modify_snapshot(frozen):
    with pytest.raises(ValueError, match='separate'):
        recorder.run_recorded('portfolio_state_replay', frozen, frozen / 'results')


@pytest.mark.parametrize('failure', [False, True])
def test_run_records_success_or_failure_without_live_execution(frozen, tmp_path, monkeypatch, failure):
    monkeypatch.setattr(recorder, 'source_identity', lambda: {'revision': 'test', 'file_sha256': {}})
    monkeypatch.setattr(recorder, 'effective_parameters', lambda: {'threshold': 8.5})
    def fake_run(*args, **kwargs):
        if failure:
            raise RuntimeError('synthetic error')
    monkeypatch.setattr(recorder.runpy, 'run_module', fake_run)
    output = tmp_path / 'output'
    if failure:
        with pytest.raises(RuntimeError):
            recorder.run_recorded('portfolio_state_replay', frozen, output)
    else:
        recorder.run_recorded('portfolio_state_replay', frozen, output)
    payload = json.loads(next(output.rglob('run_metadata.json')).read_text())
    assert payload['status'] == ('failed' if failure else 'completed')
    assert payload['parameters']['threshold'] == 8.5
    assert payload['finished_at']


def test_settings_change_is_recorded(monkeypatch):
    from platform_v2.futures.config import settings
    original = recorder.effective_parameters()['futures']['BUY_THRESHOLD']
    monkeypatch.setattr(settings, 'BUY_THRESHOLD', original + 1)
    assert recorder.effective_parameters()['futures']['BUY_THRESHOLD'] == original + 1


def test_input_mutation_during_run_is_reported_as_failure(frozen, tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, 'source_identity', lambda: {'file_sha256': {}})
    monkeypatch.setattr(recorder, 'effective_parameters', lambda: {})
    monkeypatch.setattr(recorder.runpy, 'run_module', lambda *a, **k: (frozen / 'signals.json').write_text('[]'))
    output = tmp_path / 'results'
    with pytest.raises(ValueError, match='hash mismatch'):
        recorder.run_recorded('portfolio_state_replay', frozen, output)
    assert json.loads(next(output.rglob('run_metadata.json')).read_text())['status'] == 'failed'


def test_live_output_path_is_rejected(frozen):
    with pytest.raises(ValueError, match='external'):
        recorder.run_recorded('portfolio_state_replay', frozen, recorder.PROJECT_ROOT / 'platform_v2/runtime/artifacts/test')
