"""Offline relocation tests: never touch the real service or deployment."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def prepared_source(tmp_path, monkeypatch):
    script = Path(__file__).with_name('prepare_relocation.py')
    spec = importlib.util.spec_from_file_location('prepare_relocation_under_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old, new = tmp_path/'old', tmp_path/'new'
    new.mkdir()
    (old/'deploy').mkdir(parents=True)
    (old/'sqlite').mkdir()
    source = b'{"format":1,"files":{}}'
    sha = hashlib.sha256(source).hexdigest()
    release = old/'releases'/sha
    release.mkdir(parents=True)
    (release/'source.json.gz').write_bytes(gzip.compress(source))
    (release/'run.py').write_text('# unchanged launcher\n')
    (release/'sha256.txt').write_text(sha+'\n')
    (old/'releases'/'inactive').mkdir()
    (old/'sqlite/libsqlite3.so.0').write_bytes(b'fake-native-library')
    (old/'sqlite/verification.json').write_text('{}')
    activation = {'approved':True, 'release':str(release), 'release_sha256':sha,
                  'activation_close_ms':1792337399999,
                  'sqlite_library':str(old/'sqlite/libsqlite3.so.0'),
                  'sqlite_library_sha256':module.sha(old/'sqlite/libsqlite3.so.0')}
    (old/'deploy/activation.json').write_text(json.dumps(activation))
    (old/'deploy/start.py').write_text('# '+str(old)+'\n')
    unit = tmp_path/'service'
    unit.write_text('ExecStart='+str(old/'deploy/start.py')+'\n')
    monkeypatch.setattr(module, 'OLD', old)
    monkeypatch.setattr(module, 'NEW', new)
    monkeypatch.setattr(module, 'UNIT', unit)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *a, **k:'5 * * * * '+str(old/'deploy/start.py')+'\n')
    return module, activation


def test_only_selected_snapshot_is_copied(prepared_source):
    module, before = prepared_source
    module.main()
    assert [p.name for p in (module.NEW/'releases').iterdir()] == [before['release_sha256']]
    after = json.loads((module.NEW/'deploy/activation.json').read_text())
    assert after['release_sha256'] == before['release_sha256']
    assert after['activation_close_ms'] == before['activation_close_ms']
    assert str(module.OLD) not in (module.NEW/'deploy/activation.json').read_text()
    assert module.UNIT.read_text() == (module.NEW/'migration/service.before').read_text()
    assert str(module.OLD) in module.UNIT.read_text()  # prepare never switches
    assert (module.OLD/'releases/inactive').is_dir()  # no source deletion


def test_preparation_rejects_existing_destination(prepared_source):
    module, _ = prepared_source
    module.main()
    with pytest.raises(RuntimeError, match='Already exists'):
        module.main()


def test_invalid_snapshot_rejected_before_copy(prepared_source):
    module, config = prepared_source
    (Path(config['release'])/'source.json.gz').write_bytes(gzip.compress(b'tampered'))
    with pytest.raises(AssertionError):
        module.main()
    assert not (module.NEW/'migration').exists()
