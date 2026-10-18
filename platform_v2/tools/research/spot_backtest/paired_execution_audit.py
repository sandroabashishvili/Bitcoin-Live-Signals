"""Explain frozen matched-account entries/permissions/exits, not causal PnL attribution."""
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
from .compare import digest, load
from .reconcile_live import position_stamp, closed_by


def run(root, evidence=None):
    root = root.resolve()
    seal = json.loads((root/'manifest.json').read_text())
    for name, expected in seal['files'].items():
        if digest(root/name) != expected:raise ValueError('Paired evidence changed: '+name)
    arms = {name:load(root,name) for name in ('baseline','unchanged')}
    indexed = {name:{r['timestamp_ms']:r for r in rows} for name,(_,rows) in arms.items()}
    positions = {name:{position_stamp(p):p for s in result['segments'] for p in s['positions']}
        for name,(result,_) in arms.items()}
    if any(None in p for p in positions.values()):raise ValueError('Position missing signal identity')
    a,b = (positions[n] for n in arms)
    pairs=[]
    for stamp in sorted(set(a)|set(b)):
        raw, recorded = a.get(stamp),b.get(stamp)
        pairs.append({'timestamp_ms':stamp,'recomputed_position':raw,'recorded_position':recorded,
            'recomputed_signal':indexed['baseline'][stamp]['signal'],
            'recorded_signal':indexed['unchanged'][stamp]['signal'],
            'recomputed_permission':indexed['baseline'][stamp]['permission'],
            'recorded_permission':indexed['unchanged'][stamp]['permission'],
            'entry_price_difference':raw['execution']['entry_price']-recorded['execution']['entry_price'] if raw and recorded else None})
    stats={}
    for name,(result,rows) in arms.items():
        failed=Counter();reasons=Counter()
        for row in rows:
            p=row['permission']
            if row['signal'] and row['signal']['side']=='BUY' and p and p['status']!='ALLOWED':
                failed.update(k for k,v in p['checks'].items() if not v)
                reasons.update([p['reason']])
        stats[name]={'failed_checks':dict(failed),'denial_reasons':dict(reasons),
            'exit_reasons':result['segments'][0]['exit_reasons']}
    summary={'same_signal_entries':len(set(a)&set(b)),
        'recomputed_only_entries':len(set(a)-set(b)),'recorded_only_entries':len(set(b)-set(a)),
        'shared_entries_with_different_price':sum(p['entry_price_difference']!=0 for p in pairs if p['entry_price_difference'] is not None),
        'accounts':stats,'limits':'Descriptive comparison of exogenous decisions; not causal PnL attribution or original operational execution.'}
    operational_pairs=[]
    if evidence is not None:
        from .paired_accounts import read_verified
        protocol=json.loads((root/'paired_account_protocol.json').read_text())
        if digest(evidence/'manifest.json')!=protocol['evidence_manifest_sha256']:
            raise ValueError('Different operational reference snapshot')
        snapshot=read_verified(evidence,'live_snapshot.json',json.loads((evidence/'manifest.json').read_text()))
        unique={p['position_id']:p for p in snapshot['families']['positions']}
        live={position_stamp(p):p for p in unique.values() if protocol['start_ms']<=p['opened_at_ms']<=protocol['end_ms']+60000}
        for stamp in sorted(set(live)|set(b)):
            if stamp is None:raise ValueError('Operational position lacks candle identity')
            operational_pairs.append({'timestamp_ms':stamp,'operational_position':live.get(stamp),
                'recorded_model_position':b.get(stamp)})
        summary['operational_vs_recorded_model']={
            'same_signal_entries':len(set(live)&set(b)), 'operational_only':len(set(live)-set(b)),
            'recorded_model_only':len(set(b)-set(live)),
            'operational_closed_net_USDT':sum(p['net_pnl'] for p in live.values() if closed_by(p,protocol['end_ms']+60000)),
            'recorded_model_closed_net_USDT':arms['unchanged'][0]['closed_net_USDT'],
            'warning':'Same entry count alone does not establish identical entries or isolate execution effects.'}
    out=root/'execution_comparison';out.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__),out/'analysis_source.py')
    for name,value in (('position_pairs.json',pairs),('summary.json',summary)):
        (out/name).write_text(json.dumps(value,indent=2)+'\n')
    if evidence is not None:
        (out/'operational_position_pairs.json').write_text(json.dumps(operational_pairs,indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps({'parent_manifest_sha256':digest(root/'manifest.json'),
        'files':{p.name:digest(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]) if len(sys.argv)>2 else None)
