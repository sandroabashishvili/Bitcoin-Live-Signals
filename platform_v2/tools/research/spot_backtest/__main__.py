"""Create/run independent raw-market Spot backtests. No deployment operations."""
import argparse,hashlib,json,shutil,sqlite3,subprocess,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from . import common as lab
from . import dataset
from .candidates import PROTOCOL, ISOLATED_VARIANTS
from .pullback_audit import AUDIT_PROTOCOL

RUNS = ('baseline', 'unchanged', 'control_v2', 'votes_existing_v1', 'scenarios_votes_v1',
        'scenarios_control_v2', 'pullback_audit_v1', *ISOLATED_VARIANTS)

ROOT=Path('/home/sandro/SmartSignalHub')


def prepare(folder):
    folder=lab.outside_live(folder);folder.mkdir(parents=True,exist_ok=False)
    # An explicit offline experiment may capture its input code on demand.
    # Live trading never selects or imports this research-only capture.
    from platform_v2.shared.backend.research_evidence.release import build
    release, source_sha256 = build(ROOT, folder/'capture')
    release.chmod(0o755)
    release.rename(folder/'source')
    (folder/'source').chmod(0o555)
    (folder/'capture').rmdir()
    end=int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()*1000)
    sources=[ROOT/'platform_v2/runtime/database/smartsignalhub_market_data.sqlite3']
    public=[]
    with sqlite3.connect(folder/'market.sqlite3') as db:
        dataset.create_schema(db)
        for source in sources:
            dataset.import_market(db,source,end);db.commit();print('Imported',source.parent.parent.name,flush=True)
        cov=dataset.coverage(db)
        first=cov['15m']['first_ms']
        start_date=datetime.fromtimestamp(first/1000,timezone.utc).replace(day=1)
        this_month=datetime.fromtimestamp(end/1000,timezone.utc).replace(day=1)
        periods=[]
        while start_date<this_month:
            periods.append(start_date.strftime('%Y-%m'))
            start_date=(start_date.replace(day=28)+timedelta(days=4)).replace(day=1)
        day=this_month
        while int(day.timestamp()*1000)<end:
            periods.append(day.strftime('%Y-%m-%d'));day+=timedelta(days=1)
        for period in periods:
            try:
                rows,meta=dataset.public_file(folder/'public',period)
                meta.update(dataset.add_public_flow(db,rows,meta['url']));meta['status']='verified'
            except (HTTPError,URLError,TimeoutError) as exc:
                meta={'period':period,'status':'unavailable','reason':str(exc)}
            public.append(meta);db.commit();print('Historical flow',period,meta['status'],meta.get('matched_local_candles',0),flush=True)
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        coverage=dataset.coverage(db)
        flow=db.execute('SELECT count(*),min(close_ms),max(close_ms) FROM flow').fetchone()
        conflicts=db.execute('SELECT count(*) FROM conflicts').fetchone()[0]
        crosscheck=dataset.crosscheck_flow(db,sources[0])
        lab.write(folder/'flow_crosscheck.json',crosscheck)
    protocol={'format':'raw-spot-backtest-v1','created_utc':datetime.now(timezone.utc).isoformat(),
        'source_sha256':source_sha256,'cutoff_ms':end,'coverage':coverage,
        'flow_candles':flow[0],'flow_first_close_ms':flow[1],'flow_last_close_ms':flow[2],
        'overlap_conflicts':conflicts,'source_priority':'Live market SQLite first; archived market SQLite newest to oldest; conflicts counted, never silently overwritten.',
        'public_imports':public,'market_sha256':lab.digest(folder/'market.sqlite3'),
        'source_archive_sha256':lab.digest(folder/'source/source.json.gz'),
        'strategy':'Current pinned Spot formulas, permissions, sizing, fees and exits. No new five-scenario or 4-of-6 candidate yet.',
        'initial_account':'Independent empty paper account per fully covered segment; no inherited live positions.',
        'flow_model':'Official 15m kline taker-buy base volume; sellers=total-buy; exchange trade count is NOT aggregate trade count.',
        'execution':'Entry at exact next 1m open with a 60-second post-close decision delay; OHLC-based native exits, no tick-fill claim.',
        'warmup':'200 consecutive closed bars for each of 5m/15m/4h; native causal indicator history restarts at gaps.'}
    lab.write(folder/'protocol.json',protocol)
    (folder/'market.sqlite3').chmod(0o444)
    print('Prepared',folder,flush=True)


