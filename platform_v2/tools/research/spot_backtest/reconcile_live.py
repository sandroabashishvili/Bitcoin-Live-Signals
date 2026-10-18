"""Read-only, frozen evidence comparison of operational Spot vs raw backtest.

This diagnoses existing decisions; it never runs a new strategy or writes live data.
Usage: python -m platform_v2.tools.research.spot_backtest.reconcile_live ROOT OUTPUT
"""
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import zlib

from .compare import load, digest


def millis(value):
    if isinstance(value,(int,float)) or str(value).isdigit():return int(value)
    d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
    return int(d.timestamp()*1000)


def position_stamp(position):
    value=position.get('signal_candle_close_time')
    if not value:return None
    return millis(value)//1000*1000+999


def closed_by(position,end):
    return position.get('status')=='CLOSED' and bool(position.get('closed_at')) and millis(position['closed_at'])<=end


def summary_positions(positions,start,end):
    cohort=[p for p in positions if start<=p['opened_at_ms']<=end]
    closed=[p for p in cohort if closed_by(p,end)]
    return {'opened':len(cohort),'closed_by_cutoff':len(closed),'open_at_cutoff':len(cohort)-len(closed),
        'closed_net_USDT':sum(p['net_pnl'] for p in closed)}


def differing_components(a,b):
    return [k for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)]


