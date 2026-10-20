"""Reviewed cutover candidate only. Requires explicit activation.json; never stops a process."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

def require(ok,reason):
    if not ok:raise RuntimeError(reason)

ROOT=Path('/home/sandro/SmartSignalHub')
HERE=Path(__file__).resolve().parent
config=json.loads((HERE/'activation.json').read_text())
require(config.get('approved') is True,'cutover not approved')
require(isinstance(config['activation_close_ms'],int) and config['activation_close_ms'] % 900000==899999,'invalid epoch')
release=Path(config['release'])
import gzip
require(hashlib.sha256(gzip.decompress((release/'source.json.gz').read_bytes())).hexdigest()==config['release_sha256'],'release hash mismatch')
require(hashlib.sha256(Path(config['sqlite_library']).read_bytes()).hexdigest()==config['sqlite_library_sha256'],'SQLite library hash mismatch')
with sqlite3.connect(':memory:') as db:
    require(db.execute('select sqlite_source_id()').fetchone()[0]==config['sqlite_source_id'],'loaded SQLite mismatch')
lock=ROOT/'platform_v2/runtime/research-supervisor.lock'
fd=os.open(lock,os.O_CREAT|os.O_RDWR,0o600)
fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);os.set_inheritable(fd,True)
# A legacy terminal launch does not know our lock; refuse it explicitly.
for proc in Path('/proc').glob('[0-9]*'):
    if proc.name==str(os.getpid()):continue
    try:
        args=(proc/'cmdline').read_bytes().split(b'\0')
        if (proc/'cwd').resolve()!=ROOT:continue
        if any(m.encode() in args for m in ('platform_v2.tools.runtime_start_system','platform_v2.spot.app.run_loop','platform_v2.futures.app.run_loop')):
            raise RuntimeError('existing runtime process: '+proc.name)
    except (PermissionError,FileNotFoundError,ProcessLookupError):pass
os.chdir(ROOT)
env=dict(os.environ,SSH_RESEARCH_EVIDENCE='1',SSH_RESEARCH_ATOMIC_SIMULATION='1',
         SSH_RESEARCH_BACKFILL='1',SSH_RESEARCH_ACTIVATION_CLOSE_MS=str(config['activation_close_ms']),PYTHONUNBUFFERED='1')
python=str(ROOT/'venv/bin/python')
os.execve(python,[python,str(release/'run.py'),'--release',str(release/'source.json.gz'),
    '--sha256',config['release_sha256'],'--module','platform_v2.tools.runtime_start_system'],env)
