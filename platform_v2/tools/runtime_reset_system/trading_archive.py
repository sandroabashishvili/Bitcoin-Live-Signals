"""Recoverable all-system trading-state rotation, preserving market/content.

Only a quiescent-runtime cutover may call this primitive. It does not activate an
epoch, edit deployment, rebuild dashboards or start processes. No standalone CLI.
"""
from contextlib import closing, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

from platform_v2.shared.backend.persistence.database_paths import sqlite_sidecar_paths


NAMES=('smartsignalhub_trading.sqlite3','smartsignalhub_market_data.sqlite3','smartsignalhub_content.sqlite3')


def runtime_processes(project_root, proc_root=Path('/proc')):
    found=[]
    for proc in proc_root.glob('[0-9]*'):
        try:
            if proc.stat().st_uid!=os.getuid():continue
            args=(proc/'cmdline').read_bytes().split(b'\0')
            # sd-pam and other non-dumpable user helpers can hide cwd. Inspect
            # argv first; no cwd access is needed for the known Python launchers.
            # Conservatively reject these modules even from a different cwd.
            if any(arg in (b'platform_v2.tools.runtime_start_system',b'platform_v2.spot.app.run_loop',
                           b'platform_v2.futures.app.run_loop',
                           b'/home/sandro/research_snapshots/readiness_R21_20260927/deploy/start.py',
                           str(project_root/'platform_v2/deployment/deploy/start.py').encode())
                   or arg.startswith(b'platform_v2.futures_hedge.app.') for arg in args):
                found.append(proc.name)
        except (FileNotFoundError,ProcessLookupError):continue
        except PermissionError:
            raise RuntimeError('Cannot prove runtime process absence: '+proc.name)
    return found


@contextmanager
def stopped_runtime_guard(project_root):
    """Never stops a service; fails unless it is already inactive and locked."""
    state=subprocess.run(['systemctl','--user','show','smartsignalhub-runtime.service',
        '--property=ActiveState','--value'],capture_output=True,text=True)
    if state.returncode!=0 or state.stdout.strip()!='inactive':
        raise RuntimeError('Owning user service must be explicitly stopped first')
    lock=project_root/'platform_v2/runtime/research-supervisor.lock'
    with lock.open('r+b') as handle:
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            processes=runtime_processes(project_root)
            if processes:raise RuntimeError('Manual runtime writers still present: '+','.join(processes))
            yield
        finally:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def validate_targets(database_root, archive):
    database_root,archive=database_root.resolve(),archive.resolve()
    if archive.is_relative_to(database_root) or database_root.is_relative_to(archive):
        raise ValueError('Archive must not overlap database root')
    for name in NAMES:
        p=database_root/name
        if not p.is_file() or p.is_symlink():raise ValueError('Required canonical database missing or linked: '+name)
    for system in ('spot','futures','hedge'):
        root=database_root.parent/system
        if root.exists() and (root.is_symlink() or not root.is_dir() or any(root.iterdir())):
            raise ValueError('Legacy runtime state needs separate reviewed archival: '+str(root))
    if archive.exists():raise FileExistsError('Use a new archive directory')


def rotate(database_root: Path, archive: Path, *, writer_guard, preserved_config: dict):
    """Back up ALL DBs, verify, and rotate only trading files under held writer guard.

    writer_guard must be a context manager proving service/manual writers absent
    and holding the supervisor lock for the ENTIRE operation. A bare boolean is
    deliberately not accepted. Callers still need coordinated epoch configuration.
    """
    database_root,archive=database_root.resolve(),archive.resolve()
    validate_targets(database_root,archive)
    with writer_guard:
        # Recheck after acquiring the guard; no mutation precedes it.
        validate_targets(database_root,archive)
        required=sum((database_root/n).stat().st_size for n in NAMES)
        if shutil.disk_usage(archive.parent).free<required+1024**3:
            raise ValueError('Insufficient space for verified self-contained archive')
        archive.mkdir();(archive/'database').mkdir();(archive/'raw_trading').mkdir()
        journal={'status':'PREPARING','moved':[], 'files':{},'deployment_before':preserved_config}
        def save():
            (archive/'transition.json').write_text(json.dumps(journal,indent=2)+'\n')
        save()
        try:
            # Stop guard must cover all three sources: individually consistent
            # online backups do not imply cross-DB consistency during active writes.
            for name in NAMES:
                src=database_root/name;target=archive/'database'/name
                with closing(sqlite3.connect(src.as_uri()+'?mode=ro',uri=True)) as source:
                    with closing(sqlite3.connect(target)) as backup:
                        source.backup(backup)
                        if backup.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
                            raise ValueError('Backup integrity failed: '+name)
                journal['files']['database/'+name]=digest(target)
            # Verify backups again before removing anything from active storage.
            if any(digest(archive/f)!=h for f,h in journal['files'].items()):
                raise ValueError('Archived bytes changed before rotation')
            journal['status']='BACKUPS_VERIFIED';save()
            # Include WAL/SHM if present; never discard sidecars independently.
            for source in sqlite_sidecar_paths(database_root/NAMES[0]):
                if source.exists():
                    target=archive/'raw_trading'/source.name
                    source.rename(target)
                    journal['moved'].append(source.name);save()
            journal['status']='TRADING_ROTATED_PENDING_EPOCH_ACTIVATION';save()
        except BaseException:
            # Restore only exact moved files; never overwrite newly appeared data.
            rollback=[]
            for name in reversed(journal['moved']):
                source=archive/'raw_trading'/name;target=database_root/name
                if target.exists():rollback.append('REFUSED_OVERWRITE:'+name)
                elif source.exists():source.rename(target)
            journal['status']='FAILED_ROLLED_BACK' if not rollback else 'FAILED_MANUAL_RECOVERY_REQUIRED'
            journal['rollback_issues']=rollback;save()
            raise
        return journal
