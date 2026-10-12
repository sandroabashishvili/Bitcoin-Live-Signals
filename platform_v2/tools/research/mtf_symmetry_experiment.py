"""Four predeclared offline MTF symmetry variants; no production promotion."""
from __future__ import annotations

import argparse
import ast
import gzip
import json
import statistics
from collections import Counter
from pathlib import Path

from platform_v2.tools.research import signal_lab as lab

VARIANTS = {'mtf_sym_4h_v1': ['4h'], 'mtf_sym_5m_v1': ['5m'],
            'mtf_sym_15m_v1': ['15m'], 'mtf_sym_all_v1': ['5m', '15m', '4h']}

HELPERS = '''
    @staticmethod
    def _symmetric_signal(timeframe, snapshot):
        import math
        def finite(value):
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        def compare(left, right):
            if not finite(left) or not finite(right):
                return 0
            return 1 if left > right else -1 if left < right else 0
        rsi = compare(snapshot.rsi, 50.0)
        if timeframe == "5m":
            if not finite(snapshot.adx) or snapshot.adx <= settings.REGIME_ADX_MIN:
                return "NO_SIGNAL"
            votes = [rsi, compare(snapshot.price, snapshot.vwap)]
            minimum = 2
        elif timeframe == "15m":
            votes = [rsi, compare(snapshot.ema50_slope, 0.0)]
            minimum = 2
        elif timeframe == "4h":
            votes = [rsi, compare(snapshot.tenkan, snapshot.kijun), compare(snapshot.ema50, snapshot.ema200)]
            minimum = 2
        else:
            raise ValueError("Unsupported symmetry timeframe")
        if votes.count(1) >= minimum:
            return "LONG"
        if votes.count(-1) >= minimum:
            return "SHORT"
        return "NO_SIGNAL"
'''


def candidate_source(original, timeframes):
    """Change only timeframe dispatch; original aggregation/scoring stays frozen."""
    tree = ast.parse(original)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MultiTimeframeContextService')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_signal_for_timeframe')
    lines = original.splitlines(keepends=True)
    insertion = next(i for i in range(fn.lineno, fn.end_lineno) if 'if timeframe == "5m"' in lines[i])
    lines.insert(insertion, f'        if timeframe in {tuple(timeframes)!r}:\n'
                           '            return MultiTimeframeContextService._symmetric_signal(timeframe, snapshot)\n\n')
    result = ''.join(lines) + HELPERS
    compile(result, '<mtf-symmetry-candidate>', 'exec')
    return result


def prepare(workspace):
    workspace = lab.outside_live(workspace)
    protocol = lab.verify(workspace)
    original = json.loads(gzip.decompress((workspace / 'source/source.json.gz').read_bytes()))['files'][lab.FILES['mtf']]
    target = workspace / 'experiments/mtf_symmetry_v1'
    target.mkdir(parents=True, exist_ok=False)
    lab.write(target / 'protocol.json', {
        'baseline': 'baseline-next-minute', 'variants': VARIANTS, 'input_protocol_sha256': lab.digest(workspace / 'protocol.json'),
        'period': [protocol['start_ms'], protocol['end_ms']],
        'rules': {'5m': 'RSI>50 and price>VWAP LONG; mirrored SHORT; ADX>20 for both',
                  '15m': 'RSI>50 and EMA50 slope>0 LONG; mirrored SHORT; MACD remains disabled',
                  '4h': '2 of RSI>50, Tenkan>Kijun, EMA50>EMA200 LONG; mirrored SHORT'},
        'boundary_policy': 'equal/missing/nonfinite values abstain; 4h requires two valid agreeing votes',
        'unchanged': ['MTF aggregation and raw score weights', 'other five components', 'master thresholds',
                      'entry permissions', 'sizing', 'fees', 'SL/TP/profit-lock formulas'],
        'evaluation': ['signals LONG/SHORT/NO_SIGNAL', 'permissions and positions', 'equity and realized/unrealized PnL',
                       'fees', '1m model assumptions', 'equity drawdown path', 'temporal stability'],
        'status': 'exploratory reused period, not independent validation; no automatic promotion'})
    for name, timeframes in VARIANTS.items():
        folder = lab.candidate(workspace, name)
        (folder / 'mtf.py').write_text(candidate_source(original, timeframes))
        lab.write(folder / 'candidate_protocol.json', {'timeframes': timeframes, 'component': 'mtf',
                  'source_sha256': lab.digest(folder / 'mtf.py'), 'scores_sha256': lab.digest(folder / 'scores.py')})
    return target


