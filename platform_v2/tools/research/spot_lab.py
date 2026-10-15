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
from platform_v2.tools.research.spot_permission_audit import summarize as summarize_forward_returns

MTF = 'platform_v2/spot/services/signal/mtf_context_service.py'
COMPONENT = 'platform_v2/spot/services/signal/long_component_score_service.py'
PERMISSION = 'platform_v2/spot/services/permission/permission_decision_service.py'
NAMES = ('baseline','unchanged','symmetric_all','trend_mirror_v1','mtf_trend_mirror_v1','proximity_off_v1','mtf_proximity_off_v1')
NAMES += ('trend_alignment_v1','mtf_trend_alignment_v1','trend_dmi_v1','mtf_trend_dmi_v1')
NAMES += ('regime_monotonic_v1','mtf_regime_monotonic_v1','regime_strength_v1','mtf_regime_strength_v1')
NAMES += ('momentum_rsi_direction_v1','mtf_momentum_rsi_direction_v1','momentum_macd_positive_v1','mtf_momentum_macd_positive_v1')


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
    if model not in ('observed','next-minute') or name not in NAMES or limit < 0:
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
        candidate = root / 'spot_candidates' / name
        declaration = json.loads((candidate/'protocol.json').read_text())
        overlays = declaration.get('overlays', {MTF:{'file':'mtf.py','sha256':declaration.get('source_sha256')}})
        if not overlays or set(overlays)-{MTF,COMPONENT,PERMISSION}:
            raise ValueError('Undeclared Spot source overlay')
        for path, entry in overlays.items():
            if entry['file'] not in ('mtf.py','component.py','permission.py') or lab.digest(candidate/entry['file'])!=entry['sha256']:
                raise ValueError('Candidate source hash mismatch')
            shutil.copyfile(candidate/entry['file'],output/entry['file'])
        lab.write(output/'candidate_protocol.json', declaration)
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


