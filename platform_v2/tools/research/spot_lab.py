"""Full, isolated Spot replay driver. No live changes or automatic promotion."""
import argparse
import gzip
import json
import math
import shutil
import sqlite3
import statistics
import sys
from pathlib import Path
from platform_v2.tools.research import signal_lab as lab
from platform_v2.tools.research.mtf_symmetry_experiment import candidate_source

MTF = 'platform_v2/spot/services/signal/mtf_context_service.py'


def prepare(workspace):
    root = lab.outside_live(workspace)
    lab.verify(root)
    payload = json.loads(gzip.decompress((root / 'source/source.json.gz').read_bytes()))
    for name in ('unchanged', 'symmetric_all'):
        folder = root / 'spot_candidates' / name
        folder.mkdir(parents=True, exist_ok=False)
        code = payload['files'][MTF]
        if name == 'symmetric_all':
            code = candidate_source(code, ['5m', '15m', '4h']).replace('return "LONG"', 'return "BUY"').replace('return "SHORT"', 'return "SELL"')
        (folder / 'mtf.py').write_text(code)
        lab.write(folder / 'protocol.json', {'component': 'mtf', 'source_sha256': lab.digest(folder / 'mtf.py'),
          'variant': name, 'source_market': 'spot', 'rules': '5m RSI/VWAP agreement plus shared ADX>20; 15m RSI/slope agreement; 4h two of RSI/Tenkan-Kijun/EMA50-200'})
    return root / 'spot_candidates'


def run(workspace, name='baseline', model='observed', limit=0):
    root = lab.outside_live(workspace)
    if model not in ('observed','next-minute') or name not in ('baseline','unchanged','symmetric_all') or limit < 0:
        raise ValueError('Unsupported Spot experiment')
    lab.verify(root)
    if model == 'next-minute':
        observed = root / 'spot_runs/baseline-observed'
        lab._verify_run(root, observed)
        r = json.loads((observed / 'portfolio.json').read_text())
        if not r['historical_parity_ok'] or r['limit'] != limit:
            raise ValueError('Matching historical Spot baseline required')
    if name != 'baseline':
        if model != 'next-minute':
            raise ValueError('Spot candidates require uniform modeled execution')
        baseline = root / 'spot_runs/baseline-next-minute'
        lab._verify_run(root, baseline)
        r = json.loads((baseline / 'portfolio.json').read_text())
        if not r['signal_parity_ok'] or r['limit'] != limit:
            raise ValueError('Matching modeled baseline required')
    run_id = 'baseline-' + model if name == 'baseline' else name
    output = root / 'spot_runs' / run_id
    output.mkdir(parents=True, exist_ok=False)
    for module, destination in [('spot_lab_worker.py','worker.py'),('spot_lab_support.py','spot_lab_support.py')]:
        shutil.copyfile(Path(__file__).with_name(module), output / destination)
    if name != 'baseline':
        shutil.copyfile(root / 'spot_candidates' / name / 'mtf.py', output / 'mtf.py')
    lab.write(output / 'execution_protocol.json', {'model':model,'limit':limit,'market':'spot',
        'first_attempt': 'First LIVE_OBSERVED attempt; latest enrichment in that same attempt only',
        'initial_positions': 'First captured pre-batch position documents, loaded once',
        'candidate':name,'live_changes':False})
    code = lab.launch_recorded([sys.executable,'-B',str(output/'worker.py'),str(root),name,model,str(limit),run_id],output)
    lab.verify(root)
    lab.write(output / 'manifest.json', {'protocol_sha256':lab.digest(root/'protocol.json'),
         'files':{p.name:lab.digest(p) for p in output.iterdir() if p.is_file()}})
    if code:
        raise RuntimeError('Spot replay failed verification; inspect '+str(output))
    return output


