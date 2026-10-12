"""Frozen signal and portfolio experiments. Never touches live positions or deploys."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path

LIVE = Path('/home/sandro/SmartSignalHub/platform_v2/runtime').resolve()
FILES = {
    'scores': 'platform_v2/futures/services/signal/futures_component_score_service.py',
    'mtf': 'platform_v2/futures/services/signal/futures_mtf_context_service.py',
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


def launch_recorded(command, output):
    """Keep the console evidence as well as structured results on failed runs."""
    with (output / 'console.log').open('x') as log:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end='', flush=True)
            return process.wait()


def outside_live(path):
    path = Path(path).expanduser().resolve()
    if path == LIVE or path.is_relative_to(LIVE) or LIVE.is_relative_to(path):
        raise ValueError('Research destination must be separate from live runtime')
    return path


def create(workspace, trading_db, market_db, release, start_ms, end_ms):
    workspace = outside_live(workspace)
    if end_ms <= start_ms:
        raise ValueError('Invalid research time range')
    release = Path(release).resolve()
    raw = gzip.decompress((release / 'source.json.gz').read_bytes())
    sha = hashlib.sha256(raw).hexdigest()
    if sha != (release / 'sha256.txt').read_text().strip():
        raise ValueError('Pinned source hash mismatch')
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / 'data').mkdir()
    (workspace / 'source').mkdir()
    for name in ('source.json.gz', 'run.py', 'sha256.txt'):
        shutil.copyfile(release / name, workspace / 'source' / name)
    databases = {}
    for name, source in [('trading', trading_db), ('market', market_db)]:
        source = Path(source).expanduser().resolve()
        target = workspace / 'data' / (name + '.sqlite3')
        # Online backup includes WAL contents; never copy a live SQLite file directly.
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
            with sqlite3.connect(target) as dst:
                src.backup(dst)
                if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Snapshot integrity check failed')
        target.chmod(0o444)
        databases[name] = {'source': str(source), 'sha256': digest(target)}
    protocol = {'format': 1, 'created_utc': datetime.now(UTC).isoformat(),
                'start_ms': start_ms, 'end_ms': end_ms, 'source_sha256': sha,
                'databases': databases, 'horizons_minutes': [15, 60, 240],
                'runner_sha256': digest(workspace / 'source/run.py'),
                'scope': 'signal quality only; no fees, positions or TP/SL',
                'validation': 'exploratory reused history, not independent holdout'}
    write(workspace / 'protocol.json', protocol)
    candidate(workspace, 'unchanged')
    return workspace


def candidate(workspace, name):
    workspace = outside_live(workspace)
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name):
        raise ValueError('Use a lowercase experiment name')
    target = workspace / 'candidates' / name
    target.mkdir(parents=True, exist_ok=False)
    files = json.loads(gzip.decompress((workspace / 'source/source.json.gz').read_bytes()))['files']
    for key, relative in FILES.items():
        (target / (key + '.py')).write_text(files[relative])
    return target


def verify(workspace):
    workspace = outside_live(workspace)
    p = json.loads((workspace / 'protocol.json').read_text())
    for name, item in p['databases'].items():
        if digest(workspace / 'data' / (name + '.sqlite3')) != item['sha256']:
            raise ValueError('Frozen database changed: ' + name)
    raw = gzip.decompress((workspace / 'source/source.json.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest() != p['source_sha256']:
        raise ValueError('Frozen source changed')
    if digest(workspace / 'source/run.py') != p['runner_sha256']:
        raise ValueError('Frozen launcher changed')
    return p


def run(workspace, name='baseline', limit=0, component=None):
    workspace = outside_live(workspace)
    if limit < 0 or not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name):
        raise ValueError('Invalid run name or limit')
    verify(workspace)
    if name != 'baseline':
        if component not in ('mtf', 'regime', 'trend', 'momentum', 'orderbook', 'structure'):
            raise ValueError('Declare exactly one changed component')
        baseline = json.loads((workspace / 'runs/baseline/result.json').read_text())
        if not baseline['parity_ok'] or baseline['limit'] != limit:
            raise ValueError('A matching, parity-verified baseline is required')
    output = workspace / 'runs' / name
    output.mkdir(parents=True, exist_ok=False)
    if name != 'baseline':
        for key in FILES:
            shutil.copyfile(workspace / 'candidates' / name / (key + '.py'), output / (key + '.py'))
    worker = Path(__file__).with_name('signal_lab_worker.py')
    shutil.copyfile(worker, output / 'worker.py')
    command = [sys.executable, '-B', str(output / 'worker.py'), str(workspace), name, str(limit), component or '']
    returncode = launch_recorded(command, output)
    verify(workspace)
    if returncode:
        raise RuntimeError('Research replay failed; inspect ' + str(output))
    # Retain exact executable candidate code even if editable files change later.
    if name != 'baseline':
        report = json.loads((output / 'result.json').read_text())
        for key, expected in report['overlays'].items():
            if digest(output / (key + '.py')) != expected:
                raise ValueError('Candidate source changed during replay')
    write(output / 'manifest.json', {'files': {p.name: digest(p) for p in output.iterdir() if p.is_file()},
                                    'protocol_sha256': digest(workspace / 'protocol.json')})
    return output


def compare(workspace, name):
    import statistics
    workspace = outside_live(workspace)
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name):
        raise ValueError('Invalid candidate name')
    protocol = verify(workspace)
    for run_name in ('baseline', name):
        run_root = workspace / 'runs' / run_name
        manifest = json.loads((run_root / 'manifest.json').read_text())
        if manifest['protocol_sha256'] != digest(workspace / 'protocol.json'):
            raise ValueError('Run protocol changed')
        for filename, expected in manifest['files'].items():
            if digest(run_root / filename) != expected:
                raise ValueError('Run artifact changed: ' + filename)
    base = json.loads((workspace / 'runs/baseline/result.json').read_text())
    test = json.loads((workspace / 'runs' / name / 'result.json').read_text())
    if not base['parity_ok'] or not test['parity_ok']:
        raise ValueError('Only verified runs can be compared')
    if [r['observation_id'] for r in base['decisions']] != [r['observation_id'] for r in test['decisions']]:
        raise ValueError('Different cohorts')
    with sqlite3.connect((workspace / 'data/market.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        prices = {}
        for t, payload in db.execute("SELECT event_time_ms,payload_json FROM market_observations WHERE venue='binance' AND market_type='futures' AND dataset='candles' AND symbol='BTCUSDT' AND timeframe='1m' AND event_time_ms+60000<=?", (protocol['end_ms'],)):
            r = json.loads(payload)
            price = float(r['open'])
            if t in prices or not math.isfinite(price) or price <= 0 or r['close_time'] != t + 59999:
                raise ValueError('Invalid/duplicate label candle')
            prices[t] = price
    report = {'scope': protocol['scope'], 'validation': protocol['validation'],
              'changed_actions': sum(a['selected_direction'] != b['selected_direction'] for a, b in zip(base['decisions'], test['decisions'])),
              'baseline_actions': base['actions'], 'candidate_actions': test['actions'], 'horizons': {}}
    for h in protocol['horizons_minutes']:
        values = {'baseline': {'LONG': [], 'SHORT': []}, 'candidate': {'LONG': [], 'SHORT': []}}
        missing = 0
        for a, b in zip(base['decisions'], test['decisions']):
            start = (a['available_ms'] // 60000 + 1) * 60000
            end = start + h * 60000
            if start not in prices or end not in prices:
                missing += 1
                continue
            ret = (prices[end] / prices[start] - 1) * 100
            for key, row in [('baseline', a), ('candidate', b)]:
                side = row['selected_direction']
                if side in ('LONG', 'SHORT'):
                    values[key][side].append(ret if side == 'LONG' else -ret)
        report['horizons'][str(h)] = {'missing_labels': missing, **{
            key: {side: {'n': len(v), 'mean_pct': statistics.mean(v) if v else None,
                          'median_pct': statistics.median(v) if v else None,
                          'positive_pct': 100 * sum(x > 0 for x in v) / len(v) if v else None}
                  for side, v in sides.items()} for key, sides in values.items()}}
    write(workspace / 'runs' / name / 'comparison.json', report)
    return report


def portfolio_run(workspace, name='baseline', model='observed', limit=0, component=None):
    workspace = outside_live(workspace)
    if model not in ('observed', 'next-minute') or limit < 0 or not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name):
        raise ValueError('Invalid replay model, name or limit')
    verify(workspace)
    if name != 'baseline' and model != 'next-minute':
        raise ValueError('Candidates require a uniform next-minute execution model')
    if model == 'next-minute':
        observed_root = workspace / 'portfolio_runs/baseline-observed'
        _verify_run(workspace, observed_root)
        observed = json.loads((observed_root / 'portfolio.json').read_text())
        smoke = json.loads((observed_root / 'result.json').read_text())['limit']
        if not observed['historical_parity_ok'] or smoke != limit:
            raise ValueError('A matching, historically verified observed baseline is required')
        if not limit:
            verification = json.loads((observed_root / 'historical_verification.json').read_text())
            if not verification['passed']:
                raise ValueError('Observed baseline failed independent event/account verification')
    if name != 'baseline':
        if component not in ('mtf', 'regime', 'trend', 'momentum', 'orderbook', 'structure'):
            raise ValueError('Declare exactly one candidate component')
        baseline_root = workspace / 'portfolio_runs/baseline-next-minute'
        _verify_run(workspace, baseline_root)
        model_result = json.loads((baseline_root / 'result.json').read_text())
        if not model_result['parity_ok']:
            raise ValueError('Execution-model baseline failed signal reconstruction')
        if model_result['limit'] != limit:
            raise ValueError('Baseline sample differs')
    run_id = 'baseline-' + model if name == 'baseline' else name
    output = workspace / 'portfolio_runs' / run_id
    output.mkdir(parents=True, exist_ok=False)
    for module, target in [('signal_lab_worker.py', 'worker.py'), ('portfolio_lab_support.py', 'portfolio_lab_support.py')]:
        shutil.copyfile(Path(__file__).with_name(module), output / target)
    if name != 'baseline':
        for key in FILES:
            shutil.copyfile(workspace / 'candidates' / name / (key + '.py'), output / (key + '.py'))
    write(output / 'execution_protocol.json', {'model': model, 'component': component, 'limit': limit,
          'starting_state': 'captured_before_first_cycle', 'late_cycles': 'included_for_state_continuity',
          'candidate_scope': 'component logic only, weights/execution rules frozen'})
    command = [sys.executable, '-B', str(output / 'worker.py'), str(workspace), name, str(limit), component or '', model, run_id]
    returncode = launch_recorded(command, output)
    verify(workspace)
    if name != 'baseline' and (output / 'result.json').exists():
        replay_result = json.loads((output / 'result.json').read_text())
        for key, expected in replay_result['overlays'].items():
            if digest(output / (key + '.py')) != expected:
                raise ValueError('Candidate source changed during portfolio replay')
    write(output / 'manifest.json', {'files': {p.name: digest(p) for p in output.iterdir() if p.is_file()},
                                    'protocol_sha256': digest(workspace / 'protocol.json')})
    if returncode:
        raise RuntimeError('Portfolio replay did not pass validation; inspect ' + str(output))
    if model == 'observed' and name == 'baseline' and not limit:
        verification = portfolio_verify(workspace, run_id)
        if not verification['passed']:
            raise RuntimeError('Independent event/account verification failed: ' + str(output))
    return output


def _verify_run(workspace, run_root):
    manifest = json.loads((run_root / 'manifest.json').read_text())
    if manifest['protocol_sha256'] != digest(workspace / 'protocol.json'):
        raise ValueError('Run protocol changed')
    for filename, expected in manifest['files'].items():
        if digest(run_root / filename) != expected:
            raise ValueError('Run artifact changed: ' + filename)


def portfolio_compare(workspace, name):
    workspace = outside_live(workspace)
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name):
        raise ValueError('Invalid candidate name')
    verify(workspace)
    roots = {k: workspace / 'portfolio_runs' / v for k, v in [('baseline', 'baseline-next-minute'), ('candidate', name)]}
    reports = {}
    for key, path in roots.items():
        _verify_run(workspace, path)
        reports[key] = json.loads((path / 'portfolio.json').read_text())
    a, b = reports['baseline'], reports['candidate']
    if a['signal_parity_ok'] is not True:
        raise ValueError('Execution-model baseline failed signal reconstruction')
    if a['model'] != b['model'] or a['model'] != 'next-minute' or a['initial_state'] != b['initial_state'] or a['profile'] != b['profile']:
        raise ValueError('Incompatible execution model or initial account')
    if [r['observation_id'] for r in a['cycles']] != [r['observation_id'] for r in b['cycles']]:
        raise ValueError('Different replay schedules')
    output = {'scope': 'Full production Futures simulation with modeled next-minute execution',
              'changed_signals': sum(x['signal'] != y['signal'] for x, y in zip(a['cycles'], b['cycles'])),
              'changed_permissions': sum((x['permission_status'], x['permission_reason']) != (y['permission_status'], y['permission_reason']) for x, y in zip(a['cycles'], b['cycles'])),
              'same_final_state': a['final_state'] == b['final_state'],
              'same_cycle_paths': a['cycles'] == b['cycles'],
              'same_final_metrics': a['final_metrics'] == b['final_metrics'],
              'input_report_sha256': {key: digest(path / 'portfolio.json') for key, path in roots.items()},
              'baseline': {k: a[k] for k in ('actions', 'stats_delta', 'event_counts', 'denials', 'final_metrics', 'missing_modeled_quotes')},
              'candidate': {k: b[k] for k in ('actions', 'stats_delta', 'event_counts', 'denials', 'final_metrics', 'missing_modeled_quotes')},
              'limitations': a['limitations']}
    write(roots['candidate'] / 'portfolio_comparison.json', output)
    return roots['candidate'] / 'portfolio_comparison.json'


def portfolio_verify(workspace, run_id='baseline-observed'):
    """Independent terminal-state and OPENED/CLOSED parity against frozen archive."""
    workspace = outside_live(workspace)
    if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in run_id):
        raise ValueError('Invalid run id')
    verify(workspace)
    root = workspace / 'portfolio_runs' / run_id
    _verify_run(workspace, root)
    report = json.loads((root / 'portfolio.json').read_text())
    result = json.loads((root / 'result.json').read_text())
    if report['model'] != 'observed' or result['limit']:
        raise ValueError('Only complete observed-mode runs have historical terminal parity')
    ids = {p['position_id'] for p in report['initial_state']['open_positions']}
    actual = {}
    for cycle in report['cycles']:
        for event in cycle['events']:
            if event['event'] in ('OPENED', 'CLOSED'):
                key = (event['position_id'], event['event'])
                if key in actual:
                    raise ValueError('Duplicate replay trade event')
                actual[key] = event
                ids.add(event['position_id'])
    expected = {}
    with sqlite3.connect((workspace / 'data/trading.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        terminal = json.loads(db.execute("SELECT payload_json FROM runtime_state WHERE system='futures' AND state_key='simulation_engine'").fetchone()[0])
        for text, in db.execute("SELECT payload_json FROM runtime_rows WHERE system='futures' AND family='futures_position_events'"):
            r = json.loads(text)
            key = (r.get('position_id'), r.get('event'))
            if key[0] in ids and key[1] in ('OPENED', 'CLOSED'):
                if key[1] == 'OPENED' and key[0] in {p['position_id'] for p in report['initial_state']['open_positions']}:
                    continue
                if key in expected:
                    raise ValueError('Duplicate historical trade event')
                expected[key] = r
    fields = ('timestamp_ms', 'entry_price', 'exit_price', 'side', 'outcome', 'net_pnl', 'gross_pnl',
              'fees_paid', 'execution', 'opened_at_ms', 'position_management', 'management_policy_applied')
    differences = [{'position_id': key[0], 'event': key[1], 'fields': [k for k in fields if actual[key].get(k) != expected[key].get(k)]}
                   for key in sorted(actual.keys() & expected.keys())]
    differences = [r for r in differences if r['fields']]
    missing, unexpected = sorted(expected.keys() - actual.keys()), sorted(actual.keys() - expected.keys())
    terminal_ok = report['final_state'] == terminal
    verification = {'passed': bool(report['historical_parity_ok'] and terminal_ok and not differences and not missing and not unexpected),
                    'terminal_state_matches_archive': terminal_ok, 'checked_trade_events': len(actual),
                    'event_mismatches': differences, 'missing_events': missing, 'unexpected_events': unexpected}
    write(root / 'historical_verification.json', verification)
    write(root / 'manifest.json', {'files': {p.name: digest(p) for p in root.iterdir() if p.is_file() and p.name != 'manifest.json'},
                                 'protocol_sha256': digest(workspace / 'protocol.json')})
    return verification
