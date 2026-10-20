"""Prepare a read-only preflight for an ALL-system trading epoch transition.

This module cannot stop/restart services, reset databases, or change activation.
Usage: python -m platform_v2.tools.runtime_reset_system.epoch_plan NEW_OUTPUT
"""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

from platform_v2.shared.backend.persistence.database_paths import (
    DATABASE_ROOT, TRADING_DATABASE_PATH, MARKET_DATA_DATABASE_PATH, CONTENT_DATABASE_PATH,
)

DEPLOY = Path(__file__).resolve().parents[2] / 'deployment' / 'deploy'
SYSTEMS = ('spot', 'futures', 'hedge')


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


@contextmanager
def readonly(path):
    # Live WAL is visible. immutable=1 would incorrectly omit committed WAL rows.
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=10)
    db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
    try:yield db
    finally:db.close()


def assert_orderflow(row):
    start,end=row.get('window_start_ms'),row.get('window_end_ms')
    return (row.get('completeness')=='COMPLETE_CLOSED_WINDOW_V1'
        and type(start) is int and type(end) is int
        and start%900000==0 and end==start+899999)


def inspect_databases(trading, market, content):
    info={}
    for label,path in (('trading',trading),('market',market),('content',content)):
        with readonly(path) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            expected={'trading':{'runtime_rows','runtime_state','research_runs','decision_observations','execution_cycle_receipts','research_blobs'},
                'market':{'market_observations','market_series'},'content':{'news_articles','news_batches'}}[label]
            if not expected<=tables:raise ValueError('Missing '+label+' schema: '+str(expected-tables))
            result={'path':str(path),'bytes':path.stat().st_size,
                'wal_bytes':Path(str(path)+'-wal').stat().st_size if Path(str(path)+'-wal').exists() else 0}
            if label=='trading':
                result['families']=[{'system':s,'family':f,'rows':n} for s,f,n in db.execute(
                    'SELECT system,family,count(*) FROM runtime_rows GROUP BY system,family')]
                result['last_runs']={}
                for system in ('spot','futures'):
                    last=db.execute("SELECT payload_json FROM research_runs WHERE system=? AND kind='STARTED' ORDER BY id DESC LIMIT 1",(system,)).fetchone()
                    run=json.loads(last[0]) if last else {}
                    result['last_runs'][system]={k:run.get(k) for k in ('release_sha256','config_sha256',
                        'activation_close_ms','atomic_simulation','backfill','release_verified')}
                result['evidence_tables_retention']='Archive whole database; never delete append-only research evidence in place.'
            elif label=='market':
                result['coverage']=[dict(zip(('market','dataset','timeframe','rows','first_event_ms','last_event_ms'),r))
                    for r in db.execute('SELECT market_type,dataset,timeframe,count(*),min(event_time_ms),max(event_time_ms) '
                        'FROM market_observations GROUP BY market_type,dataset,timeframe')]
                result['latest_orderflow']={}
                for system in ('spot','futures'):
                    r=db.execute("SELECT event_time_ms,payload_json FROM market_observations WHERE market_type=? AND dataset='orderflow' AND timeframe='15m' ORDER BY event_time_ms DESC LIMIT 1",(system,)).fetchone()
                    v=json.loads(r[1]) if r else {}
                    result['latest_orderflow'][system]={'event_time_ms':r[0] if r else None,
                        'complete_aligned_window':assert_orderflow(v),
                        **{k:v.get(k) for k in ('source','completeness','window_start_ms','window_end_ms','period_count')}}
            else:
                result['news_articles']=db.execute('SELECT count(*) FROM news_articles').fetchone()[0]
                result['news_batches']=db.execute('SELECT count(*) FROM news_batches').fetchone()[0]
            info[label]=result
    return info


