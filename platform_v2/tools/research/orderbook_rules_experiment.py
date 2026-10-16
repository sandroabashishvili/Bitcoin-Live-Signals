"""Predeclared Spot ORDERBOOK ablations on captured complete closed-window input."""
import ast
import gzip
import json
import sqlite3
import zlib
import hashlib
from functools import lru_cache
from pathlib import Path
from platform_v2.tools.research import signal_lab as lab
from platform_v2.tools.research.orderflow_input_audit import aggregate, snapshot_matches, response_pairs

COMPONENT='platform_v2/spot/services/signal/long_component_score_service.py'
MTF='platform_v2/spot/services/signal/mtf_context_service.py'
RULES={
    'no_imbalance': 'Remove only the imbalance bonus/penalty; retain ratio and dominance bands. Diagnostic redundancy ablation, not independent indicators.',
    'monotonic': 'Use one directional dominance measure: <=0:0; (0,.1):.75; [.1,.25):1.5; [.25,.5):2.25; [.5,1]:2.5. Mirror LONG/opposing sides; do not raise the attainable peak.',
    'disabled': 'Zero only ORDERBOOK contribution on both sides; diagnostic control, not a deletion recommendation.',
}


def candidate_source(source, variant):
    if variant not in RULES:raise ValueError('Unsupported ORDERBOOK variant')
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SpotLongComponentScoreService')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='directional_orderbook_score')
    checks=[n for n in method.body if isinstance(n,ast.If)]
    if len(checks)!=4 or 'ORDERBOOK_DIRECTIONAL_IMBALANCE_CONFIRM_MIN' not in ast.unparse(checks[-1].test):
        raise ValueError('Unexpected ORDERBOOK structure')
    if variant=='no_imbalance':method.body.remove(checks[-1])
    elif variant=='disabled':method.body=ast.parse('return 0.0').body
    else:
        method.body=ast.parse('''
if directional_volume <= 0 or opposite_volume <= 0:
    return 0.0
if directional_dominance <= 0:
    return 0.0
if directional_dominance < 0.1:
    return 0.75
if directional_dominance < 0.25:
    return 1.5
if directional_dominance < 0.5:
    return 2.25
return 2.5
''').body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n'