def report(workspace):
    workspace = lab.outside_live(workspace)
    inputs = lab.verify(workspace)
    experiment = workspace / 'experiments/mtf_symmetry_v1'
    declared = json.loads((experiment / 'protocol.json').read_text())
    if declared['input_protocol_sha256'] != lab.digest(workspace / 'protocol.json') or declared['variants'] != VARIANTS:
        raise ValueError('Predeclared experiment protocol changed')
    baseline_root = workspace / 'portfolio_runs/baseline-next-minute'
    lab._verify_run(workspace, baseline_root)
    base = json.loads((baseline_root / 'portfolio.json').read_text())
    if base['cycles'][0]['stats_after'] != base['initial_state']['stats']:
        raise ValueError('Common opening equity requires separate inherited-account valuation')
    opening_equity = base['cycles'][0]['summary']['equity']
    midpoint = (inputs['start_ms'] + inputs['end_ms']) // 2
    names = ['baseline-next-minute', *VARIANTS]
    summaries = {}
    for name in names:
        root = workspace / 'portfolio_runs' / name
        lab._verify_run(workspace, root)
        data = json.loads((root / 'portfolio.json').read_text())
        if name != 'baseline-next-minute':
            candidate = workspace / 'candidates' / name
            candidate_protocol = json.loads((candidate / 'candidate_protocol.json').read_text())
            if candidate_protocol['timeframes'] != VARIANTS[name]:
                raise ValueError('Candidate timeframe declaration changed')
            if lab.digest(root / 'mtf.py') != candidate_protocol['source_sha256'] or lab.digest(root / 'scores.py') != candidate_protocol['scores_sha256']:
                raise ValueError('Executed source differs from declared candidate')
            lab.portfolio_compare(workspace, name)
        if data['initial_state'] != base['initial_state'] or data['model'] != base['model']:
            raise ValueError('Initial state or execution model differs')
        points = [opening_equity, *[r['summary']['equity'] for r in data['cycles']]]
        peak, worst = points[0], 0.0
        for value in points:
            peak = max(peak, value)
            worst = max(worst, (peak - value) / peak * 100 if peak > 0 else 0)
        closes = [e for r in data['cycles'] for e in r['events'] if e.get('event') == 'CLOSED']
        nets = [r['net_pnl'] for r in closes]
        positives, negatives = sum(v for v in nets if v > 0), -sum(v for v in nets if v < 0)
        halves = {label: round(sum(r['stats_after']['total_net_pnl'] - r['stats_before']['total_net_pnl']
                  for r in data['cycles'] if (r['timestamp_ms'] < midpoint) == (label == 'first')), 2)
                  for label in ('first', 'second')}
        summary = {'actions': data['actions'], 'period_stats': data['stats_delta'],
            'final_equity': data['final_metrics']['equity'],
            'equity_difference_vs_baseline': round(data['final_metrics']['equity'] - base['final_metrics']['equity'], 2),
            'equity_change_from_common_opening': round(data['final_metrics']['equity'] - opening_equity, 2),
            'cycle_equity_max_drawdown_pct': round(worst, 4),
            'closed_net_positive_pct': round(100 * sum(v > 0 for v in nets) / len(nets), 2) if nets else None,
            'closed_net_median': statistics.median(nets) if nets else None,
            'closed_net_profit_factor': positives / negatives if negatives else None,
            'half_period_realized_net': halves, 'open_positions': data['final_metrics']['open_positions'],
            'unrealized_pnl': data['final_metrics']['unrealized_pnl'],
            'missing_modeled_quotes': len(data['missing_modeled_quotes']),
            'source_report_sha256': lab.digest(root / 'portfolio.json')}
        decision_rows = json.loads((root / 'result.json').read_text())['decisions']
        summary['mtf_timeframe_directions'] = {tf: dict(Counter(r['mtf_signals'][tf] for r in decision_rows)) for tf in ('5m', '15m', '4h')}
        summary['closed_net_by_direction'] = {side: round(sum(r['net_pnl'] for r in closes if r.get('side') == side), 2) for side in ('LONG', 'SHORT')}
        if name != 'baseline-next-minute':
            comparison = json.loads((root / 'portfolio_comparison.json').read_text())
            summary.update({k: comparison[k] for k in ('changed_signals', 'changed_permissions')})
        summaries[name] = summary
    output = {'protocol_sha256': lab.digest(experiment / 'protocol.json'), 'results': summaries,
              'common_opening_equity': opening_equity, 'temporal_split_ms': midpoint,
              'limitations': ['Four exploratory comparisons on reused 12-day history, not independent holdout',
                 'Closed-trade net includes two inherited initial positions; accounts share those positions',
                 'Half-period PnL uses cycle recognition, not an independently reset account in each half',
                 'Equity drawdown sampled at recorded cycles, not intraminute extrema',
                 'Signal direction counts alone do not establish quality',
                 'Observed historical PnL is not the comparison baseline; both variants use next-minute execution',
                 'No automatic candidate selection or production change']}
    lab.write(experiment / 'results.json', output)
    lines = ['# MTF symmetry: full-system exploratory replay', '',
             'Same frozen input data, initial account, production trading rules and next-minute execution model.', '',
             '| Variant | LONG | SHORT | NO SIGNAL | New opens | Closes | Period net USDT | Final equity USDT | Equity delta vs baseline | Cycle max DD % |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name, r in summaries.items():
        a, s = r['actions'], r['period_stats']
        lines.append(f"| {name} | {a.get('LONG',0)} | {a.get('SHORT',0)} | {a.get('NO_SIGNAL',0)} | {s['total_positions']:.0f} | {s['closed_positions']:.0f} | {s['total_net_pnl']:.2f} | {r['final_equity']:.2f} | {r['equity_difference_vs_baseline']:+.2f} | {r['cycle_equity_max_drawdown_pct']:.4f} |")
    lines += ['', '## Temporal stability (recognized realized net USDT)', '', '| Variant | First half | Second half |', '|---|---:|---:|']
    for name, r in summaries.items():
        h = r['half_period_realized_net']
        lines.append(f"| {name} | {h['first']:.2f} | {h['second']:.2f} |")
    lines += ['', '## Limits', '', *['- ' + v for v in output['limitations']], '',
              'Exact definitions and candidate hashes are retained in protocol.json and each candidate/run folder.']
    (experiment / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    return experiment / 'REPORT.md'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    print(report(args.workspace) if args.report else prepare(args.workspace))
