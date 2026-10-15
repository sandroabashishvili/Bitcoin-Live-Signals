"""Descriptive BUY-filter audit on verified frozen replay; no trade simulation."""
import argparse
import json
import math
import sqlite3
import statistics
from collections import Counter
from pathlib import Path

from platform_v2.tools.research import signal_lab as lab

HORIZONS = (15, 60, 240)


def failed_checks(row):
    permission = row.get('permission')
    if permission is None:
        raise ValueError('BUY without permission evidence')
    return tuple(sorted(k for k, v in permission['checks'].items() if v is False))


def summarize(rows, prices, end_ms):
    """Exact endpoint labels; never borrow later prices or fill missing minutes."""
    forwards = {}
    for horizon in HORIZONS:
        values = []
        missing = Counter()
        for row in rows:
            start = row['clock_ms']
            end = start + horizon * 60000
            if end + 60000 > end_ms:
                missing['outside_frozen_period'] += 1
            elif start not in prices:
                missing['entry_minute_missing'] += 1
            elif end not in prices:
                missing['endpoint_minute_missing'] += 1
            else:
                values.append((prices[end] / prices[start] - 1) * 100)
        forwards[str(horizon)] = {
            'labeled': len(values), 'missing': dict(missing),
            'mean_pct': statistics.mean(values) if values else None,
            'median_pct': statistics.median(values) if values else None,
            'positive_pct': 100 * sum(v > 0 for v in values) / len(values) if values else None,
        }
    return {'BUY_cycles': len(rows), 'forward_returns': forwards}


def audit_rows(rows, prices, end_ms):
    buys = [r for r in rows if r['signal']['side'] == 'BUY']
    allowed = [r for r in buys if r['permission']['status'] == 'ALLOWED']
    denied = [r for r in buys if r['permission']['status'] == 'DENIED']
    if len(allowed) + len(denied) != len(buys):
        raise ValueError('Unknown permission status')
    # Multiple failing checks are not collapsed into the first reported reason.
    failures = {r['observation_id']: failed_checks(r) for r in buys}
    checks = sorted({check for values in failures.values() for check in values})
    primary = sorted({r['permission']['reason'] for r in denied})
    return {
        'all_BUY': summarize(buys, prices, end_ms),
        'allowed': summarize(allowed, prices, end_ms),
        'denied': summarize(denied, prices, end_ms),
        'primary_reasons': {reason: summarize([r for r in denied if r['permission']['reason'] == reason], prices, end_ms) for reason in primary},
        'checks': {check: {
            'failed_including_overlaps': summarize([r for r in buys if check in failures[r['observation_id']]], prices, end_ms),
            'sole_failed_check': summarize([r for r in buys if failures[r['observation_id']] == (check,)], prices, end_ms),
            'other_checks_pass': summarize([r for r in buys if not set(failures[r['observation_id']]) - {check}], prices, end_ms),
        } for check in checks},
        'failure_combinations': dict(Counter(' + '.join(failures[r['observation_id']]) or 'none' for r in buys)),
    }


