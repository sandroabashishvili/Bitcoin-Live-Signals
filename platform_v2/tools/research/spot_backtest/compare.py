"""Verify sealed runs and produce a reproducible exploratory comparison.

Usage: python -m platform_v2.tools.research.spot_backtest.compare WORKSPACE
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import shutil
import sys

NAMES = ('baseline', 'control_v2', 'votes_existing_v1', 'scenarios_votes_v1')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(root, name):
    folder = root/'runs'/name
    manifest = json.loads((folder/'manifest.json').read_text())
    assert digest(root/'protocol.json') == manifest['protocol_sha256'], 'Protocol mismatch'
    for filename, expected in manifest['files'].items():
        assert digest(folder/filename) == expected, f'Run evidence changed: {name}/{filename}'
    if name != 'baseline':
        sealed = json.loads((folder/'pre_run_manifest.json').read_text())
        for filename, expected in sealed['files'].items():
            assert digest(folder/filename) == expected, f'Pre-run input changed: {name}/{filename}'
    return json.loads((folder/'results.json').read_text()), [json.loads(line) for line in (folder/'cycles.jsonl').open()]


def episodes(rows):
    """One episode begins at each NO_SIGNAL->BUY transition or segment boundary."""
    selected = []
    previous = None
    for row in rows:
        if row['signal']['side'] == 'BUY' and (previous is None or previous['segment'] != row['segment']
                or previous['signal']['side'] != 'BUY'):
            selected.append(row)
        previous = row
    return selected


def summarize(result, rows, prices):
    buys = [r for r in rows if r['signal']['side'] == 'BUY']
    starts = episodes(rows)
    checks = Counter()
    for row in buys:
        permission = row['permission']
        if permission and permission['status'] != 'ALLOWED':
            checks.update(k for k, passed in permission['checks'].items() if not passed)
    per_segment = []
    position_tags = Counter()
    by_quote = {(r['segment'], r['quote_ms']): r for r in rows}
    for s in result['segments']:
        for p in s['positions']:
            row = by_quote[(s['segment'], p['opened_at_ms'])]
            tag = row.get('candidate', {}).get('selected')
            if tag: position_tags[tag] += 1
        per_segment.append({k: s[k] for k in ('segment', 'start_ms', 'last_signal_close_ms', 'cycles',
            'new_positions', 'closed_positions', 'open_positions', 'closed_net_USDT', 'exit_reasons', 'final_account')})
    cohort = {(r['segment'], r['timestamp_ms']) for r in rows}
    forward = {}
    for hours in (1, 4, 12):
        values = [100*(prices[r['timestamp_ms']+hours*3600000]/r['signal']['snapshot_price']-1)
            for r in starts if (r['segment'], r['timestamp_ms']+hours*3600000) in cohort]
        forward[str(hours)+'h'] = {'episodes_with_coverage': len(values), 'excluded': len(starts)-len(values),
            'mean_close_change_pct': sum(values)/len(values) if values else None,
            'positive_pct': 100*sum(v>0 for v in values)/len(values) if values else None}
    detected, qualified, selected = Counter(), Counter(), Counter()
    for row in rows:
        d = row.get('candidate', {})
        detected.update(k for k,v in d.get('detected', {}).items() if v)
        qualified.update(d.get('qualified', []))
        if d.get('selected'): selected[d['selected']] += 1
    return {'buy_candles': len(buys), 'buy_episodes': len(starts), 'new_positions': result['new_positions'],
        'closed_positions': result['closed_positions'], 'closed_net_USDT': result['closed_net_USDT'],
        'all_failed_permission_checks_on_BUY': dict(checks), 'segments': per_segment,
        'detected_scenarios_overlapping': dict(detected), 'qualified_scenarios_overlapping': dict(qualified),
        'selected_scenarios_one_per_cycle': dict(selected), 'positions_by_selected_scenario': dict(position_tags),
        'forward_close_change_by_episode_NOT_trade_PnL': forward}


def main(root):
    root = root.resolve()
    protocol = json.loads((root/'protocol.json').read_text())
    assert digest(root/'market.sqlite3') == protocol['market_sha256'], 'Market changed'
    loaded = {name: load(root, name) for name in NAMES}
    baseline, base_rows = loaded['baseline']
    assert baseline == loaded['control_v2'][0], 'Refactored control results changed'
    assert base_rows == loaded['control_v2'][1], 'Refactored control cycle parity failed'
    keys = [(r['segment'], r['timestamp_ms'], r['quote_ms']) for r in base_rows]
    for _, rows in loaded.values():
        assert [(r['segment'], r['timestamp_ms'], r['quote_ms']) for r in rows] == keys, 'Different cohort'
    with sqlite3.connect((root/'market.sqlite3').as_uri()+'?mode=ro&immutable=1', uri=True) as db:
        prices = {stamp: json.loads(payload)['close'] for stamp, payload in db.execute("SELECT close_ms,payload FROM candles WHERE tf='15m'")}
    summary = {name: summarize(result, rows, prices) for name, (result, rows) in loaded.items()}
    single_account=len(baseline['segments'])==1
    for name, (_, rows) in loaded.items():
        summary[name]['new_BUY_candles_vs_baseline'] = sum(r['signal']['side']=='BUY' and b['signal']['side']!='BUY' for r,b in zip(rows, base_rows))
        summary[name]['removed_BUY_candles_vs_baseline'] = sum(r['signal']['side']!='BUY' and b['signal']['side']=='BUY' for r,b in zip(rows, base_rows))
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'market_sha256': protocol['market_sha256'],
        'control_exact_cycle_parity': True, 'shared_cycles': len(base_rows), 'runs': summary,
        'caveats': ['Exploratory, no holdout and no deployment.', 'BUY candles are states, not independent trades; episode counts also are not independent statistical samples.',
            ('One continuous account per variant, initial 3000 USDT. Closed net excludes open positions; final equity includes marks, not hypothetical closing costs.' if single_account else
             'Closed net sums independent fresh accounts per segment; inspect open marked equity separately.'),
            'Scenario attributions in the combined strategy are NOT independent standalone scenario backtests.',
            'Equal-existing also removes opposing SHORT veto. Scenario candidate changes component definitions too; not a pure single-parameter ablation.',
            'Native weighted setup confidence preserved, equal weights apply only to signal votes. STRUCTURE vote overlaps mandatory scenario trigger.',
            'Forward changes are unadjusted snapshot-close to future-close diagnostics, not execution PnL, and have no market-matched benchmark.']}
    out = root/'comparisons'/'votes_scenarios_v1'
    out.mkdir(parents=True, exist_ok=False)
    (out/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    lines = ['# Spot equal votes and scenarios: exploratory comparison', '',
        f'Exact unchanged-control parity: {len(base_rows)} cycles. Same frozen inputs; no deployment.', '',
        '| Variant | BUY candles | BUY episodes | Positions | Still open | Closed net USDT* |',
        '|---|---:|---:|---:|---:|---:|']
    for name, s in summary.items():
        still_open=sum(segment['open_positions'] for segment in s['segments'])
        lines.append(f"| {name} | {s['buy_candles']} | {s['buy_episodes']} | {s['new_positions']} | {still_open} | {s['closed_net_USDT']:+.4f} |")
    lines += ['', ('*One continuous account per variant; closed net excludes open positions.' if single_account else
        '*Sum across separate fresh accounts, not a continuous-account return.'), '', '## Segment results', '']
    for name, s in summary.items():
        lines.append(f'### {name}\n')
        for segment in s['segments']:
            lines.append(f"- Segment {segment['segment']}: {segment['new_positions']} positions, {segment['open_positions']} open, closed net {segment['closed_net_USDT']:+.4f}; final equity {segment['final_account']['equity']:.2f}.")
        lines.append('')
    lines += ['## Interpretation limits', ''] + ['- '+c for c in report['caveats']]
    lines += ['', 'Detailed permission checks, per-scenario overlap and episode forward-price diagnostics are in summary.json.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))
    (out/'manifest.json').write_text(json.dumps({'source_sha256': digest(Path(__file__)), 'files': {p.name: digest(p) for p in out.iterdir() if p.is_file()},
        'run_manifests': {name: digest(root/'runs'/name/'manifest.json') for name in NAMES}}, indent=2)+'\n')
    print('\n'.join(lines))


def continuous_summary(root):
    """Consolidate the declared continuous round, preserving all prior reports."""
    root=root.resolve()
    declaration=json.loads((root/'continuous_experiment_protocol.json').read_text())
    if digest(root/'market.sqlite3')!=declaration['market_sha256']:
        raise ValueError('Continuous round market changed')
    verified={}
    for name in declaration['runs']:
        folder=root/'runs'/name
        manifest=json.loads((folder/'manifest.json').read_text())
        if manifest['protocol_sha256']!=digest(root/'protocol.json'):raise ValueError('Wrong data protocol')
        for filename,expected in manifest['files'].items():
            if digest(folder/filename)!=expected:raise ValueError('Run evidence changed: '+name+'/'+filename)
        run_protocol=json.loads((folder/'candidate_protocol.json').read_text())
        if run_protocol.get('continuous_experiment')!=declaration:
            raise ValueError('Different round declaration: '+name)
        result=json.loads((folder/'results.json').read_text())
        if len(result['segments'])!=1 or result['cycles']!=declaration['expected_cycles']:
            raise ValueError('Not a complete continuous-account result: '+name)
        verified[name]=result
    for first,second in (('baseline','control_v2'),('scenarios_votes_v1','scenarios_control_v2')):
        for filename in ('results.json','cycles.jsonl'):
            if digest(root/'runs'/first/filename)!=digest(root/'runs'/second/filename):
                raise ValueError('Exact deterministic control parity failed: '+first)
    labels={'baseline':'Current pinned logic','votes_existing_v1':'Existing gates, equal 4/6',
        'scenarios_votes_v1':'Five scenarios combined','scenario_pullback_v1':'Pullback',
        'scenario_breakout_v1':'Breakout','scenario_reversal_v1':'Bullish reversal',
        'scenario_range_bounce_v1':'Range bounce','scenario_failed_break_v1':'Failed break / reclaim'}
    rows={}
    for name,label in labels.items():
        result=verified[name];segment=result['segments'][0]
        if segment['initial_balance_USDT']!=3000.:raise ValueError('Unexpected initial capital')
        rows[name]={'label':label,'BUY_candles':result['actions'].get('BUY',0),'positions':result['new_positions'],
            'closed':result['closed_positions'],'open':segment['open_positions'],'closed_net_USDT':result['closed_net_USDT'],
            'final_marked_equity_USDT':segment['final_account']['equity'],'final_account':segment['final_account'],
            'start_ms':segment['start_ms'],'last_signal_close_ms':segment['last_signal_close_ms']}
    out=root/'comparisons/continuous_round_v1';out.mkdir(parents=True,exist_ok=False)
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'declaration':declaration,
        'exact_baseline_control':True,'exact_combined_control':True,'runs':rows,
        'limits':['Research only; no untouched holdout, no production deployment.',
            'One continuous native 3000 USDT account PER VARIANT; variant results are not additive.',
            'Native fees included; zero additional slippage; modeled minute-open fills and OHLC exits, not actual exchange execution.',
            'Closed net excludes remaining open positions; marked equity does not deduct hypothetical closing fees.',
            'Same existing hypotheses and numeric definitions, no parameter tuning in this round.',
            'Native weighted setup confidence remains in SL/TP; equal weights apply to signal votes. Several votes are correlated.']}
    (out/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    lines=['# Continuous-account Spot comparison', '',
        f"Every variant: {declaration['expected_cycles']} decisions, one continuous account starting at 3000 USDT. Both exact controls passed.", '',
        '| Variant | BUY candles | Positions | Closed | Open | Closed net USDT | Final marked equity USDT |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows.values():
        lines.append(f"| {row['label']} | {row['BUY_candles']} | {row['positions']} | {row['closed']} | {row['open']} | {row['closed_net_USDT']:+.4f} | {row['final_marked_equity_USDT']:.2f} |")
    first=next(iter(rows.values()))
    lines+=['', 'Period UTC: '+datetime.fromtimestamp(first['start_ms']/1000,timezone.utc).isoformat()+
        ' through '+datetime.fromtimestamp(first['last_signal_close_ms']/1000,timezone.utc).isoformat()+'.', '', '## Limits', '']
    lines+=['- '+limit for limit in report['limits']]
    lines+=['', 'Detailed signal/permission diagnostics: ../votes_scenarios_v1 and ../scenarios_isolated_v1.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))
    shutil.copyfile(Path(__file__),out/'compare.py')
    (out/'manifest.json').write_text(json.dumps({'round_declaration_sha256':digest(root/'continuous_experiment_protocol.json'),
        'run_manifests':{name:digest(root/'runs'/name/'manifest.json') for name in declaration['runs']},
        'files':{p.name:digest(p) for p in out.iterdir() if p.is_file()}},indent=2)+'\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    continuous_summary(Path(sys.argv[1])) if '--continuous-summary' in sys.argv[2:] else main(Path(sys.argv[1]))