def compare(workspace):
    root=lab.outside_live(workspace);lab.verify(root)
    results={}
    for name in ('baseline-next-minute','unchanged','symmetric_all'):
        folder=root/'spot_runs'/name;lab._verify_run(root,folder)
        results[name]=json.loads((folder/'portfolio.json').read_text())
    base=results['baseline-next-minute']
    if not base['signal_parity_ok']:raise ValueError('Unverified modeled baseline')
    protocol=json.loads((root/'protocol.json').read_text())
    with sqlite3.connect((root/'data/market.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        prices={}
        for stamp,text in db.execute("SELECT event_time_ms,payload_json FROM market_observations WHERE venue='binance' AND market_type='spot' AND dataset='candles' AND symbol='BTCUSDT' AND timeframe='1m' AND event_time_ms+60000<=?",(protocol['end_ms'],)):
            candle=json.loads(text);value=float(candle['open'])
            if stamp in prices or candle['timestamp']!=stamp or candle['close_time']!=stamp+59999 or not math.isfinite(value) or value<=0:
                raise ValueError('Invalid signal-quality price input')
            prices[stamp]=value
    summaries={}
    for name,data in results.items():
        if data['initial_positions']!=base['initial_positions'] or [r['observation_id'] for r in data['cycles']]!=[r['observation_id'] for r in base['cycles']]:
            raise ValueError('Different Spot account/cohort')
        comparable=lambda row:{k:row[k] for k in ('timestamp_ms','signal','permission','account_after','positions')}
        if name=='unchanged' and [comparable(r) for r in data['cycles']]!=[comparable(r) for r in base['cycles']]:
            raise ValueError('Unchanged Spot control differs')
        initial_ids={r['position_id'] for r in data['initial_positions']}
        new=[r for r in data['final_positions'] if r['position_id'] not in initial_ids]
        freshness=1791655199999  # Exact end of the previously used Futures research period.
        by_period={}
        for label in ('previously_used_calendar','later_calendar'):
            rows=[r for r in data['cycles'] if (r['timestamp_ms']<freshness)==(label=='previously_used_calendar')]
            by_period[label]={'cycles':len(rows),'recognized_net':round(sum(r['account_after']['closed_net_pnl']-r['account_before']['closed_net_pnl'] for r in rows),2),
                              'BUY':sum(r['signal']['side']=='BUY' for r in rows)}
        peak=max(base['cycles'][0]['account_before']['equity'],base['cycles'][0]['account_after']['equity']);dd=0
        for row in data['cycles']:
            value=row['account_after']['equity'];peak=max(peak,value);dd=max(dd,100*(peak-value)/peak)
        summaries[name]={'actions':data['actions'],'evaluated_directions':data['evaluated_directions'],
           'new_positions':len(new),'closed_new_positions':sum(r['status']=='CLOSED' for r in new),
           'period_net_pnl':data['period_net_pnl'],'final_account':data['final_account'],
           'equity_difference_vs_baseline':round(data['final_account']['equity']-base['final_account']['equity'],2),
           'cycle_drawdown_pct':round(dd,4),'calendar_splits':by_period,
           'changed_BUY_decisions':sum(a['signal']['side']!=b['signal']['side'] for a,b in zip(data['cycles'],base['cycles'])),
           'changed_permissions':sum(a['permission']!=b['permission'] for a,b in zip(data['cycles'],base['cycles'])),
           'missing_quotes':len(data['missing_modeled_quotes']),'portfolio_sha256':lab.digest(root/'spot_runs'/name/'portfolio.json')}
        forwards={}
        for horizon in (15,60,240):
            values=[];missing=0
            for row in data['cycles']:
                start,end=row['clock_ms'],row['clock_ms']+horizon*60000
                if start not in prices or end not in prices:
                    missing+=1;continue
                if row['signal']['side']=='BUY':values.append((prices[end]/prices[start]-1)*100)
            forwards[str(horizon)]={'BUY_n':len(values),'mean_pct':statistics.mean(values) if values else None,
                'median_pct':statistics.median(values) if values else None,
                'positive_pct':100*sum(v>0 for v in values)/len(values) if values else None,
                'missing_label_cycles':missing}
        summaries[name]['BUY_forward_price_returns']=forwards
    output=root/'spot_comparison';output.mkdir(exist_ok=True)
    lab.write(output/'results.json',{'results':summaries,'limitations':base['limitations']+[
       'Earlier calendar overlaps the Futures candidate-selection period',
       'Later calendar is only about two days; not sufficient independent validation',
       'Chronological splits retain evolving positions, not independently reset accounts']})
    lines=['# Spot full replay: MTF symmetry comparison','',
           '| Variant | BUY signals | New opens | Period net USDT | Final equity USDT | Equity difference | Cycle DD % |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for name,r in summaries.items():
        lines.append(f"| {name} | {r['actions'].get('BUY',0)} | {r['new_positions']} | {r['period_net_pnl']:.2f} | {r['final_account']['equity']:.2f} | {r['equity_difference_vs_baseline']:+.2f} | {r['cycle_drawdown_pct']:.4f} |")
    lines += ['','Split boundaries use the exact end of Futures research (2026-10-10 17:59:59.999 UTC).',
              'The later approximately two-day segment is descriptive, not sufficient independent validation.',
              'The unchanged control must reproduce all semantic cycle paths; random paper order UUIDs are excluded.',
              'No automatic promotion or live changes. Full per-cycle, permission and private SQLite evidence is retained.']
    lines += ['','## BUY signal quality (forward open-price returns, not position win rate)','',
              '| Variant | Horizon min | BUY n | Mean % | Median % | Positive % |',
              '|---|---:|---:|---:|---:|---:|']
    for name,r in summaries.items():
        for horizon,v in r['BUY_forward_price_returns'].items():
            lines.append(f"| {name} | {horizon} | {v['BUY_n']} | {v['mean_pct']:.4f} | {v['median_pct']:.4f} | {v['positive_pct']:.2f} |")
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    return output/'REPORT.md'


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','run','compare'])
    p.add_argument('workspace',type=Path)
    p.add_argument('--name',default='baseline')
    p.add_argument('--model',choices=['observed','next-minute'],default='observed')
    p.add_argument('--limit',type=int,default=0)
    a=p.parse_args()
    print(prepare(a.workspace) if a.command=='prepare' else compare(a.workspace) if a.command=='compare' else run(a.workspace,a.name,a.model,a.limit))
