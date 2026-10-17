"""Verify unchanged rules/control and compare standalone scenario accounts.

Usage: python -m platform_v2.tools.research.spot_backtest.isolate_compare WORKSPACE
Existing run/report directories are never overwritten.
"""
import ast
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys

from .candidates import ISOLATED_VARIANTS
from .compare import digest, load, summarize


def require(condition, message):
    if not condition:
        raise ValueError(message)


def definitions(path):
    tree = ast.parse(path.read_text())
    return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in ('finite', 'detectors', 'scenario_votes')}


def validate_isolation(rows, anchor_rows, active):
    require(len(rows) == len(anchor_rows), 'Different cycle count')
    for row, anchor in zip(rows, anchor_rows):
        require(tuple(row[k] for k in ('segment', 'timestamp_ms', 'quote_ms')) ==
            tuple(anchor[k] for k in ('segment', 'timestamp_ms', 'quote_ms')), 'Different cohort')
        d, a = row['candidate'], anchor['candidate']
        require(d['active_scenarios'] == [active], 'Scenario mask mismatch')
        for key in ('detected', 'scenario_votes', 'qualified', 'native_long_score', 'native_direction'):
            require(d[key] == a[key], 'Historical formulas changed: '+key)
        expected = active if active in a['qualified'] else None
        require(d['selected'] == expected, 'Selected inactive or unqualified scenario')
        require(d['raw_buy'] == (expected is not None), 'Wrong isolated raw BUY')
        require(d['votes'] == a['scenario_votes'][active], 'Votes differ from original scenario')
        require(row['signal']['setup_confidence'] == anchor['signal']['setup_confidence'], 'Confidence changed')
        expected_buy = expected is not None and anchor['signal']['side'] == 'BUY'
        require((row['signal']['side'] == 'BUY') == expected_buy, 'Isolated signal is not the original scenario subset')


def position_details(result, rows):
    by_quote = {(r['segment'], r['quote_ms']): r for r in rows}
    closed = [p for s in result['segments'] for p in s['positions'] if p['status'] == 'CLOSED']
    all_positions = [p for s in result['segments'] for p in s['positions']]
    selected = Counter()
    permission_reasons = Counter()
    for row in rows:
        if row['signal']['side'] == 'BUY':
            permission_reasons[row['permission']['reason'] if row['permission'] else 'no_permission'] += 1
    for s in result['segments']:
        require(s['initial_balance_USDT'] == 3000., 'Unexpected initial account size')
        for p in s['positions']:
            row = by_quote[(s['segment'], p['opened_at_ms'])]
            require(row['signal']['side'] == 'BUY', 'Position without BUY')
            require(row['permission'] is not None and row['permission']['status'] == 'ALLOWED', 'Position without permission')
            selected[row['candidate']['selected']] += 1
    return {'closed_exit_reasons': dict(Counter(p['exit_reason'] for p in closed)),
        'net_positive_closed_positions': sum(p['net_pnl']>0 for p in closed),
        'closed_net_expectancy_USDT': sum(p['net_pnl'] for p in closed)/len(closed) if closed else None,
        'open_positions': len(all_positions)-len(closed), 'opened_positions_by_selected_scenario': dict(selected),
        'first_permission_reason_on_BUY_exclusive': dict(permission_reasons)}


