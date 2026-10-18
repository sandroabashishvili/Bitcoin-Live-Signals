"""Run two frozen, matched-start accounts without touching the operational DB.

Usage: python -m ...spot_backtest.paired_accounts MARKET_ROOT EVIDENCE_ROOT NEW_OUTPUT
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from .compare import digest, load
from .paired_support import select_cohort
from .__main__ import run as launch


def read_verified(folder, name, manifest):
    path = folder/name
    if digest(path) != manifest['files'][name]:
        raise ValueError('Evidence changed: '+name)
    return json.loads(path.read_text())


def run(root, evidence, output):
    root, evidence, output = (p.resolve() for p in (root, evidence, output))
    runtime = Path('/home/sandro/SmartSignalHub/platform_v2/runtime')
    if output.is_relative_to(runtime) or output.is_relative_to(root) or output.is_relative_to(evidence):
        raise ValueError('Use a new separate research output directory')
    _, baseline = load(root, 'baseline')
    manifest = json.loads((evidence/'manifest.json').read_text())
    snapshot = read_verified(evidence, 'live_snapshot.json', manifest)
    prior = read_verified(evidence, 'summary.json', manifest)
    records = {str(r['timestamp_ms']):r for r in snapshot['families']['signals']}
    start, end = prior['common_first_signal_ms'], prior['common_last_signal_ms']
    window, common = select_cohort([r['timestamp_ms'] for r in baseline], records, start, end)
    # Check actual initial ledger state rather than asserting an empty live account.
    unique_positions = {r['position_id']:r for r in snapshot['families']['positions']}
    from .reconcile_live import millis
    inherited = [r for r in unique_positions.values() if r['opened_at_ms'] < start and
        (not r.get('closed_at') or millis(r['closed_at']) > start)]
    if inherited:raise ValueError('Operational account had inherited open positions at matched start')
    output.mkdir(parents=True, exist_ok=False)
    for name in ('market.sqlite3', 'protocol.json', 'flow_crosscheck.json'):
        shutil.copyfile(root/name, output/name)
    shutil.copytree(root/'source', output/'source')
    (output/'market.sqlite3').chmod(0o444)
    (output/'recorded_signals.json').write_text(json.dumps(records, sort_keys=True, allow_nan=False)+'\n')
    protocol = {'format':'matched-fresh-spot-accounts-v1',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'start_ms':start,'end_ms':end,'expected_common_cycles':len(common),
        'covered_exit_cycles':len(window),'missing_decisions_skipped_in_both':len(window)-len(common),
        'initial_balance_USDT':3000.,'inherited_live_positions':0,
        'arms':{'baseline':'recomputed','unchanged':'recorded','control_v2':'recomputed'},
        'recorded_signals_sha256':digest(output/'recorded_signals.json'),
        'parent_protocol_sha256':digest(root/'protocol.json'),
        'evidence_manifest_sha256':digest(evidence/'manifest.json'),
        'assumptions':['Same native empty accounts, capital, modeled quotes, exit bars and observation mask.',
            'Only modeled decision path differs; historical decisions retain historical scores/setup, not actual quotes or portfolio.',
            'Historical entry quality is recalculated against each fresh account signal history.',
            'Recorded outputs may have become available after fixed model fill time; retrospective diagnostic, NOT causal tradable replay.',
            'Not a causal ORDERBOOK-only experiment or actual operational PnL reproduction.']}
    (output/'paired_account_protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    shutil.copyfile(Path(__file__), output/'analysis_source.py')
    (output/'preparation_manifest.json').write_text(json.dumps({'files':{
        str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file()}},indent=2)+'\n')
    for arm in protocol['arms']:
        launch(output, arm)
    results = {arm:json.loads((output/'runs'/arm/'results.json').read_text()) for arm in protocol['arms']}
    def cycle_rows(arm):
        return [json.loads(s) for s in (output/'runs'/arm/'cycles.jsonl').read_text().splitlines()]
    raw, recorded, control = (cycle_rows(a) for a in protocol['arms'])
    if results['baseline'] != results['control_v2'] or raw != control:
        raise ValueError('Unchanged recomputed control failed exact parity')
    if [r['timestamp_ms'] for r in raw] != [r['timestamp_ms'] for r in recorded]:
        raise ValueError('Account clock cohorts differ')
    for a,b in zip(raw, recorded):
        if a['quote_ms'] != b['quote_ms'] or bool(a['signal']) != bool(b['signal']):
            raise ValueError('Quote clock or missing-record mask differs')
        if b['signal'] and b['signal']['side'] != records[str(b['timestamp_ms'])]['side']:
            raise ValueError('Recorded decision side changed')
    rows = []
    for arm, result in results.items():
        if len(result['segments']) != 1:raise ValueError('Matched account reset unexpectedly')
        segment = result['segments'][0]
        rows.append({'arm':arm,'mode':protocol['arms'][arm], 'BUY':result['actions'].get('BUY',0),
            'positions':result['new_positions'],'closed':result['closed_positions'],
            'open':segment['open_positions'],'closed_net_USDT':result['closed_net_USDT'],
            'final_equity_USDT':segment['final_account']['equity']})
    paired_cycles = [{'timestamp_ms':a['timestamp_ms'], 'raw_signal':a['signal'],
        'recorded_signal':b['signal'],'raw_permission':a['permission'],
        'recorded_permission':b['permission']} for a,b in zip(raw,recorded)
        if a['signal'] and (a['signal']['side']=='BUY' or b['signal']['side']=='BUY')]
    (output/'decision_comparison.json').write_text(json.dumps(paired_cycles,indent=2)+'\n')
    summary = {'protocol':protocol,'accounts':rows,'exact_recomputed_control_parity':True,
        'operational_reference_NOT_identical_execution':prior['live_entry_cohort']}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines = ['# ერთნაირი საწყისი ანგარიშების დიაგნოსტიკა','',
        'პერიოდი UTC: '+datetime.fromtimestamp(start/1000,timezone.utc).isoformat()+' — '+datetime.fromtimestamp(end/1000,timezone.utc).isoformat(),
        '',f'საერთო გადაწყვეტილებები: {len(common)}; ორივეში გამოტოვებულია {len(window)-len(common)} უცნობი გადაწყვეტილება; დახურვის მართვა არ წყდება.',
        '', '| გზა | BUY | პოზიციები | დახურული | ღია | დახურული net USDT | საბოლოო equity |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['arm']} ({r['mode']}) | {r['BUY']} | {r['positions']} | {r['closed']} | {r['open']} | {r['closed_net_USDT']:+.4f} | {r['final_equity_USDT']:.2f} |")
    lines += ['', 'უცვლელი საკონტროლო გაშვება ზუსტად ემთხვევა ყველა შედეგსა და ციკლს.', '',
        'ორივე მოდელირებულ ანგარიშში საწყისი კაპიტალია 3,000 USDT; ორივე ცარიელია. ინდიკატორების warmup უცვლელია.',
        'ეს არ არის მოქმედი რეესტრის რეპროდუქცია: შენახული სიგნალები აქ გარედან მიწოდებული ისტორიული გადაწყვეტილებებია, ხოლო შესრულება მოდელირებულია.',
        'ორიგინალური გადაწყვეტილება ზოგჯერ მოდელირებულ ფასზე გვიან იყო ცნობილი; ეს დიაგნოსტიკაა და არა შესრულებადი სტრატეგიის backtest.',
        'Entry quality ხელახლა ითვლება ახალი ანგარიშის სიგნალების ისტორიით. ძველი score/confidence/setup შენარჩუნებულია; ამიტომ სხვაობა მხოლოდ ORDERBOOK-ს ვერ მიეწერება.',
        'დეტალური სიგნალები/ნებართვები: decision_comparison.json; ყველა შესვლა/დახურვა: runs/*/results.json.',
        'მოქმედი სისტემა, ბაზები და ძველი ანგარიშები არ შეცვლილა.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    (output/'manifest.json').write_text(json.dumps({'files':{str(p.relative_to(output)):digest(p)
        for p in output.rglob('*') if p.is_file()}},indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__ == '__main__':run(*(Path(p) for p in sys.argv[1:]))