def compare(workspace, names=None, output_name='spot_comparison'):
    root=lab.outside_live(workspace);lab.verify(root)
    results={}
    for name in names or ('baseline-next-minute','unchanged','symmetric_all'):
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
    if output_name not in ('spot_comparison','spot_trend_comparison','spot_filter_comparison','spot_trend_rules_comparison','spot_regime_comparison','spot_momentum_comparison'):
        raise ValueError('Unsupported report destination')
    output=root/output_name;output.mkdir(exist_ok=True)
    ablations={}
    for reference,candidate in [('baseline-next-minute','trend_mirror_v1'),('symmetric_all','mtf_trend_mirror_v1')]:
        if candidate not in results:continue
        pairs=list(zip(results[reference]['cycles'],results[candidate]['cycles']))
        changed=[b for a,b in pairs if a['signal']['evaluated_direction']!=b['signal']['evaluated_direction']]
        ablations[candidate]={'reference':reference,
            'changed_BUY_decisions':sum(a['signal']['side']!=b['signal']['side'] for a,b in pairs),
            'changed_evaluated_directions':len(changed),
            'changed_short_scores':sum(a['signal']['direction_scores']['short']!=b['signal']['direction_scores']['short'] for a,b in pairs),
            'long_scores_and_gates_unchanged':all(a['signal']['direction_scores']['long']==b['signal']['direction_scores']['long'] and a['signal']['gates']==b['signal']['gates'] for a,b in pairs),
            'account_and_position_paths_unchanged':all(a['account_after']==b['account_after'] and a['positions']==b['positions'] for a,b in pairs),
            'max_long_score_on_changed_directions':max((r['signal']['direction_scores']['long'] for r in changed),default=None),
            'changed_directions_all_below_BUY_threshold':all(r['signal']['direction_scores']['long']<r['signal']['threshold'] for r in changed)}
    rule_ablations={}
    for name in ('trend_alignment_v1','mtf_trend_alignment_v1','trend_dmi_v1','mtf_trend_dmi_v1'):
        if name not in results:continue
        reference='symmetric_all' if name.startswith('mtf_') else 'baseline-next-minute'
        pairs=list(zip(results[reference]['cycles'],results[name]['cycles']))
        rule_ablations[name]={'reference':reference,
            'changed_BUY_decisions':sum(a['signal']['side']!=b['signal']['side'] for a,b in pairs),
            'changed_trend_scores':sum(a['signal']['component_scores']['trend']!=b['signal']['component_scores']['trend'] for a,b in pairs),
            'changed_trend_gates':sum(a['signal']['gates']['trend']!=b['signal']['gates']['trend'] for a,b in pairs),
            'other_long_components_unchanged':all({k:v for k,v in a['signal']['component_scores'].items() if k!='trend'}=={k:v for k,v in b['signal']['component_scores'].items() if k!='trend'} for a,b in pairs),
            'incremental_equity_USDT':round(results[name]['final_account']['equity']-results[reference]['final_account']['equity'],2),
            'added_BUY_quality':summarize_forward_returns([b for a,b in pairs if a['signal']['side']!='BUY' and b['signal']['side']=='BUY'],prices,protocol['end_ms']),
            'removed_BUY_quality':summarize_forward_returns([a for a,b in pairs if a['signal']['side']=='BUY' and b['signal']['side']!='BUY'],prices,protocol['end_ms'])}
        if not rule_ablations[name]['other_long_components_unchanged']:raise ValueError('Unrelated rule component changed')
    regime_ablations={}
    for name in ('regime_monotonic_v1','mtf_regime_monotonic_v1','regime_strength_v1','mtf_regime_strength_v1'):
        if name not in results:continue
        reference='symmetric_all' if name.startswith('mtf_') else 'baseline-next-minute'
        pairs=list(zip(results[reference]['cycles'],results[name]['cycles']))
        regime_ablations[name]={'reference':reference,
            'changed_BUY_decisions':sum(a['signal']['side']!=b['signal']['side'] for a,b in pairs),
            'changed_regime_scores':sum(a['signal']['component_scores']['regime']!=b['signal']['component_scores']['regime'] for a,b in pairs),
            'changed_regime_gates':sum(a['signal']['gates']['regime']!=b['signal']['gates']['regime'] for a,b in pairs),
            'other_long_components_unchanged':all({k:v for k,v in a['signal']['component_scores'].items() if k!='regime'}=={k:v for k,v in b['signal']['component_scores'].items() if k!='regime'} for a,b in pairs),
            'opposing_score_unchanged':all(a['signal']['direction_scores']['short']==b['signal']['direction_scores']['short'] for a,b in pairs),
            'incremental_equity_USDT':round(results[name]['final_account']['equity']-results[reference]['final_account']['equity'],2),
            'added_BUY_quality':summarize_forward_returns([b for a,b in pairs if a['signal']['side']!='BUY' and b['signal']['side']=='BUY'],prices,protocol['end_ms']),
            'removed_BUY_quality':summarize_forward_returns([a for a,b in pairs if a['signal']['side']=='BUY' and b['signal']['side']!='BUY'],prices,protocol['end_ms'])}
        if not regime_ablations[name]['other_long_components_unchanged'] or not regime_ablations[name]['opposing_score_unchanged']:
            raise ValueError('Undeclared REGIME effect on other components/opposing score')
    momentum_ablations={}
    for name in ('momentum_rsi_direction_v1','mtf_momentum_rsi_direction_v1','momentum_macd_positive_v1','mtf_momentum_macd_positive_v1'):
        if name not in results:continue
        reference='symmetric_all' if name.startswith('mtf_') else 'baseline-next-minute'
        pairs=list(zip(results[reference]['cycles'],results[name]['cycles']))
        momentum_ablations[name]={'reference':reference,
            'changed_BUY_decisions':sum(a['signal']['side']!=b['signal']['side'] for a,b in pairs),
            'changed_momentum_scores':sum(a['signal']['component_scores']['momentum']!=b['signal']['component_scores']['momentum'] for a,b in pairs),
            'changed_momentum_gates':sum(a['signal']['gates']['momentum']!=b['signal']['gates']['momentum'] for a,b in pairs),
            'other_long_components_unchanged':all({k:v for k,v in a['signal']['component_scores'].items() if k!='momentum'}=={k:v for k,v in b['signal']['component_scores'].items() if k!='momentum'} for a,b in pairs),
            'opposing_score_unchanged':all(a['signal']['direction_scores']['short']==b['signal']['direction_scores']['short'] for a,b in pairs),
            'incremental_equity_USDT':round(results[name]['final_account']['equity']-results[reference]['final_account']['equity'],2),
            'added_BUY_quality':summarize_forward_returns([b for a,b in pairs if a['signal']['side']!='BUY' and b['signal']['side']=='BUY'],prices,protocol['end_ms']),
            'removed_BUY_quality':summarize_forward_returns([a for a,b in pairs if a['signal']['side']=='BUY' and b['signal']['side']!='BUY'],prices,protocol['end_ms'])}
        if not momentum_ablations[name]['other_long_components_unchanged'] or not momentum_ablations[name]['opposing_score_unchanged']:
            raise ValueError('Undeclared MOMENTUM effect')
    lab.write(output/'results.json',{'results':summaries,'trend_ablations':ablations,'rule_ablations':rule_ablations,'regime_ablations':regime_ablations,'momentum_ablations':momentum_ablations,'limitations':base['limitations']+[
       'Earlier calendar overlaps the Futures candidate-selection period',
       'Later calendar is only about two days; not sufficient independent validation',
       'Chronological splits retain evolving positions, not independently reset accounts']})
    lines=['# Spot full replay: research ablation comparison','',
           '| Variant | BUY signals | New opens | Period net USDT | Final equity USDT | Equity difference | Cycle DD % |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for name,r in summaries.items():
        lines.append(f"| {name} | {r['actions'].get('BUY',0)} | {r['new_positions']} | {r['period_net_pnl']:.2f} | {r['final_account']['equity']:.2f} | {r['equity_difference_vs_baseline']:+.2f} | {r['cycle_drawdown_pct']:.4f} |")
    lines += ['','Split boundaries use the exact end of Futures research (2026-10-10 17:59:59.999 UTC).',
              'The later approximately two-day segment is descriptive, not sufficient independent validation.',
              'The unchanged control must reproduce all semantic cycle paths; random paper order UUIDs are excluded.',
              'No automatic promotion or live changes. Full per-cycle, permission and private SQLite evidence is retained.']
    if ablations:
        lines += ['','## Isolated TREND effect','',
            'Bearish TREND awards become 0.7/0.8/0.8/0.8 instead of 1/1/1/1; bullish awards and predicates stay unchanged.']
        for name,r in ablations.items():
            lines.append(f"- {name} versus {r['reference']}: {r['changed_short_scores']} changed opposing scores, {r['changed_evaluated_directions']} changed evaluated directions, {r['changed_BUY_decisions']} changed BUY decisions. Account/position paths unchanged: {r['account_and_position_paths_unchanged']}.")
        lines += ['','This ablation alone provides no BUY-quality or portfolio improvement on this period.',
            'Do not infer that TREND is sound or irrelevant: only directional point asymmetry was tested, not the indicator predicates or redundant evidence. No live promotion.']
    if rule_ablations:
        lines += ['','## TREND predicate ablations','',
            'alignment: remove only price dependence from EMA50/EMA200 point award.',
            'dmi: remove only ADX availability/strength dependence from DI point award.',
            'Original point awards and all position-entry filters stay unchanged. No proximity-off variant is used here.','']
        for name,r in rule_ablations.items():
            lines.append(f"- {name} versus {r['reference']}: {r['changed_trend_scores']} changed TREND scores, {r['changed_trend_gates']} changed TREND gates, {r['changed_BUY_decisions']} changed BUY decisions; incremental equity {r['incremental_equity_USDT']:+.2f} USDT.")
        lines += ['','### Added BUY signals (gross future prices, not trade PnL)','',
            '| Variant | Added BUY n | Horizon min | Labeled | Mean % | Median % | Positive % |',
            '|---|---:|---:|---:|---:|---:|---:|']
        for name,r in rule_ablations.items():
            for horizon,v in r['added_BUY_quality']['forward_returns'].items():
                fmt=lambda value: 'n/a' if value is None else f'{value:.4f}'
                lines.append(f"| {name} | {r['added_BUY_quality']['BUY_cycles']} | {horizon} | {v['labeled']} | {fmt(v['mean_pct'])} | {fmt(v['median_pct'])} | {fmt(v['positive_pct'])} |")
    if regime_ablations:
        lines += ['','## REGIME effects','',
            'monotonic: change only LONG ADX base awards above 25 to the existing 20-25 award (1.6).',
            'strength: replace whole LONG REGIME with existing shared ADX/spike helper; cannot attribute its effect to one removed term.',
            'TREND and all permission filters, including proximity, remain original.','']
        for name,r in regime_ablations.items():
            lines.append(f"- {name} versus {r['reference']}: {r['changed_regime_scores']} changed REGIME scores, {r['changed_regime_gates']} changed gates, {r['changed_BUY_decisions']} changed BUY decisions; incremental equity {r['incremental_equity_USDT']:+.2f} USDT.")
        lines += ['','### Added/removed BUY quality (gross price moves, not trade PnL)','',
            '| Variant | Group | BUY n | Horizon min | Labeled | Mean % | Median % | Positive % |',
            '|---|---|---:|---:|---:|---:|---:|---:|']
        for name,r in regime_ablations.items():
            for group in ('added_BUY_quality','removed_BUY_quality'):
                for horizon,v in r[group]['forward_returns'].items():
                    fmt=lambda value: 'n/a' if value is None else f'{value:.4f}'
                    lines.append(f"| {name} | {group} | {r[group]['BUY_cycles']} | {horizon} | {v['labeled']} | {fmt(v['mean_pct'])} | {fmt(v['median_pct'])} | {fmt(v['positive_pct'])} |")
    if momentum_ablations:
        lines += ['','## MOMENTUM effects','',
            'rsi_direction: only LONG RSI ladder becomes +1.4 above 50, without upper RSI ceiling.',
            'macd_positive: only LONG MACD award requires MACD>0 in addition to its original condition.',
            'Opposing MOMENTUM, TREND/REGIME, histogram disabled, weights/thresholds and all permissions remain original.','']
        for name,r in momentum_ablations.items():
            lines.append(f"- {name} versus {r['reference']}: {r['changed_momentum_scores']} changed MOMENTUM scores, {r['changed_momentum_gates']} changed gates, {r['changed_BUY_decisions']} changed BUY decisions; incremental equity {r['incremental_equity_USDT']:+.2f} USDT.")
        lines += ['','### Added/removed BUY quality (gross price moves, not trade PnL)','',
            '| Variant | Group | BUY n | Horizon min | Labeled | Mean % | Median % | Positive % |',
            '|---|---|---:|---:|---:|---:|---:|---:|']
        for name,r in momentum_ablations.items():
            for group in ('added_BUY_quality','removed_BUY_quality'):
                for horizon,v in r[group]['forward_returns'].items():
                    fmt=lambda value: 'n/a' if value is None else f'{value:.4f}'
                    lines.append(f"| {name} | {group} | {r[group]['BUY_cycles']} | {horizon} | {v['labeled']} | {fmt(v['mean_pct'])} | {fmt(v['median_pct'])} | {fmt(v['positive_pct'])} |")
    lines += ['','## BUY signal quality (forward open-price returns, not position win rate)','',
              '| Variant | Horizon min | BUY n | Mean % | Median % | Positive % |',
              '|---|---:|---:|---:|---:|---:|']
    for name,r in summaries.items():
        for horizon,v in r['BUY_forward_price_returns'].items():
            fmt=lambda value, digits: 'n/a' if value is None else f'{value:.{digits}f}'
            lines.append(f"| {name} | {horizon} | {v['BUY_n']} | {fmt(v['mean_pct'],4)} | {fmt(v['median_pct'],4)} | {fmt(v['positive_pct'],2)} |")
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    return output/'REPORT.md'


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','run','compare','compare-trend','compare-filters','compare-trend-rules','compare-regime','compare-momentum'])
    p.add_argument('workspace',type=Path)
    p.add_argument('--name',default='baseline')
    p.add_argument('--model',choices=['observed','next-minute'],default='observed')
    p.add_argument('--limit',type=int,default=0)
    a=p.parse_args()
    if a.command=='compare-trend':
        print(compare(a.workspace, ('baseline-next-minute','unchanged','symmetric_all','trend_mirror_v1','mtf_trend_mirror_v1'), 'spot_trend_comparison'))
    elif a.command=='compare-filters':
        print(compare(a.workspace, ('baseline-next-minute','unchanged','symmetric_all','proximity_off_v1','mtf_proximity_off_v1'), 'spot_filter_comparison'))
    elif a.command=='compare-trend-rules':
        print(compare(a.workspace, ('baseline-next-minute','unchanged','symmetric_all','trend_alignment_v1','mtf_trend_alignment_v1','trend_dmi_v1','mtf_trend_dmi_v1'), 'spot_trend_rules_comparison'))
    elif a.command=='compare-regime':
        print(compare(a.workspace, ('baseline-next-minute','unchanged','symmetric_all','regime_monotonic_v1','mtf_regime_monotonic_v1','regime_strength_v1','mtf_regime_strength_v1'), 'spot_regime_comparison'))
    elif a.command=='compare-momentum':
        print(compare(a.workspace, ('baseline-next-minute','unchanged','symmetric_all','momentum_rsi_direction_v1','mtf_momentum_rsi_direction_v1','momentum_macd_positive_v1','mtf_momentum_macd_positive_v1'), 'spot_momentum_comparison'))
    else:
        print(prepare(a.workspace) if a.command=='prepare' else compare(a.workspace) if a.command=='compare' else run(a.workspace,a.name,a.model,a.limit))