def main(root):
    root = root.resolve()
    protocol = json.loads((root/'protocol.json').read_text())
    require(digest(root/'market.sqlite3') == protocol['market_sha256'], 'Frozen market changed')
    anchor_result, anchor_rows = load(root, 'scenarios_votes_v1')
    control_result, control_rows = load(root, 'scenarios_control_v2')
    require(anchor_result == control_result and anchor_rows == control_rows, 'Combined control not exactly reproducible')
    del control_result, control_rows
    baseline_result, baseline_rows = load(root, 'baseline')
    keys = ('segment', 'timestamp_ms', 'quote_ms')
    require([tuple(r[k] for k in keys) for r in baseline_rows] ==
        [tuple(r[k] for k in keys) for r in anchor_rows], 'Baseline cohort mismatch')
    with sqlite3.connect((root/'market.sqlite3').as_uri()+'?mode=ro&immutable=1', uri=True) as db:
        prices = {stamp: json.loads(payload)['close'] for stamp, payload in db.execute("SELECT close_ms,payload FROM candles WHERE tf='15m'")}
    summaries = {'baseline': summarize(baseline_result, baseline_rows, prices),
        'scenarios_votes_v1': summarize(anchor_result, anchor_rows, prices) | position_details(anchor_result, anchor_rows)}
    del baseline_result, baseline_rows
    original_rules = json.loads((root/'runs/scenarios_votes_v1/candidate_protocol.json').read_text())['rules']
    original_definitions = definitions(root/'runs/scenarios_votes_v1/candidates.py')
    for name, active in ISOLATED_VARIANTS.items():
        folder = root/'runs'/name
        candidate_protocol = json.loads((folder/'candidate_protocol.json').read_text())
        require(candidate_protocol['rules'] == original_rules, 'Declared numeric rules changed')
        require(candidate_protocol['isolation']['active_scenarios'] == [active], 'Wrong frozen isolation mask')
        require(candidate_protocol['isolation']['reference_manifest_sha256'] == digest(root/'runs/scenarios_votes_v1/manifest.json'),
            'Different original combined reference')
        require(definitions(folder/'candidates.py') == original_definitions, 'Detector/vote implementation changed')
        result, rows = load(root, name)
        validate_isolation(rows, anchor_rows, active)
        extra = position_details(result, rows)
        require(set(extra['opened_positions_by_selected_scenario']) <= {active}, 'Position attributed to inactive scenario')
        summaries[name] = summarize(result, rows, prices) | extra
        print('Verified isolated scenario', active, flush=True)
        del result, rows
    pairwise = {}
    names = tuple(ISOLATED_VARIANTS.values())
    for i, first in enumerate(names):
        for second in names[i+1:]:
            pairwise[first+' & '+second] = sum(first in r['candidate']['qualified'] and second in r['candidate']['qualified'] for r in anchor_rows)
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'market_sha256': protocol['market_sha256'],
        'shared_cycles': len(anchor_rows), 'combined_control_exact_cycle_parity': True,
        'original_rule_implementation_unchanged': True, 'per_cycle_original_vote_vectors_unchanged': True,
        'runs': summaries, 'pairwise_qualified_overlaps_NOT_independent_trades': pairwise,
        'limits': ['Exploratory history already examined; no independent holdout and no deployment.',
            'Each scenario has its OWN fresh 3000 USDT account per segment. Never sum their returns as a combined portfolio.',
            'Combined run priority labels are not standalone performance; overlaps can enter several standalone accounts.',
            'Closed net excludes positions left open at boundaries; final account equity retains marked positions.',
            'Native fees included, zero additional slippage, modeled 1m-open fills and OHLC exits.',
            'Signals can be identical subsets while permissions/positions differ due to independent account and signal histories.',
            'Equal votes retain native weighted confidence for adaptive setups; structural detector overlaps STRUCTURE vote.']}
    out = root/'comparisons/scenarios_isolated_v1'
    out.mkdir(parents=True, exist_ok=False)
    (out/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    lines = ['# Standalone Spot scenarios: unchanged v1 rules', '',
        f'All {len(anchor_rows)} cycles share frozen inputs. Combined-control exact parity passed.', '',
        '| Variant | BUY candles | BUY episodes | Opened | Closed | Still open | Closed net USDT |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name, s in summaries.items():
        still_open = sum(seg['open_positions'] for seg in s['segments'])
        lines.append(f"| {name} | {s['buy_candles']} | {s['buy_episodes']} | {s['new_positions']} | {s['closed_positions']} | {still_open} | {s['closed_net_USDT']:+.4f} |")
    lines += ['', '## Independent covered segments', '',
        '| Variant | Segment | Closed net USDT | Still open | Final marked equity USDT |',
        '|---|---:|---:|---:|---:|']
    for name, s in summaries.items():
        for seg in s['segments']:
            lines.append(f"| {name} | {seg['segment']} | {seg['closed_net_USDT']:+.4f} | {seg['open_positions']} | {seg['final_account']['equity']:.2f} |")
    lines += ['', '## Limits', ''] + ['- '+limit for limit in report['limits']]
    lines += ['', 'All failed BUY permission checks, forward-price diagnostics and pairwise overlaps are in summary.json.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))
    source_names = ('isolate_compare.py', 'compare.py')
    for name in source_names:
        shutil.copyfile(Path(__file__).with_name(name), out/name)
    (out/'manifest.json').write_text(json.dumps({'analysis_sources': {name: digest(Path(__file__).with_name(name)) for name in source_names},
        'run_manifests': {name: digest(root/'runs'/name/'manifest.json') for name in ('baseline', 'scenarios_votes_v1', 'scenarios_control_v2', *ISOLATED_VARIANTS)},
        'files': {p.name: digest(p) for p in out.iterdir() if p.is_file()}}, indent=2)+'\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