def run(workspace):
    root = lab.outside_live(workspace)
    lab.verify(root)
    protocol = json.loads((root / 'protocol.json').read_text())
    inputs = {}
    for name in ('baseline-next-minute', 'unchanged', 'symmetric_all'):
        folder = root / 'spot_runs' / name
        lab._verify_run(root, folder)
        inputs[name] = json.loads((folder / 'portfolio.json').read_text())
    baseline = inputs['baseline-next-minute']
    if not baseline['signal_parity_ok']:
        raise ValueError('Unverified baseline')
    semantic = lambda data: [{k: r[k] for k in ('timestamp_ms', 'signal', 'permission', 'account_after', 'positions')} for r in data['cycles']]
    if semantic(baseline) != semantic(inputs['unchanged']):
        raise ValueError('Unchanged control differs')
    for data in inputs.values():
        if data['initial_positions'] != baseline['initial_positions'] or [r['observation_id'] for r in data['cycles']] != [r['observation_id'] for r in baseline['cycles']]:
            raise ValueError('Account or cohort mismatch')
    with sqlite3.connect((root / 'data/market.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        prices = {}
        for stamp, text in db.execute("SELECT event_time_ms,payload_json FROM market_observations WHERE venue='binance' AND market_type='spot' AND dataset='candles' AND symbol='BTCUSDT' AND timeframe='1m' AND event_time_ms+60000<=?", (protocol['end_ms'],)):
            candle = json.loads(text)
            price = float(candle['open'])
            if stamp in prices or candle['timestamp'] != stamp or candle['close_time'] != stamp + 59999 or not math.isfinite(price) or price <= 0:
                raise ValueError('Invalid price labels')
            prices[stamp] = price
    results = {name: audit_rows(inputs[name]['cycles'], prices, protocol['end_ms']) for name in ('baseline-next-minute', 'symmetric_all')}
    output = root / 'spot_permission_audit'
    output.mkdir(exist_ok=False)
    limitations = [
        'Descriptive associations, NOT causal filter efficacy or a counterfactual portfolio replay.',
        'Fixed-horizon gross price returns, NOT net trade PnL, SL/TP outcomes or profit probabilities.',
        'Signal cycles overlap and cluster; observations are not independent trades.',
        'Filter groups differ in entry times and account state; cannot infer removal benefit from group means.',
        'Failure groups overlap; sole_failed_check identifies one-step candidates only in the existing trajectory.',
        'Removing a filter changes subsequent positions, balance, cooldown and proximity; full replay is required.',
        'Previously reused exploratory period; no independent validation and no live change.',
        'MTF symmetric_all is an unpromoted candidate, not production.',
    ]
    lab.write(output / 'results.json', {'results': results, 'start_ms': protocol['start_ms'], 'end_ms': protocol['end_ms'], 'limitations': limitations})
    fmt = lambda value: 'n/a' if value is None else f'{value:.4f}'
    lines = ['# Spot BUY permission audit', '', 'Research only; no production change.', '',
             'Labels: exact 1m opens at modeled decision clock and +15/+60/+240 minutes. No forward-filled gaps.',
             'These are gross market moves, not hypothetical trade profit.', '']
    for name, result in results.items():
        lines += [f'## {name}', '', '| Group | BUY cycles | Horizon min | Labeled | Mean % | Median % | Positive % |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        groups = {k: result[k] for k in ('all_BUY', 'allowed', 'denied')}
        groups.update({'primary:' + k: v for k, v in result['primary_reasons'].items()})
        for group, summary in groups.items():
            for horizon, value in summary['forward_returns'].items():
                lines.append(f"| {group} | {summary['BUY_cycles']} | {horizon} | {value['labeled']} | {fmt(value['mean_pct'])} | {fmt(value['median_pct'])} | {fmt(value['positive_pct'])} |")
        lines += ['', '### All failing checks (overlapping groups)', '', '| Check | All failures | Sole failure | Sole failure 60m mean % |', '|---|---:|---:|---:|']
        for check, values in result['checks'].items():
            sole = values['sole_failed_check']
            lines.append(f"| {check} | {values['failed_including_overlaps']['BUY_cycles']} | {sole['BUY_cycles']} | {fmt(sole['forward_returns']['60']['mean_pct'])} |")
    lines += ['', '## Limits', ''] + ['- ' + value for value in limitations]
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    lab.write(output / 'manifest.json', {'protocol_sha256': lab.digest(root / 'protocol.json'),
        'runs': {name: lab.digest(root / 'spot_runs' / name / 'manifest.json') for name in inputs},
        'files': {name: lab.digest(output / name) for name in ('REPORT.md', 'results.json')},
        'audit_source_sha256': lab.digest(Path(__file__)), 'runtime_changed': False})
    return output / 'REPORT.md'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    print(run(parser.parse_args().workspace))
