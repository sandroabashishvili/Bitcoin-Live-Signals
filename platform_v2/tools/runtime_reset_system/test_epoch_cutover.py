from copy import deepcopy
import json
import pytest
from .epoch_cutover import configs_for_epoch, atomic_json


def test_epoch_changes_both_monitors_without_changing_strategy_or_capital():
    a={'activation_close_ms':899999,'release_sha256':'pinned','sqlite_library':'keep'}
    e={'systems':{s:{'release_sha256':'pinned','activation_close_ms':'899999','config_sha256':s}
        for s in ('spot','futures')}}
    old=deepcopy((a,e));new,expected=configs_for_epoch(a,e,1799999)
    assert (a,e)==old
    assert new['release_sha256']=='pinned' and new['sqlite_library']=='keep'
    assert new['activation_close_ms']==1799999
    for s in ('spot','futures'):
        assert expected['systems'][s]['activation_close_ms']=='1799999'
        assert expected['systems'][s]['config_sha256']==s


@pytest.mark.parametrize('stamp',[0,900000,True,-1])
def test_reject_misaligned_epoch(stamp):
    with pytest.raises(ValueError):configs_for_epoch({}, {}, stamp)


def test_config_staging_does_not_overwrite_unknown_temporary_file(tmp_path):
    target=tmp_path/'activation.json';target.write_text('{"original":true}')
    target.with_name('activation.json.epoch-tmp').write_text('unknown')
    with pytest.raises(FileExistsError):atomic_json(target,{'new':True})
    assert json.loads(target.read_text())=={'original':True}


def test_new_epoch_bootstraps_projection_schema_without_losing_evidence(tmp_path):
    import sqlite3
    from platform_v2.shared.backend.research_evidence.ledger import Ledger
    from platform_v2.shared.backend.persistence.sqlite_schema import initialize_database
    path=tmp_path/'new_trading.sqlite3'
    ledger=Ledger(path)
    ledger.append('research_runs',run_id='first',system='spot',kind='STARTED',payload={})
    initialize_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM runtime_rows').fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM runtime_state').fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM research_runs').fetchone()==(1,)
