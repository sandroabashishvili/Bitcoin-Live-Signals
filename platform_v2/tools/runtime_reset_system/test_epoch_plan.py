from contextlib import contextmanager, nullcontext
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import pytest

from platform_v2.tools.runtime_reset_system.epoch_plan import assert_orderflow, readonly
from platform_v2.tools.runtime_reset_system.trading_archive import NAMES, digest, rotate


def make_dbs(root):
    root.mkdir()
    for name in NAMES:
        with sqlite3.connect(root/name) as db:
            db.execute('CREATE TABLE marker(value TEXT)')
            db.execute('INSERT INTO marker VALUES (?)',(name,))


def test_complete_flow_requires_exact_closed_15m_window():
    row={'window_start_ms':900000,'window_end_ms':1799999,'completeness':'COMPLETE_CLOSED_WINDOW_V1'}
    assert assert_orderflow(row)
    assert not assert_orderflow(row|{'window_end_ms':1800000})
    assert not assert_orderflow(row|{'completeness':'UNKNOWN'})
    assert not assert_orderflow({})


def test_inspection_cannot_write_existing_db_or_create_missing_db(tmp_path):
    path=tmp_path/'data.sqlite3'
    with pytest.raises(sqlite3.OperationalError):
        with readonly(path):pass
    assert not path.exists()
    with sqlite3.connect(path) as db:db.execute('CREATE TABLE example(value)')
    with readonly(path) as db:
        with pytest.raises(sqlite3.OperationalError):db.execute('INSERT INTO example VALUES (1)')


def test_rotation_keeps_market_and_news_and_archives_complete_trading(tmp_path):
    root=tmp_path/'live';make_dbs(root)
    old={name:digest(root/name) for name in NAMES}
    archive=tmp_path/'archive'
    journal=rotate(root,archive,writer_guard=nullcontext(),preserved_config={'epoch':123})
    assert journal['status']=='TRADING_ROTATED_PENDING_EPOCH_ACTIVATION'
    assert not (root/NAMES[0]).exists()
    for name in NAMES[1:]:assert digest(root/name)==old[name]
    for name in NAMES:
        with sqlite3.connect(archive/'database'/name) as db:
            assert db.execute('SELECT value FROM marker').fetchone()[0]==name
    assert (archive/'raw_trading'/NAMES[0]).exists()


def test_writer_guard_failure_makes_no_archive_or_live_changes(tmp_path):
    root=tmp_path/'live';make_dbs(root);archive=tmp_path/'archive'
    @contextmanager
    def active_writer():
        raise RuntimeError('writer active')
        yield
    with pytest.raises(RuntimeError,match='writer active'):
        rotate(root,archive,writer_guard=active_writer(),preserved_config={})
    assert not archive.exists()
    assert all((root/name).exists() for name in NAMES)


def test_backup_failure_does_not_remove_original_databases(tmp_path,monkeypatch):
    import platform_v2.tools.runtime_reset_system.trading_archive as mod
    root=tmp_path/'live';make_dbs(root);archive=tmp_path/'archive'
    def fail(path):raise OSError('simulated archive checksum failure')
    monkeypatch.setattr(mod,'digest',fail)
    with pytest.raises(OSError):rotate(root,archive,writer_guard=nullcontext(),preserved_config={})
    assert all((root/name).exists() for name in NAMES)
    assert json.loads((archive/'transition.json').read_text())['status']=='FAILED_ROLLED_BACK'


def test_archive_refuses_overlapping_or_existing_destination(tmp_path):
    root=tmp_path/'live';make_dbs(root)
    with pytest.raises(ValueError):rotate(root,root/'archive',writer_guard=nullcontext(),preserved_config={})
    existing=tmp_path/'archive';existing.mkdir()
    with pytest.raises(FileExistsError):rotate(root,existing,writer_guard=nullcontext(),preserved_config={})


def test_real_guard_rejects_active_service_before_lock_access(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import platform_v2.tools.runtime_reset_system.trading_archive as mod
    monkeypatch.setattr(mod.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout='active\n'))
    with pytest.raises(RuntimeError,match='explicitly stopped'):
        with mod.stopped_runtime_guard(tmp_path):pytest.fail('must not enter')
    assert not (tmp_path/'platform_v2').exists()


def test_real_guard_requires_no_manual_runtime_writers(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import platform_v2.tools.runtime_reset_system.trading_archive as mod
    monkeypatch.setattr(mod.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout='inactive\n'))
    p=tmp_path/'platform_v2/runtime/research-supervisor.lock';p.parent.mkdir(parents=True);p.touch()
    monkeypatch.setattr(mod,'runtime_processes',lambda root:['123'])
    with pytest.raises(RuntimeError,match='Manual runtime writers'):
        with mod.stopped_runtime_guard(tmp_path):pytest.fail('must not enter')
    monkeypatch.setattr(mod,'runtime_processes',lambda root:[])
    with mod.stopped_runtime_guard(tmp_path):pass


def test_rotation_refuses_to_leave_legacy_engine_state_active(tmp_path):
    root=tmp_path/'database';make_dbs(root)
    state=tmp_path/'futures/state';state.mkdir(parents=True)
    (state/'engine.json').write_text('{}')
    with pytest.raises(ValueError,match='Legacy runtime state'):
        rotate(root,tmp_path/'archive',writer_guard=nullcontext(),preserved_config={})
    assert all((root/name).exists() for name in NAMES)


def test_failure_after_move_restores_original_trading_file(tmp_path,monkeypatch):
    root=tmp_path/'database';make_dbs(root);archive=tmp_path/'archive'
    original=digest(root/NAMES[0]);write=Path.write_text;calls=[]
    def fail_once(path,*args,**kwargs):
        if path.name=='transition.json':
            calls.append(1)
            if len(calls)==3:raise OSError('simulated journal failure after move')
        return write(path,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',fail_once)
    with pytest.raises(OSError,match='after move'):
        rotate(root,archive,writer_guard=nullcontext(),preserved_config={})
    assert digest(root/NAMES[0])==original
    assert json.loads((archive/'transition.json').read_text())['status']=='FAILED_ROLLED_BACK'


def test_process_guard_does_not_need_non_runtime_helpers_cwd(tmp_path):
    from .trading_archive import runtime_processes
    helper=tmp_path/'289';helper.mkdir();(helper/'cmdline').write_bytes(b'')
    (helper/'cwd').symlink_to('/unreadable-helper-cwd')
    assert runtime_processes(tmp_path,proc_root=tmp_path)==[]
    runtime=tmp_path/'300';runtime.mkdir()
    (runtime/'cmdline').write_bytes(b'python\0-m\0platform_v2.spot.app.run_loop\0')
    assert runtime_processes(tmp_path,proc_root=tmp_path)==['300']
