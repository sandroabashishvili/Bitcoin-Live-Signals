"""Stdlib-only source pinning and fail-closed IO boundary for raw backtests."""
import gzip,hashlib,importlib.util,json,sys
from pathlib import Path

root=Path(sys.argv[1]).resolve();out=root/'runs'/sys.argv[2]
protocol=json.loads((root/'protocol.json').read_text())
sealed=json.loads((out/'pre_run_manifest.json').read_text())
if hashlib.sha256((root/'protocol.json').read_bytes()).hexdigest()!=sealed['protocol_sha256']:raise ValueError('Protocol changed after sealing')
for name,expected in sealed['files'].items():
    if hashlib.sha256((out/name).read_bytes()).hexdigest()!=expected:raise ValueError('Run input changed after sealing: '+name)
raw=gzip.decompress((root/'source/source.json.gz').read_bytes())
if hashlib.sha256(raw).hexdigest()!=protocol['source_sha256']:raise ValueError('Pinned source hash mismatch')
if hashlib.sha256((root/'market.sqlite3').read_bytes()).hexdigest()!=protocol['market_sha256']:raise ValueError('Frozen market hash mismatch')
payload=json.loads(raw);payload['project_root']=str(out/'isolated_project')
spec=importlib.util.spec_from_file_location('pinned_loader',root/'source/run.py')
loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
sys.meta_path.insert(0,loader.PinnedSource(payload));sys.dont_write_bytecode=True

def guard(event,args):
    if event in ('socket.connect','socket.bind','subprocess.Popen','os.system'):raise PermissionError('Offline backtest cannot use network/processes')
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=Path(args[0]).resolve();mode,flags=args[1],args[2]
        if path.is_relative_to(Path('/home/sandro/SmartSignalHub/platform_v2/runtime')):raise PermissionError('Live runtime access denied')
        writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&3!=0)
        if writing and not path.is_relative_to(out):raise PermissionError('Write outside private run denied')
    if event=='sqlite3.connect' and str(args[0])!=(root/'market.sqlite3').as_uri()+'?mode=ro&immutable=1':raise PermissionError('Only frozen market SQLite allowed')
    mutations={'os.mkdir':(0,),'os.remove':(0,),'os.rmdir':(0,),'os.rename':(0,1),'os.chmod':(0,),'os.symlink':(1,),'os.link':(0,1)}
    if event in mutations and any(not Path(args[i]).resolve().is_relative_to(out) for i in mutations[event]):raise PermissionError('Mutation outside private run denied')

sys.addaudithook(guard)
variant=json.loads((out/'candidate_protocol.json').read_text())['variant']
if variant == 'pullback_audit_v1':
    from pullback_audit import run
    run(root,out)
else:
    from engine import run
    run(root,out,variant=variant)