def audit_complete_inputs(root):
    protocol=json.loads((root/'protocol.json').read_text());records=[]
    with sqlite3.connect((root/'data/trading.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        @lru_cache(maxsize=64)
        def blob(ref):
            raw=zlib.decompress(db.execute('SELECT compressed_json FROM research_blobs WHERE sha256=?',(ref,)).fetchone()[0])
            if hashlib.sha256(raw).hexdigest()!=ref:raise ValueError('Captured blob hash mismatch')
            return json.loads(raw)
        for oid,run,attempt,cycle,text in db.execute("SELECT id,run_id,attempt_id,cycle_key,payload_json FROM research_first_live_decisions WHERE system='spot' ORDER BY id"):
            stamp=json.loads(text)['record']['timestamp_ms']
            if not protocol['start_ms']<=stamp<protocol['end_ms']:continue
            chain=[json.loads(r[0]) for r in db.execute("SELECT payload_json FROM decision_observations WHERE system='spot' AND run_id=? AND attempt_id IS ? AND cycle_key=? AND kind='LIVE_OBSERVED' AND id>=? ORDER BY id",(run,attempt,cycle,oid))]
            if not chain or any(not p.get('evidence_complete') for p in chain):raise ValueError('Incomplete observation chain')
            last=chain[-1];row=None
            for ref in last['input_refs']:
                m=blob(ref)
                if m['identity']==['binance','crypto','spot','orderflow','BTCUSDT','15m']:row=blob(m['chunks'][-1])[-1]
            if not row or row.get('completeness')!='COMPLETE_CLOSED_WINDOW_V1':raise ValueError('Unverified orderflow input')
            if row['window_end_ms']!=stamp or row['window_start_ms']!=stamp-899999:raise ValueError('Wrong decision candle')
            events=db.execute("SELECT id,event_key,kind,at_ms,payload_json FROM market_acquisition_events WHERE system='spot' AND run_id=? AND attempt_id IS ? AND cycle_key=? ORDER BY id",(run,attempt,cycle))
            pages=list(response_pairs(events,last['available_ms']));trades={}
            if len(pages)!=row['page_count']:raise ValueError('Wrong raw page count')
            for i,(_,request,response) in enumerate(pages):
                params=request['params']
                if i==0 and (int(params['startTime'][0])!=row['window_start_ms'] or int(params['endTime'][0])!=stamp):raise ValueError('Wrong first request bounds')
                if i and ('fromId' not in params or 'startTime' in params or 'endTime' in params):raise ValueError('Wrong continuation cursor')
                for trade in blob(response['content_ref']):
                    if row['window_start_ms']<=trade['T']<=stamp:
                        if trade['a'] in trades and trades[trade['a']]!=trade:raise ValueError('Conflicting duplicate')
                        trades[trade['a']]=trade
            summary=aggregate(sorted(trades.values(),key=lambda t:t['a']))
            if not snapshot_matches(row,summary) or any(row[k]!=summary[k] for k in ('first_trade_ms','last_trade_ms')):raise ValueError('Raw trades differ from consumed input')
            records.append({'observation_id':oid,'timestamp_ms':stamp,'trades':len(trades),'pages':len(pages),
                'dominance':row['dominance_ratio'],'imbalance':row['imbalance'],'raw_match':True})
    if not records:raise ValueError('No verified corrected cohort')
    result={'cycles':len(records),'all_raw_pages_verified':True,'first_close_ms':records[0]['timestamp_ms'],
        'last_close_ms':records[-1]['timestamp_ms'],'dominance_equals_imbalance':sum(r['dominance']==r['imbalance'] for r in records),
        'records':records,'live_writes':False}
    lab.write(root/'orderbook_input_validation.json',result)
    return result


def prepare(workspace):
    root=lab.outside_live(workspace);lab.verify(root)
    audit_complete_inputs(root)
    payload=json.loads(gzip.decompress((root/'source/source.json.gz').read_bytes()))
    for variant,rule in RULES.items():
        code=candidate_source(payload['files'][COMPONENT],variant)
        for use_mtf in (False,True):
            name=('mtf_' if use_mtf else '')+f'orderbook_{variant}_v1'
            folder=root/'spot_candidates'/name;folder.mkdir(parents=True,exist_ok=False)
            (folder/'component.py').write_text(code)
            overlays={COMPONENT:{'file':'component.py','sha256':lab.digest(folder/'component.py')}}
            if use_mtf:
                mtf=root/'spot_candidates/symmetric_all/mtf.py'
                declaration=json.loads((mtf.parent/'protocol.json').read_text())
                if lab.digest(mtf)!=declaration['source_sha256']:raise ValueError('MTF hash mismatch')
                (folder/'mtf.py').write_bytes(mtf.read_bytes())
                overlays[MTF]={'file':'mtf.py','sha256':lab.digest(folder/'mtf.py')}
            lab.write(folder/'protocol.json',{'variant':name,'overlays':overlays,
                'components':['orderbook']+(['mtf'] if use_mtf else []),'rules':rule,
                'reference':'symmetric_all' if use_mtf else 'baseline-next-minute',
                'selection':'Three variants fixed before replay; short exploratory corrected-input period, not independent validation.',
                'unchanged':'Other five component formulas (apart from explicitly declared MTF context), weights, gates, thresholds, permissions, fees, sizing and native exits.',
                'source_market':'spot','live_changes':False,
                'pinned_archive_sha256':lab.digest(root/'source/source.json.gz')})
    return root/'spot_candidates'


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path)
    print(prepare(p.parse_args().workspace))
