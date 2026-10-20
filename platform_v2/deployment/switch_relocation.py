"""Explicit one-time switch of prepared deployment; never resets any database."""
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVIDENCE = HERE/'migration'
UNIT = Path('/home/sandro/.config/systemd/user/smartsignalhub-runtime.service')
SERVICE = 'smartsignalhub-runtime.service'
PS = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'


def command(args, **kwargs):
    return subprocess.check_output(args, text=True, timeout=55, **kwargs)


def systemctl(*args):
    return command(['systemctl', '--user', *args])


def powershell(code):
    return command([PS, '-NoProfile', '-Command', "$ErrorActionPreference='Stop'; "+code])


def open_attempts():
    path = ROOT/'platform_v2/runtime/database/smartsignalhub_trading.sqlite3'
    with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=10) as db:
        return db.execute("SELECT count(*) FROM cycle_attempt_events s WHERE kind='STARTED' AND NOT EXISTS "
            "(SELECT 1 FROM cycle_attempt_events t WHERE t.attempt_id=s.attempt_id AND t.kind IN "
            "('COMMITTED','FAILED','INTERRUPTED','ABANDONED'))").fetchone()[0]


def set_windows_action(arguments):
    escaped = arguments.replace("'", "''")
    powershell("$t=Get-ScheduledTask -TaskName 'SmartSignalHub-WSL'; "
        "$a=New-ScheduledTaskAction -Execute $t.Actions[0].Execute -Argument '"+escaped+"'; "
        "Set-ScheduledTask -TaskName $t.TaskName -Action $a | Out-Null")


def main():
    before = json.loads((EVIDENCE/'preparation.json').read_text())
    if before['state'] != 'PREPARED_NOT_SWITCHED':
        raise RuntimeError('Preparation already switched or not ready')
    active = json.loads((HERE/'deploy/activation.json').read_text())
    assert hashlib.sha256(gzip.decompress((Path(active['release'])/'source.json.gz').read_bytes())).hexdigest() == before['release_sha256']
    assert UNIT.read_text() == (EVIDENCE/'service.before').read_text()
    assert command(['crontab', '-l']) == (EVIDENCE/'crontab.before').read_text()
    task = json.loads(powershell("Get-ScheduledTask -TaskName 'SmartSignalHub-WSL' | "
        "Select-Object -ExpandProperty Actions | Select-Object Execute,Arguments | ConvertTo-Json -Compress"))
    old_args = task['Arguments']
    assert before['old_root'] in old_args
    new_args = old_args.replace(before['old_root'], str(HERE))
    (EVIDENCE/'windows-task.before.xml').write_text(powershell("Export-ScheduledTask -TaskName 'SmartSignalHub-WSL'"))
    (EVIDENCE/'windows-action.before.json').write_text(json.dumps(task, indent=2)+'\n')
    database_root = ROOT/'platform_v2/runtime/database'
    inodes = {p.name: p.stat().st_ino for p in database_root.glob('*.sqlite3')}
    deadline = time.monotonic()+45
    while open_attempts():
        if time.monotonic() >= deadline:
            raise RuntimeError('Cycles still in progress; service unchanged. Retry between cycles.')
        time.sleep(1)
    stopped = False
    try:
        systemctl('stop', SERVICE)
        stopped = True
        assert systemctl('show', SERVICE, '--property=ActiveState', '--value').strip() == 'inactive'
        with (ROOT/'platform_v2/runtime/research-supervisor.lock').open('r+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            assert open_attempts() == 0, 'Cycle started during shutdown; old service will be restored'
            UNIT.write_text((EVIDENCE/'service.after').read_text())
            subprocess.run(['crontab', str(EVIDENCE/'crontab.after')], check=True, timeout=15)
            set_windows_action(new_args)
            systemctl('daemon-reload')
        systemctl('start', SERVICE)
        time.sleep(3)
        assert systemctl('is-active', SERVICE).strip() == 'active'
        pid = systemctl('show', SERVICE, '--property=MainPID', '--value').strip()
        args = (Path('/proc')/pid/'cmdline').read_bytes().decode().replace('\0', ' ')
        assert str(HERE/'releases') in args
        assert before['old_root'] not in args
        assert inodes == {p.name: p.stat().st_ino for p in database_root.glob('*.sqlite3')}
        after = {'state': 'SWITCHED', 'utc': datetime.now(timezone.utc).isoformat(),
                 'release_sha256': active['release_sha256'], 'main_pid': pid,
                 'activation_close_ms': active['activation_close_ms'], 'database_inodes': inodes,
                 'windows_arguments': new_args}
        (EVIDENCE/'switch.json').write_text(json.dumps(after, indent=2)+'\n')
        before['state'] = 'SWITCHED'
        (EVIDENCE/'preparation.json').write_text(json.dumps(before, indent=2)+'\n')
        print(json.dumps(after, indent=2))
    except BaseException:
        if stopped:
            systemctl('stop', SERVICE)
            UNIT.write_text((EVIDENCE/'service.before').read_text())
            subprocess.run(['crontab', str(EVIDENCE/'crontab.before')], check=True, timeout=15)
            set_windows_action(old_args)
            systemctl('daemon-reload')
            systemctl('start', SERVICE)
        raise


if __name__ == '__main__':
    main()