def run(output, *, deploy=DEPLOY, database_root=DATABASE_ROOT, check_service=True):
    output=output.resolve();database_root=database_root.resolve();deploy=deploy.resolve()
    runtime=DATABASE_ROOT.parent.resolve()
    if output.is_relative_to(runtime) or output.is_relative_to(database_root) or output.is_relative_to(deploy):
        raise ValueError('Plan must be separate from live runtime and deployment')
    activation=json.loads((deploy/'activation.json').read_text())
    expectations=json.loads((deploy/'expectations.json').read_text())
    archive=Path(activation['release'])/'source.json.gz'
    release_verified=hashlib.sha256(gzip.decompress(archive.read_bytes())).hexdigest()==activation['release_sha256']
    data=inspect_databases(*(database_root/p.name for p in (TRADING_DATABASE_PATH,MARKET_DATA_DATABASE_PATH,CONTENT_DATABASE_PATH)))
    service='not_checked'
    if check_service:
        service=subprocess.run(['systemctl','--user','is-active','smartsignalhub-runtime.service'],capture_output=True,text=True).stdout.strip()
    issues=[]
    if not release_verified:issues.append('PINNED_SOURCE_HASH_MISMATCH')
    for system in ('spot','futures'):
        run_info=data['trading']['last_runs'][system]
        expected=expectations.get('systems',{}).get(system,{})
        if not all(run_info.get(k) is True for k in ('release_verified','atomic_simulation','backfill')):
            issues.append(system+':RESEARCH_FLAGS_NOT_READY')
        for k in ('release_sha256','config_sha256','activation_close_ms'):
            if str(run_info.get(k))!=str(expected.get(k)) or run_info.get(k) is None:
                issues.append(system+':MONITOR_EXPECTATION_MISMATCH:'+k)
        if not data['market']['latest_orderflow'][system]['complete_aligned_window']:
            issues.append(system+':LATEST_ORDERFLOW_NOT_COMPLETE')
    plan={'format':'all-system-trading-epoch-preflight-v1','prepared_utc':datetime.now(timezone.utc).isoformat(),
        'scope':list(SYSTEMS),'operation_performed':'READ_ONLY_PREFLIGHT_ONLY','reset_executed':False,
        'ready_to_execute':False,'service_state':service,'pinned_source_verified':release_verified,
        'current_activation_close_ms':activation['activation_close_ms'],'existing_condition_findings':issues,
        'databases':data,'free_bytes':shutil.disk_usage(output.parent).free,
        'archive_before_reset':['Self-contained SQLite online backups of all three databases after writers stop; verify integrity and SHA-256.',
            'Current pinned source bundle, activation.json, expectations.json, monitor-command.json and any mutable runtime roots.'],
        'preserve_in_place':[str(database_root/MARKET_DATA_DATABASE_PATH.name),str(database_root/CONTENT_DATABASE_PATH.name)],
        'rotate_as_whole':str(database_root/TRADING_DATABASE_PATH.name),
        'pending_execution_gates':['Confirm owning user service and all manual runtime writers stopped; hold supervisor lock.',
            'Create and verify recoverable pre-reset archive; do not copy a changing SQLite main file alone.',
            'Choose first expected closed 15m candle at cutover, not preparation time or an invented historical start.',
            'Review coordinated activation.json and monitoring expectations change; keep the same approved strategy release.',
            'Use reviewed trading-only transition; existing unflagged reset also removes active market/content history.',
            'Restart owning service exactly once; verify three fresh accounts, complete inputs, first decisions, receipts and monitoring.',
            'Record first actual decision as strategy start; preserve any startup delay as evidence, not fabricated decisions.'],
        'continuity_limits':['No claim that existing market history has no gaps: coverage counts are not a continuity audit.',
            'Separate read transactions per DB, not a cross-database atomic snapshot.',
            'Historical complete flow does not guarantee future connectivity or absence of future missed decisions.',
            'New epoch is a prospective validation of the existing approved rules, not deployment of experimental candidates.']}
    output.mkdir(parents=True,exist_ok=False)
    for name in ('activation.json','expectations.json','monitor-command.json','start.py'):
        shutil.copyfile(deploy/name,output/name)
    shutil.copyfile(Path(__file__),output/'preflight_source.py')
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    lines=['# ახალი სავაჭრო ციკლის მომზადება — Spot / Futures / Hedge','',
        'ეს მხოლოდ შემოწმებაა: სერვისი არ გაჩერებულა, არცერთი ბაზა არ განულებულა.',
        '',f'სერვისი: {service}. გაყინული release-ის ჰეში: {release_verified}.',
        'არსებული პირობების შენიშვნები: '+json.dumps(issues), '',
        'ბაზრისა და ნიუსების ბაზები ადგილზე რჩება. სამივე სავაჭრო სისტემის ძველი მდგომარეობა და append-only მტკიცებულებები მთლიან trading ბაზასთან ერთად არქივდება.',
        'ერთი ახალი trading ბაზა სუფთა ანგარიშებსა და ახალი ციკლის მტკიცებულებებს მოემსახურება; ძველი ჩანაწერები არ გადაიწერება.',
        'უნდა შეიცვალოს საერთო activation epoch და მონიტორინგის მოლოდინები; სტრატეგიის საცდელი ფორმულები არ ინერგება.', '',
        '## გაშვებამდე დარჩენილი სავალდებულო ნაბიჯები','']
    lines += ['- '+step for step in plan['pending_execution_gates']]
    lines += ['', 'ძველი runtime_reset_system არგუმენტების გარეშე არ გამოიყენოთ: ის ბაზრისა და ნიუსების მოქმედ ისტორიასაც არქივში გადაიტანს.',
        'ეს ანგარიში არ არის არც ბექაფი და არც სისტემის საბოლოო მზადყოფნის დასტური. დეტალები: plan.json.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    (output/'manifest.json').write_text(json.dumps({'files':{p.name:digest(p) for p in output.iterdir() if p.is_file()}},indent=2)+'\n')
    print(json.dumps({'output':str(output),'service':service,'findings':issues,'reset_executed':False},indent=2))
    return plan


if __name__=='__main__':run(Path(sys.argv[1]))
