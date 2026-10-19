"""Explicit all-system paper-account cutover. Never runs on import.

Default is validation only. --apply is an operator-authorized maintenance action.
Failures after rotation leave the owning service stopped with recovery evidence.
"""
import argparse
from contextlib import closing, nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time

from .epoch_plan import DEPLOY
from .trading_archive import NAMES, digest, rotate, stopped_runtime_guard

ROOT=Path('/home/sandro/SmartSignalHub')
SERVICE='smartsignalhub-runtime.service'


def configs_for_epoch(activation, expectations, close_ms):
    if type(close_ms) is not int or close_ms<899999 or close_ms%900000!=899999:
        raise ValueError('Epoch must be an exact closed 15m candle')
    a,e=deepcopy(activation),deepcopy(expectations)
    a['activation_close_ms']=close_ms
    a['activation_requested_utc']=datetime.now(timezone.utc).isoformat()
    for system in ('spot','futures'):
        if e['systems'][system]['release_sha256']!=a['release_sha256']:
            raise ValueError('Release expectation mismatch')
        e['systems'][system]['activation_close_ms']=str(close_ms)
    return a,e


def atomic_json(path, value):
    temporary=path.with_name(path.name+'.epoch-tmp')
    with temporary.open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush()
        import os
        os.fsync(stream.fileno())
    temporary.replace(path)


def open_attempts(database):
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        return db.execute("SELECT count(*) FROM cycle_attempt_events s WHERE kind='STARTED' AND NOT EXISTS "
            "(SELECT 1 FROM cycle_attempt_events t WHERE t.attempt_id=s.attempt_id AND t.kind IN "
            "('COMMITTED','FAILED','INTERRUPTED','ABANDONED'))").fetchone()[0]


def run(plan, archive, apply=False):
    plan,archive=plan.resolve(),archive.resolve()
    manifest=json.loads((plan/'preparation_manifest.json').read_text())
    for name,h in manifest['files'].items():
        if digest(plan/name)!=h:raise ValueError('Preparation evidence changed: '+name)
    if manifest['scope']!=['spot','futures','hedge']:raise ValueError('All-system approval scope missing')
    activation=json.loads((DEPLOY/'activation.json').read_text())
    expectations=json.loads((DEPLOY/'expectations.json').read_text())
    for name in ('activation.json','expectations.json','monitor-command.json','start.py'):
        if digest(DEPLOY/name)!=digest(plan/name):raise ValueError('Deployment drift after preparation: '+name)
    raw=gzip.decompress((Path(activation['release'])/'source.json.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=activation['release_sha256']:raise ValueError('Pinned source changed')
    # Active evidence flags are checked again below; never rotate real-money state.
    from platform_v2.futures.config import load_execution_profile
    if load_execution_profile().mode!='simulation':raise ValueError('Live execution is out of scope')
    database=ROOT/'platform_v2/runtime/database';trading=database/NAMES[0]
    if archive.exists() or not archive.parent.is_dir():raise ValueError('Use a new archive in an existing parent')
    if archive.is_relative_to(ROOT):raise ValueError('Archive must be outside checkout/runtime')
    status=subprocess.run(['systemctl','--user','is-active',SERVICE],capture_output=True,text=True)
    if status.stdout.strip()!='active':raise ValueError('Expected current owning service active before reviewed cutover')
    print(json.dumps({'validated':True,'apply':apply,'archive':str(archive),'open_attempts':open_attempts(trading)}),flush=True)
    if not apply:return
    # Allow a running cycle to finish before stopping; never silently kill a stale cycle.
    deadline=time.monotonic()+240
    while open_attempts(trading):
        if time.monotonic()>deadline:raise RuntimeError('Current attempts did not finish; no service stop or reset performed')
        print('Waiting for current atomic cycle to finish',flush=True);time.sleep(5)
    subprocess.run(['systemctl','--user','stop',SERVICE],check=True,timeout=60)
    stopped=datetime.now(timezone.utc).isoformat()
    print('Owning service stopped; acquiring writer guard',flush=True)
    # Hold lock across rotation AND config update, not just file movement.
    with stopped_runtime_guard(ROOT):
        for system in ('spot','futures'):
            with closing(sqlite3.connect(trading.as_uri()+'?mode=ro',uri=True)) as db:
                row=db.execute("SELECT payload_json FROM research_runs WHERE system=? AND kind='STARTED' ORDER BY id DESC LIMIT 1",(system,)).fetchone()
                run_info=json.loads(row[0]) if row else {}
                if run_info.get('atomic_simulation') is not True or run_info.get('release_sha256')!=activation['release_sha256']:
                    raise ValueError('Active frozen simulation/release not verified: '+system)
        preserved_bytes={str(p):digest(p) for name in NAMES[1:] for p in
            (database/name,Path(str(database/name)+'-wal')) if p.exists()}
        journal=rotate(database,archive,writer_guard=nullcontext(),preserved_config={
            'activation':activation,'expectations':expectations})
        before=archive/'deployment_before';before.mkdir()
        for name in ('activation.json','expectations.json','monitor-command.json','start.py','check-health.py'):
            shutil.copyfile(DEPLOY/name,before/name)
        shutil.copyfile(Path(__file__),archive/'cutover_source.py')
        # Old market/content bytes must remain in place until restart, not be recreated.
        if any(not Path(p).exists() or digest(Path(p))!=h for p,h in preserved_bytes.items()):
            raise RuntimeError('Market/content main or WAL bytes changed before restart')
        # initialize_run creates evidence tables first. Native cycle guards read
        # runtime_state before any first write, so bootstrap projection schema
        # explicitly while all writers are still stopped.
        from platform_v2.shared.backend.persistence.sqlite_schema import initialize_database
        initialize_database(trading)
        now=int(time.time()*1000);epoch=now//900000*900000-1
        a,e=configs_for_epoch(activation,expectations,epoch)
        backup={'format':'verified-trading-epoch-archive-v1','completed_ms':now,
            'files':journal['files'],'verification':'SQLite backup integrity and SHA-256 readback; not a full application restore drill'}
        (archive/'manifest.json').write_text(json.dumps(backup,indent=2)+'\n')
        monitor=json.loads((DEPLOY/'monitor-command.json').read_text())
        monitor[monitor.index('--backup-manifest')+1]=str(archive/'manifest.json')
        try:
            atomic_json(DEPLOY/'activation.json',a)
            atomic_json(DEPLOY/'expectations.json',e)
            atomic_json(DEPLOY/'monitor-command.json',monitor)
        except BaseException:
            # Service stays stopped. Both original configs and raw DB are recoverable.
            (archive/'CONFIG_UPDATE_FAILED.txt').write_text('Do not restart. Restore deployment_before and raw_trading together.\n')
            raise
        receipt={'status':'ROTATED_CONFIGURED_PENDING_FIRST_CYCLES','stopped_utc':stopped,
            'new_activation_close_ms':epoch,'release_sha256':a['release_sha256'],
            'scope':['spot','futures','hedge'],'market_content_preserved':True,
            'preserved_database_files_sha256':preserved_bytes,
            'deployment_after_sha256':{n:digest(DEPLOY/n) for n in ('activation.json','expectations.json','monitor-command.json')}}
        (archive/'cutover.json').write_text(json.dumps(receipt,indent=2)+'\n')
    subprocess.run(['systemctl','--user','start',SERVICE],check=True,timeout=60)
    print(json.dumps(receipt,indent=2),flush=True)
    print('Service start requested. Post-start acceptance is still required.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path);parser.add_argument('archive',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();run(args.plan,args.archive,args.apply)
