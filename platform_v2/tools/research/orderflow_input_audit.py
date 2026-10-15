"""Audit immutable first-attempt Spot orderflow inputs, not live market calls."""
import argparse
import functools
import hashlib
import json
import math
import sqlite3
import statistics
import zlib
from collections import Counter
from pathlib import Path
from platform_v2.tools.research import signal_lab as lab


def aggregate(trades):
    buyers=sellers=0.0
    times=[]
    for trade in trades:
        quantity=float(trade['q']);stamp=int(trade['T'])
        if not math.isfinite(quantity) or quantity<0:raise ValueError('Invalid captured quantity')
        if bool(trade.get('m')):sellers+=quantity
        else:buyers+=quantity
        times.append(stamp)
    total=buyers+sellers
    dominance=(buyers-sellers)/total if total>0 else 0.0
    return {'buyers':round(buyers,8),'sellers':round(sellers,8),
        'dominance_ratio':round(dominance,6),'imbalance':round(dominance,6),
        'period_count':len(trades),'first_trade_ms':min(times) if times else None,
        'last_trade_ms':max(times) if times else None}


def snapshot_matches(row,summary):
    return all(float(row.get(key,0) or 0)==summary[key] for key in
        ('buyers','sellers','dominance_ratio','imbalance','period_count'))


def response_pairs(events,cutoff):
    """Ledger responses refer to request event_key strings, NOT numeric row ids."""
    requests={}
    for event_id,event_key,kind,event_stamp,payload_text in events:
        if event_stamp>cutoff:continue
        payload=json.loads(payload_text)
        if kind=='REQUESTED':requests[event_key]=payload
        elif kind=='RESPONSE':
            request=requests.get(payload.get('request_id'))
            if request and request.get('endpoint','').endswith('/aggTrades'):
                yield event_id,request,payload


