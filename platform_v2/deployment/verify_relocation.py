"""Read-only operational acceptance; writes a local acceptance report only."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    migration = json.loads((HERE/'migration/switch.json').read_text())
    active = json.loads((HERE/'deploy/activation.json').read_text())
    service = subprocess.check_output(['systemctl', '--user', 'show', 'smartsignalhub-runtime.service',
        '--property=MainPID', '--value'], text=True).strip()
    assert int(service) > 0
    arguments = (Path('/proc')/service/'cmdline').read_bytes().decode().replace('\0', ' ')
    assert str(HERE/'releases') in arguments
    assert active['release_sha256'] == migration['release_sha256']
    assert active['activation_close_ms'] == migration['activation_close_ms']
    for relative, expected in json.loads((HERE/'migration/preparation.json').read_text())['preserved_files'].items():
        assert hashlib.sha256((HERE/relative).read_bytes()).hexdigest() == expected
    cron = subprocess.check_output(['crontab', '-l'], text=True)
    assert str(HERE/'deploy/check-health.py') in cron
    assert '/research_snapshots/' not in cron
    database_root = ROOT/'platform_v2/runtime/database'
    assert migration['database_inodes'] == {p.name:p.stat().st_ino for p in database_root.glob('*.sqlite3')}
    with sqlite3.connect((database_root/'smartsignalhub_trading.sqlite3').as_uri()+'?mode=ro', uri=True) as db:
        runs = {}
        for system in ('spot', 'futures'):
            row = db.execute("SELECT payload_json FROM research_runs WHERE system=? AND kind='STARTED' ORDER BY id DESC LIMIT 1", (system,)).fetchone()
            data = json.loads(row[0])
            assert data['release_sha256'] == active['release_sha256']
            assert str(data['activation_close_ms']) == str(active['activation_close_ms'])
            assert data['release_verified'] is True
            runs[system] = {key:data.get(key) for key in ('release_sha256', 'config_sha256', 'activation_close_ms', 'atomic_simulation', 'release_verified')}
        events = []
        for system, kind, payload in db.execute(
                "SELECT system,kind,payload_json FROM cycle_attempt_events WHERE kind IN "
                "('COMMITTED','FAILED','INTERRUPTED') ORDER BY id DESC LIMIT 8"):
            data = json.loads(payload)
            events.append({'system':system, 'kind':kind, **{key:data.get(key) for key in
                ('actual_cycle_key', 'skipped', 'skip_reason', 'recorder_errors')}})
    health = json.loads((ROOT/'platform_v2/runtime/research_health/latest.json').read_text())
    report = {'checked_utc':datetime.now(timezone.utc).isoformat(), 'state':'VERIFIED',
        'service_pid':service, 'code_and_sqlite_unchanged':True, 'database_files_preserved':True,
        'epoch_preserved':True, 'runs':runs, 'latest_attempt_events':events, 'health':health,
        'scope':'Live path relocation acceptance; not a Windows reboot test or profitability claim.'}
    (HERE/'migration/acceptance.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('checked_utc', 'state', 'service_pid',
        'code_and_sqlite_unchanged', 'database_files_preserved', 'epoch_preserved',
        'latest_attempt_events')}, indent=2))


if __name__ == '__main__':
    main()