def run(root,out):
    root=root.resolve();out=out.resolve()
    runtime=Path('/home/sandro/SmartSignalHub/platform_v2/runtime').resolve()
    if out.is_relative_to(runtime) or out==root or out.is_relative_to(root/'runs'):
        raise ValueError('Output must not overlap live runtime or existing backtest runs')
    result,cycles=load(root,'baseline')
    base={row['timestamp_ms']:row for row in cycles}
    end_signal=max(base);end_account=end_signal+60000
    out.mkdir(parents=True,exist_ok=False);(out/'blobs').mkdir()
    protocol=json.loads((root/'protocol.json').read_text())
    raw=gzip.decompress((root/'source/source.json.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=protocol['source_sha256']:raise ValueError('Pinned source changed')
    if digest(root/'market.sqlite3')!=protocol['market_sha256']:raise ValueError('Frozen market changed')
    spec=importlib.util.spec_from_file_location('reconciliation_pinned_loader',root/'source/run.py')
    loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
    pinned=json.loads(raw);pinned['project_root']=str(out/'isolated_project')
    sys.meta_path.insert(0,loader.PinnedSource(pinned));sys.dont_write_bytecode=True
    from platform_v2.spot.services.signal.long_component_score_service import SpotLongComponentScoreService
    source=runtime/'database/smartsignalhub_trading.sqlite3'
    captured=datetime.now(timezone.utc).isoformat()
    captured_inputs=[];mismatches=[];evidence={};read_blobs={}
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db,sqlite3.connect((root/'market.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as market:
        db.execute('BEGIN')
        snapshot={family:[json.loads(row[0]) for row in db.execute(
            "SELECT payload_json FROM runtime_rows WHERE system='spot' AND family=? ORDER BY date_iso,ordinal",(family,))]
            for family in ('signals','positions','orders','denied_entries')}
        live={int(s['timestamp_ms']):s for s in snapshot['signals']}
        common=sorted(set(live)&set(base))
        if not common:raise ValueError('No common decision candles')
        start=common[0]
        positions={p['position_id']:p for p in snapshot['positions']}
        live_positions=list(positions.values())
        model_positions=[p for s in result['segments'] for p in s['positions']]
        targeted={t for t in common if live[t]['side']=='BUY' or base[t]['signal']['side']=='BUY'}
        for oid,run_id,attempt,cycle,text in db.execute("SELECT id,run_id,attempt_id,cycle_key,payload_json FROM decision_observations WHERE system='spot' AND kind='LIVE_OBSERVED' ORDER BY id"):
            obs=json.loads(text);record=obs['record'];stamp=int(record['timestamp_ms'])
            if stamp not in targeted:continue
            expected=live[stamp]
            if all(record.get(k)==expected.get(k) for k in ('side','score','component_scores','mtf_signals','snapshot_price','decision_time')):
                evidence[stamp]={'id':oid,'run_id':run_id,'attempt_id':attempt,'cycle_key':cycle,'observation':obs}
        runs={run_id:{k:p.get(k) for k in ('release_sha256','loaded_code_sha256','config_sha256','startup_capture_ms')}
            for run_id,text in db.execute("SELECT run_id,payload_json FROM research_runs WHERE system='spot' AND kind='STARTED'")
            for p in [json.loads(text)]}

        @lru_cache(maxsize=1024)
        def blob(ref):
            row=db.execute('SELECT compressed_json FROM research_blobs WHERE sha256=?',(ref,)).fetchone()
            if row is None:raise ValueError('Missing captured evidence blob: '+ref)
            data=zlib.decompress(row[0])
            if hashlib.sha256(data).hexdigest()!=ref:raise ValueError('Captured evidence hash mismatch')
            return json.loads(data)

        def preserve(ref):
            path=out/'blobs'/(ref+'.zlib')
            if not path.exists():
                row=db.execute('SELECT compressed_json FROM research_blobs WHERE sha256=?',(ref,)).fetchone()
                if row is None:raise ValueError('Missing captured blob')
                if hashlib.sha256(zlib.decompress(row[0])).hexdigest()!=ref:raise ValueError('Evidence hash mismatch')
                path.write_bytes(row[0])

        def book_score(row):
            values={k:row.get(k,0.) for k in ('buyers','sellers','dominance_ratio','imbalance')}
            return SpotLongComponentScoreService.long_orderbook_score(SimpleNamespace(**values))

        by_day={};components=Counter();confusion=Counter()
        for stamp in common:
            actual=live[stamp];model=base[stamp]['signal'];day=datetime.fromtimestamp(stamp/1000,timezone.utc).date().isoformat()
            diff=differing_components(actual.get('component_scores',{}),model.get('component_scores',{}))
            components.update(diff);confusion[(actual['side'],model['side'])]+=1
            stats=by_day.setdefault(day,Counter())
            stats['common_cycles']+=1;stats['side_mismatch']+=actual['side']!=model['side']
            for key in diff:stats[key+'_score_mismatch']+=1
            if actual['side']!=model['side']:
                mismatches.append({'timestamp_ms':stamp,'UTC':actual.get('candle_close_time'),
                    'live_side':actual['side'],'model_side':model['side'],'different_components':diff,
                    'live_score':actual['score'],'model_score':model['score'],
                    'live_components':actual['component_scores'],'model_components':model['component_scores']})
        for stamp,entry in sorted(evidence.items()):
            obs=entry['observation']
            if not obs.get('evidence_complete'):continue
            selected=None
            for ref in obs.get('input_refs',[]):
                manifest=blob(ref)
                if manifest.get('identity')==['binance','crypto','spot','orderflow','BTCUSDT','15m']:
                    selected=(ref,manifest)
            if selected is None or not selected[1].get('chunks'):continue
            ref,manifest=selected;chunk=manifest['chunks'][-1]
            rows=blob(chunk)
            if not rows:continue
            book=rows[-1]
            stored=market.execute('SELECT payload FROM flow WHERE close_ms=?',(stamp,)).fetchone()
            if stored is None:continue
            flow=json.loads(stored[0]);total=flow['buyers']+flow['sellers']
            dominance=round((flow['buyers']-flow['sellers'])/total,6) if total else 0.
            repaired={'buyers':round(flow['buyers'],8),'sellers':round(flow['sellers'],8),
                'dominance_ratio':dominance,'imbalance':dominance}
            actual=live[stamp];model=base[stamp]['signal']
            a_score=book_score(book);b_score=book_score(repaired)
            preserve(ref);preserve(chunk)
            captured_inputs.append({'timestamp_ms':stamp,'UTC':actual.get('candle_close_time'),
                'observation_id':entry['id'],'available_ms':obs['available_ms'],'code':runs.get(entry['run_id']),
                'manifest_ref':ref,'last_chunk_ref':chunk,'captured_orderflow':book,'recovered_orderflow':repaired,
                'current_formula_on_captured_input':a_score,'stored_live_orderbook_score':actual['component_scores']['orderbook'],
                'current_formula_on_recovered_input':b_score,'stored_model_orderbook_score':model['component_scores']['orderbook'],
                'both_scores_reproduced':a_score==actual['component_scores']['orderbook'] and b_score==model['component_scores']['orderbook'],
                'different_orderbook_score':actual['component_scores']['orderbook']!=model['component_scores']['orderbook']})
        live_by_stamp={position_stamp(p):p for p in live_positions if position_stamp(p) in common}
        model_by_stamp={position_stamp(p):p for p in model_positions if position_stamp(p) in common}
        trade_comparisons=[]
        for stamp in sorted(set(live_by_stamp)|set(model_by_stamp)):
            a=live_by_stamp.get(stamp);b=model_by_stamp.get(stamp)
            permission=base[stamp].get('permission')
            denial=[d.get('denial_reason') for d in snapshot['denied_entries'] if d.get('signal',{}).get('timestamp_ms')==stamp]
            trade_comparisons.append({'timestamp_ms':stamp,'UTC':live[stamp].get('candle_close_time'),
                'live_side':live[stamp]['side'],'model_side':base[stamp]['signal']['side'],
                'live_position':a,'model_position':b,'live_denial_reasons':denial,
                'model_permission':permission,
                'entry_difference_USDT':a['execution']['entry_price']-b['execution']['entry_price'] if a and b else None,
                'live_closed_by_cutoff':closed_by(a,end_account) if a else None,
                'model_closed_by_cutoff':closed_by(b,end_account) if b else None})
    # Persist a single read-transaction capture; operational DB can keep running.
    (out/'live_snapshot.json').write_text(json.dumps({'captured_utc':captured,'source':str(source),'families':snapshot},allow_nan=False)+'\n')
    info={'captured_utc':captured,'source_market_sha256':protocol['market_sha256'],
        'pinned_source_sha256':protocol['source_sha256'],'common_first_signal_ms':start,'common_last_signal_ms':common[-1],
        'last_exit_scan_ms':end_account,'common_cycles':len(common),
        'model_cycles_in_live_range':sum(start<=t<=end_signal for t in base),
        'live_cycles_in_model_range':sum(min(base)<=t<=end_signal for t in live),
        'side_matrix':{a+' -> '+b:n for (a,b),n in confusion.items()},'component_mismatch_counts':dict(components),
        'live_entry_cohort':summary_positions(live_positions,start,end_account),
        'model_entry_cohort_NOT_fresh_Sep13_account':summary_positions(model_positions,start,end_account),
        'same_signal_entry_matches':len(set(live_by_stamp)&set(model_by_stamp)),
        'live_only_entries':len(set(live_by_stamp)-set(model_by_stamp)),
        'model_only_entries':len(set(model_by_stamp)-set(live_by_stamp)),
        'captured_input_cases':len(captured_inputs),
        'both_orderbook_scores_reproduced':sum(r['both_scores_reproduced'] for r in captured_inputs),
        'by_day':{day:dict(stats) for day,stats in by_day.items()},
        'limits':['Diagnostic only; no rules, data collectors, live trades or execution settings changed.',
            'Common decision candles, not claimed identical starting portfolio: model account starts Aug1, operational Spot Sep13.',
            'Operational position closures after the cutoff are not counted as closed at the cutoff; historical mark-to-market not inferred.',
            'Persisted final live signal records are compared, not silently replaced with arbitrary first-attempt observations.',
            'Original input evidence is selected only when its stored decision matches the persisted signal; absent or earlier evidence is unknown.',
            'Captured evidence copies include selected manifests and final relevant chunks, not every historical chunk in each manifest.',
            'Per-position paired net differences are observational and do not isolate causal execution/slippage effects.']}
    for name,data in (('summary.json',info),('signal_mismatches.json',mismatches),
        ('captured_inputs.json',captured_inputs),('trade_comparisons.json',trade_comparisons)):
        (out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    lines=['# Operational Spot vs raw historical baseline: reconciliation', '',
        'Captured UTC: '+captured, '', f'Common candles: {len(common)}. Component differences: {dict(components)}.', '',
        '## Signal side matrix (live -> model)', '']
    lines+=['- '+k+': '+str(v) for k,v in info['side_matrix'].items()]
    lines+=['', '## Daily differences', '', '| UTC day | Common | Different side | ORDERBOOK | MTF |', '|---|---:|---:|---:|---:|']
    for day,stats in info['by_day'].items():
        lines.append(f"| {day} | {stats['common_cycles']} | {stats['side_mismatch']} | {stats.get('orderbook_score_mismatch',0)} | {stats.get('mtf_score_mismatch',0)} |")
    lines+=['', '## Cutoff-aligned entry cohorts', '',
        'Live: '+json.dumps(info['live_entry_cohort']),
        'Model (existing Aug1-start account, NOT a fresh Sep13-start replay): '+json.dumps(info['model_entry_cohort_NOT_fresh_Sep13_account']), '',
        f"Same-signal entries: {info['same_signal_entry_matches']}; live-only: {info['live_only_entries']}; model-only: {info['model_only_entries']}.",
        f"Original input cases: {len(captured_inputs)}; both live and model ORDERBOOK scores reproduced with the pinned formula: {info['both_orderbook_scores_reproduced']}.", '', '## Limits', '']
    lines+=['- '+limit for limit in info['limits']]
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    (out/'manifest.json').write_text(json.dumps({'analysis_source_sha256':digest(Path(__file__)),
        'baseline_manifest_sha256':digest(root/'runs/baseline/manifest.json'),
        'files':{str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file()}},indent=2)+'\n')
    print(json.dumps({k:v for k,v in info.items() if k not in ('by_day','limits')},indent=2))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