def run(folder,name):
    folder=lab.outside_live(folder);p=json.loads((folder/'protocol.json').read_text())
    if name not in RUNS:raise ValueError('Unknown predeclared candidate')
    if lab.digest(folder/'market.sqlite3')!=p['market_sha256']:raise ValueError('Frozen market hash mismatch')
    crosscheck=json.loads((folder/'flow_crosscheck.json').read_text())
    if crosscheck['volume_mismatches'] or crosscheck['checked_candles']<1:
        raise ValueError('Historical flow calibration against complete aggregate trades is required')
    isolation = name in ISOLATED_VARIANTS or name == 'scenarios_control_v2'
    if isolation:
        anchor = folder/'runs/scenarios_votes_v1/candidate_protocol.json'
        if json.loads(anchor.read_text())['rules'] != PROTOCOL:
            raise ValueError('Scenario rules differ from the original combined experiment')
    out=folder/'runs'/name;out.mkdir(parents=True,exist_ok=False)
    for source,target in ((Path(__file__).with_name('worker.py'),'worker.py'),
        (Path(__file__).with_name('engine.py'),'engine.py'),(Path(__file__).with_name('candidates.py'),'candidates.py'),
        (Path(__file__).with_name('dataset.py'),'inputs.py'),
        (Path(__file__).with_name('paired_support.py'),'paired_support.py'),
        (Path(__file__).with_name('native_adapters.py'),'native_adapters.py')):shutil.copyfile(source,out/target)
    if name == 'pullback_audit_v1':
        for source,target in (('pullback_audit.py','pullback_audit.py'),('compare.py','comparison_helpers.py')):
            shutil.copyfile(Path(__file__).with_name(source),out/target)
    canonical = 'scenarios_votes_v1' if name == 'scenarios_control_v2' else name
    candidate_protocol = {'variant':canonical,'rules':PROTOCOL}
    paired_path=folder/'paired_account_protocol.json'
    if paired_path.exists():
        paired=json.loads(paired_path.read_text())
        if name not in paired['arms']:raise ValueError('Undeclared matched-account arm')
        records=folder/'recorded_signals.json'
        if lab.digest(records)!=paired['recorded_signals_sha256']:raise ValueError('Recorded signals changed')
        candidate_protocol['paired_account']=paired|{'mode':paired['arms'][name]}
        shutil.copyfile(records,out/'recorded_signals.json')
    experiment_path=folder/'continuous_experiment_protocol.json'
    if experiment_path.exists():
        experiment=json.loads(experiment_path.read_text())
        if experiment['market_sha256']!=p['market_sha256'] or experiment['candidate_rules']!=PROTOCOL:
            raise ValueError('Continuous experiment inputs or declared rules changed')
        if name not in experiment['runs']:raise ValueError('Run not declared for continuous experiment')
        candidate_protocol['continuous_experiment']=experiment
    if name == 'pullback_audit_v1':
        candidate_protocol['audit'] = AUDIT_PROTOCOL
        candidate_protocol['reference_manifest_sha256'] = lab.digest(folder/'runs/scenario_pullback_v1/manifest.json')
    if name in ISOLATED_VARIANTS:
        candidate_protocol['isolation'] = {'active_scenarios':[ISOLATED_VARIANTS[name]],
            'reference':'scenarios_votes_v1', 'reference_manifest_sha256':lab.digest(folder/'runs/scenarios_votes_v1/manifest.json'),
            'change':'Only enabled scenario set changes; all numeric definitions, native execution and segment starts unchanged.',
            'accounts':'Fresh independent account per covered segment for THIS scenario; never reuse combined-strategy positions.'}
    lab.write(out/'candidate_protocol.json',candidate_protocol)
    lab.write(out/'pre_run_manifest.json',{'protocol_sha256':lab.digest(folder/'protocol.json'),
        'files':{f.name:lab.digest(f) for f in out.iterdir() if f.is_file()}})
    rc=lab.launch_recorded([sys.executable,'-B',str(out/'worker.py'),str(folder),name],out)
    if rc:raise RuntimeError('Backtest failed; retained evidence: '+str(out))
    lab.write(out/'manifest.json',{'protocol_sha256':lab.digest(folder/'protocol.json'),
        'files':{f.name:lab.digest(f) for f in out.iterdir() if f.is_file()}})
    print(out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','run']);parser.add_argument('workspace',type=Path)
    parser.add_argument('--name',choices=RUNS,default='baseline')
    args=parser.parse_args()
    prepare(args.workspace) if args.command=='prepare' else run(args.workspace,args.name)


if __name__=='__main__':
    main()
