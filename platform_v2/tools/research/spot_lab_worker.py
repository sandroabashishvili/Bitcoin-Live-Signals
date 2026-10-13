"""Stdlib-only pinned bootstrap for complete Spot replay."""
import functools
import gzip
import hashlib
import importlib.util
import json
import sqlite3
import sys
import zlib
from pathlib import Path


def main():
    root,name,model,limit,run_id=Path(sys.argv[1]).resolve(),sys.argv[2],sys.argv[3],int(sys.argv[4]),sys.argv[5]
    output=root/'spot_runs'/run_id
    protocol=json.loads((root/'protocol.json').read_text())
    raw=gzip.decompress((root/'source/source.json.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=protocol['source_sha256']:
        raise ValueError('Source hash mismatch')
    payload=json.loads(raw)
    if name!='baseline':
        payload['files']['platform_v2/spot/services/signal/mtf_context_service.py']=(output/'mtf.py').read_text()
    payload['project_root']=str(output/'isolated_project')
    spec=importlib.util.spec_from_file_location('pinned_loader',root/'source/run.py')
    loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
    sys.meta_path.insert(0,loader.PinnedSource(payload));sys.dont_write_bytecode=True
    def guard(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system'):
            raise PermissionError('Spot replay cannot access network or spawn processes')
        if event=='open' and isinstance(args[0],(str,bytes)):
            path=Path(args[0]).resolve();mode,flags=args[1],args[2]
            if path.is_relative_to(Path('/home/sandro/SmartSignalHub/platform_v2/runtime')):
                raise PermissionError('Live runtime access denied')
            writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&3!=0)
            if writing and not path.is_relative_to(output):raise PermissionError('Write outside run denied')
        mutations={'os.mkdir':(0,),'os.remove':(0,),'os.rmdir':(0,),'os.rename':(0,1),'os.chmod':(0,),'os.symlink':(1,),'os.link':(0,1)}
        if event in mutations:
            if any(not isinstance(args[i],(str,bytes)) or not Path(args[i]).resolve().is_relative_to(output) for i in mutations[event]):
                raise PermissionError('Filesystem mutation outside run denied')
        if event=='sqlite3.connect':
            readonly=str(args[0]).startswith((root/'data').as_uri()+'/') and 'mode=ro' in str(args[0])
            private=Path(str(args[0])).resolve()==output/'replay.sqlite3'
            if not readonly and not private:raise PermissionError('Only frozen input/private output SQLite allowed')
    sys.addaudithook(guard)
    db=sqlite3.connect((root/'data/trading.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
    prices=sqlite3.connect((root/'data/market.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
    @functools.lru_cache(maxsize=256)
    def blob(sha):
        row=db.execute('SELECT compressed_json FROM research_blobs WHERE sha256=?',(sha,)).fetchone()
        if row is None:raise ValueError('Missing evidence')
        raw=zlib.decompress(row[0])
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Evidence hash mismatch')
        return json.loads(raw)
    def tail(manifest,count):
        rows=[]
        for ref in reversed(manifest['chunks']):
            rows=blob(ref)+rows
            if len(rows)>=count:break
        return rows
    from spot_lab_support import SpotReplay
    replay=SpotReplay(output,db,prices,blob,tail,protocol,model,name=='baseline',limit)
    for oid,run,attempt,cycle,text in db.execute("SELECT id,run_id,attempt_id,cycle_key,payload_json FROM research_first_live_decisions WHERE system='spot' ORDER BY id"):
        first=json.loads(text);stamp=first['record']['timestamp_ms']
        if not protocol['start_ms']<=stamp<protocol['end_ms']:continue
        if limit and len(replay.cycles)>=limit:break
        chain=[json.loads(r[0]) for r in db.execute("SELECT payload_json FROM decision_observations WHERE system='spot' AND cycle_key=? AND run_id=? AND attempt_id IS ? AND kind='LIVE_OBSERVED' AND id>=? ORDER BY id",(cycle,run,attempt,oid))]
        if not chain or any(not o.get('evidence_complete') for o in chain):raise ValueError('Incomplete first-attempt chain')
        replay.step(oid,first,chain[-1])
        if len(replay.cycles)%100==0:print('Spot replayed',len(replay.cycles),flush=True)
    result=replay.finish()
    print('Spot complete:',len(replay.cycles),'historical parity:',result['historical_parity_ok'],'net change:',result['period_net_pnl'],flush=True)
    return 0 if result['passed'] else 2


if __name__=='__main__':raise SystemExit(main())