def run(workspace):
    root=lab.outside_live(workspace);lab.verify(root)
    protocol=json.loads((root/'protocol.json').read_text())
    records=[]
    with sqlite3.connect((root/'data/trading.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        @functools.lru_cache(maxsize=512)
        def blob(ref):
            stored=db.execute('SELECT compressed_json FROM research_blobs WHERE sha256=?',(ref,)).fetchone()
            if stored is None:raise ValueError('Missing evidence blob')
            raw=zlib.decompress(stored[0])
            if hashlib.sha256(raw).hexdigest()!=ref:raise ValueError('Evidence hash mismatch')
            return json.loads(raw)
        for oid,run_id,attempt,cycle,text in db.execute("SELECT id,run_id,attempt_id,cycle_key,payload_json FROM research_first_live_decisions WHERE system='spot' ORDER BY id"):
            first=json.loads(text);stamp=first['record']['timestamp_ms']
            if not protocol['start_ms']<=stamp<protocol['end_ms']:continue
            chain=[json.loads(r[0]) for r in db.execute("SELECT payload_json FROM decision_observations WHERE system='spot' AND run_id=? AND attempt_id IS ? AND cycle_key=? AND kind='LIVE_OBSERVED' AND id>=? ORDER BY id",(run_id,attempt,cycle,oid))]
            if not chain or any(not p.get('evidence_complete') for p in chain):raise ValueError('Incomplete first-attempt evidence')
            last=chain[-1];manifest=None
            for ref in last['input_refs']:
                m=blob(ref)
                if m['identity']==['binance','crypto','spot','orderflow','BTCUSDT','15m']:manifest=m
            if manifest is None or not manifest['chunks']:raise ValueError('Missing orderflow revision')
            row=blob(manifest['chunks'][-1])[-1]
            matches=[]
            events=db.execute("SELECT id,event_key,kind,at_ms,payload_json FROM market_acquisition_events WHERE system='spot' AND run_id=? AND attempt_id IS ? AND cycle_key=? ORDER BY id",(run_id,attempt,cycle))
            for event_id,requested,p in response_pairs(events,last['available_ms']):
                trades=blob(p['content_ref'])
                if not isinstance(trades,list):raise ValueError('Unexpected aggTrades response')
                summary=aggregate(trades)
                if snapshot_matches(row,summary):matches.append((event_id,requested,p,summary))
            result={'observation_id':oid,'timestamp_ms':stamp,'snapshot_timestamp_text':row.get('timestamp_text'),
                'source':row.get('source'),'period_count':row.get('period_count'),
                'dominance_equals_imbalance':float(row.get('dominance_ratio',0))==float(row.get('imbalance',0)),
                'matched_original_responses':len(matches)}
            if matches:
                # Identical volume rows alone are insufficient to select ambiguous trade times.
                identities={(r[2]['content_ref'],r[3]['first_trade_ms'],r[3]['last_trade_ms']) for r in matches}
                if len(identities)!=1:raise ValueError('Ambiguous captured orderflow response')
                event_id,request,response,summary=matches[-1]
                params=request['params'];start=int(params['startTime'][0]);end=int(params['endTime'][0]);limit=int(params['limit'][0])
                latest=summary['last_trade_ms'];earliest=summary['first_trade_ms']
                result.update({'response_event_id':event_id,'content_ref':response['content_ref'],
                    'request_start_ms':start,'request_end_ms':end,'requested_hours':(end-start)/3600000,
                    'limit':limit,'response_count':summary['period_count'],
                    'limit_reached':summary['period_count']>=limit,'completeness':response['completeness'],
                    'first_trade_ms':earliest,'last_trade_ms':latest,
                    'last_trade_age_hours_at_decision':None if latest is None else (stamp-latest)/3600000,
                    'sample_span_minutes':None if earliest is None else (latest-earliest)/60000,
                    'trades_in_latest_closed_15m':None if earliest is None else sum(stamp-899999<=t['T']<=stamp for t in blob(response['content_ref']))})
                if earliest is not None and not (start<=earliest<=latest<=end):raise ValueError('Trade timestamps outside requested range')
            records.append(result)
            if len(records)%300==0:print('Audited first-attempt orderflow',len(records),flush=True)
    if not records:raise ValueError('No input cohort')
    verified=[r for r in records if r['matched_original_responses']]
    ages=[r['last_trade_age_hours_at_decision'] for r in verified if r['last_trade_age_hours_at_decision'] is not None]
    summary={'cycles':len(records),'matched_original_responses':len(verified),
        'unmatched_reused_or_unknown':len(records)-len(verified),
        'dominance_equals_imbalance':sum(r['dominance_equals_imbalance'] for r in records),
        'request_hours':dict(Counter(str(r['requested_hours']) for r in verified)),
        'count_at_limit':sum(r['limit_reached'] for r in verified),
        'older_than_15m':sum(a>.25 for a in ages),'older_than_23h':sum(a>23 for a in ages),
        'age_hours_min_median_max':[min(ages),statistics.median(ages),max(ages)] if ages else None,
        'sample_minutes_min_median_max':[min(r['sample_span_minutes'] for r in verified if r['sample_span_minutes'] is not None),statistics.median(r['sample_span_minutes'] for r in verified if r['sample_span_minutes'] is not None),max(r['sample_span_minutes'] for r in verified if r['sample_span_minutes'] is not None)] if ages else None,
        'responses_with_any_trade_in_latest_closed_15m':sum(bool(r['trades_in_latest_closed_15m']) for r in verified)}
    output=root/'orderflow_input_audit';output.mkdir(exist_ok=False)
    lab.write(output/'results.json',{'summary':summary,'cycles':records,'runtime_changed':False,
        'limitations':['Only first original attempts and matching captured input revisions; no retries substituted.',
            'Unmatched rows are explicitly unknown/reused, not asserted fresh or stale.',
            'This diagnoses input quality, not counterfactual signal/trade profitability.',
            'Future fetched data cannot repair historical decision availability silently.']})
    lines=['# Spot ORDERBOOK input audit','',
        'Immutable original attempts only; exact raw responses are hash verified and matched to consumed volumes.',
        'No network calls, live DB reads, source edits or trade simulation.','',
        '```json',json.dumps(summary,indent=2),'```','',
        'The source calls this ORDERBOOK, but it uses executed aggTrades quantities, not book-depth orders.',
        'Dominance and imbalance are computed identically. The volume ratio is derived from the same two quantities.',
        'Repeated transforms may be intentional score shaping, but are not independent confirmation evidence.',
        'Window completeness/freshness must be repaired before scoring changes can be trusted for promotion.',
        'Existing replay statistics remain valid reproductions of the old pipeline; they retain its input-quality limitation.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    lab.write(output/'manifest.json',{'protocol_sha256':lab.digest(root/'protocol.json'),
        'files':{name:lab.digest(output/name) for name in ('REPORT.md','results.json')},
        'audit_source_sha256':lab.digest(Path(__file__)),'runtime_changed':False})
    return output/'REPORT.md'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path)
    print(run(p.parse_args().workspace))
