"""Immutable first-decision, one-component weight screening (research only).

Not a trade replay: forward price returns do not include costs, permissions,
positions or TP/SL. No live data mutation, indicator rebuild or promotion.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics

MINUTE = 60_000
STEP = 900_000
COMPONENTS = ('mtf', 'momentum', 'regime', 'trend', 'orderbook', 'structure')
LIVE = Path('/home/sandro/SmartSignalHub/platform_v2/runtime/database')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def choose(scores, thresholds):
    ls, ss = scores['long'], scores['short']
    la, sa = ls >= thresholds['long'], ss >= thresholds['short']
    return 'LONG' if la and (not sa or ls >= ss) else 'SHORT' if sa and ss > ls else 'NO_SIGNAL'


def changed_scores(record, direction=None, component=None, factor=None):
    scores = dict(record['direction_scores'])
    if direction is not None:
        raw = Decimal(str(record['direction_component_scores'][direction][component]))
        weight = Decimal(str(record['direction_component_weights'][direction][component]))
        value = Decimal(str(scores[direction])) + raw * weight * (Decimal(str(factor)) - 1)
        scores[direction] = float(value.quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN))
    return scores


def next_minute(available):
    return (available // MINUTE + 1) * MINUTE


def summarize(values):
    return {'n': len(values), 'mean_pct': statistics.mean(values) if values else None,
            'median_pct': statistics.median(values) if values else None,
            'positive_rate_pct': 100 * sum(v > 0 for v in values) / len(values) if values else None}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(protocol, out):
    archive = Path(protocol['archive']).resolve()
    if archive.is_relative_to(LIVE) or not archive.is_file() or archive.stat().st_mode & 0o222:
        raise ValueError('Only a retained read-only archive may supply decisions')
    manifest = json.loads((archive.parent / 'manifest.json').read_text())
    with sqlite3.connect(archive.as_uri() + '?mode=ro', uri=True) as db:
        source = db.execute("SELECT id,cycle_key,payload_json FROM research_first_live_decisions WHERE system='futures' ORDER BY id").fetchall()
        eligible, excluded, seen = [], [], set()
        reference_cache = {}
        for oid, cycle, payload in source:
            observation = json.loads(payload)
            r = observation.get('record') or {}
            t = r.get('timestamp_ms')
            if not isinstance(t, int) or t < protocol['start_candle_close_ms']:
                continue
            reasons = []
            if t in seen: raise ValueError('duplicate first decision timestamp')
            seen.add(t)
            if (t + 1) % STEP: reasons.append('off_grid')
            if observation.get('timeliness') != 'ON_TIME': reasons.append('not_on_time')
            if observation.get('evidence_complete') is not True: reasons.append('incomplete_evidence')
            refs = observation.get('input_refs') or []
            if not refs: reasons.append('no_input_refs')
            for ref in refs:
                if ref not in reference_cache:
                    reference_cache[ref] = db.execute('SELECT 1 FROM research_blobs WHERE sha256=?', (ref,)).fetchone() is not None
                if not reference_cache[ref]: reasons.append('missing_input_blob'); break
            try:
                available = max(int(observation['available_ms']),
                    int(datetime.fromisoformat(r['decision_time'].replace('Z', '+00:00')).timestamp() * 1000) + 999,
                    int(r.get('execution_quote_time_ms') or 0))
                if available < t: reasons.append('availability_before_candle')
                for d in ('long', 'short'):
                    raw, weights = r['direction_component_scores'][d], r['direction_component_weights'][d]
                    if not all(finite(raw[c]) and finite(weights[c]) for c in COMPONENTS): reasons.append('bad_components')
                    if not finite(r['direction_scores'][d]) or not finite(r['direction_thresholds'][d]): reasons.append('bad_scores')
                    if not all(isinstance(r['direction_gates'][d][c], bool) for c in COMPONENTS): reasons.append('bad_gates')
                    if abs(round(sum(raw[c]*weights[c] for c in COMPONENTS), 2) - r['direction_scores'][d]) > .011: reasons.append('score_parity')
                if choose(r['direction_scores'], r['direction_thresholds']) != (r.get('selected_direction') or r.get('side')): reasons.append('choice_parity')
            except (KeyError, TypeError, ValueError, OverflowError):
                available = None
                reasons.append('missing_lineage')
            if reasons:
                excluded.append({'observation_id': oid, 'cycle': cycle, 'reasons': sorted(set(reasons))})
            else:
                eligible.append({'observation_id': oid, 'cycle': cycle, 'available_ms': available,
                                 'entry_ms': next_minute(available), 'record': r})
    if not eligible: raise ValueError('no eligible observations')
    # Freeze decision metadata and the split before reading any price outcomes.
    split = (min(r['available_ms'] for r in eligible) + max(r['available_ms'] for r in eligible)) // 2
    dump(out / 'decisions.json', eligible)
    dump(out / 'exclusions.json', excluded)
    dump(out / 'cohort.json', {'eligible': len(eligible), 'excluded': len(excluded),
         'exclusion_counts': dict(Counter(reason for row in excluded for reason in row['reasons'])),
         'split_ms': split, 'archive_sha256_recorded': manifest['archive_sha256'],
         'archive_hash_note': 'Recorded verified archive identity; source is read-only. Full blob contents not individually decoded in this screen.',
         'first_available_ms': min(r['available_ms'] for r in eligible),
         'last_available_ms': max(r['available_ms'] for r in eligible)})
    return eligible, split


def evaluate(protocol, eligible, split, prices):
    variants = [('baseline', None, None, None)] + [(f'{d}_{c}_x{factor}', d, c, factor)
        for c in protocol['components'] for d in protocol['directions'] for factor in protocol['relative_weight_factors']]
    available, missing = {}, {}
    for h in protocol['horizons_minutes']:
        labeled, counts = [], Counter()
        for r in eligible:
            start, end = r['entry_ms'], r['entry_ms'] + h * MINUTE
            half = 'first' if r['available_ms'] < split else 'second'
            if half == 'first' and end + MINUTE > split:
                counts['purged_midpoint'] += 1; continue
            if start not in prices: counts['missing_start'] += 1; continue
            if end not in prices: counts['missing_endpoint'] += 1; continue
            labeled.append((r, half, (prices[end] / prices[start] - 1) * 100))
        available[h], missing[h] = labeled, dict(counts)
    results, choices = {}, {}
    baseline = [choose(r['record']['direction_scores'], r['record']['direction_thresholds']) for r in eligible]
    for name, d, c, factor in variants:
        selections = {r['observation_id']: choose(changed_scores(r['record'], d, c, factor), r['record']['direction_thresholds']) for r in eligible}
        counts = Counter(selections.values())
        choices[name] = {'actions': dict(counts), 'changed_from_baseline': sum(selections[r['observation_id']] != b for r, b in zip(eligible, baseline))}
        results[name] = {}
        for direction in ('LONG', 'SHORT'):
            results[name][direction] = {}
            for h, labels in available.items():
                results[name][direction][str(h)] = {
                    half: summarize([ret * (-1 if direction == 'SHORT' else 1) for r, part, ret in labels
                                     if selections[r['observation_id']] == direction and (half == 'all' or part == half)])
                    for half in ('all', 'first', 'second')}
    gates = {}
    for direction in ('long', 'short'):
        gates[direction] = {}
        for c in protocol['components']:
            gates[direction][c] = {str(h): {state: summarize([ret * (-1 if direction == 'short' else 1)
                 for r, part, ret in labels if r['record']['direction_gates'][direction][c] == (state == 'passed')])
                 for state in ('passed', 'failed')} for h, labels in available.items()}
    leads = {}
    for name, _, _, _ in variants[1:]:
        leads[name] = {}
        for direction in ('LONG', 'SHORT'):
            improved = []
            for h in protocol['horizons_minutes']:
                candidate, base = results[name][direction][str(h)], results['baseline'][direction][str(h)]
                enough = all(candidate[p]['n'] >= (30 if p == 'all' else 10) and base[p]['n'] >= (30 if p == 'all' else 10) for p in ('all','first','second'))
                if enough and all(candidate[p]['mean_pct'] > base[p]['mean_pct'] for p in ('all','first','second')): improved.append(h)
            leads[name][direction] = {'qualifies_for_replay_screen_only': len(improved) >= 2, 'improved_horizons': improved}
    return {'results': results, 'actions': choices, 'gate_pass_fail': gates,
            'replay_screen_leads': leads, 'label_availability': {str(h): {'usable_decisions': len(v), 'excluded': missing[h]} for h,v in available.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--market-db', type=Path, default=LIVE / 'smartsignalhub_market_data.sqlite3')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.is_relative_to(LIVE.parent): raise ValueError('Output cannot be inside live runtime')
    out.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(args.protocol.read_text())
    if protocol['components'] != list(COMPONENTS) or protocol['relative_weight_factors'] != [0,.5,1.5]: raise ValueError('unexpected screen scope')
    dump(out / 'protocol.json', protocol)
    dump(out / 'run_metadata.json', {'started_utc': datetime.now(UTC).isoformat(), 'protocol_sha256': sha(args.protocol),
         'source_module_sha256': sha(Path(__file__)), 'scope': 'exploration only', 'status': 'STARTED'})
    eligible, split = prepare(protocol, out)
    cutoff = int(datetime.fromisoformat(protocol['price_freeze_end_utc']).timestamp()*1000)
    with sqlite3.connect(args.market_db.resolve().as_uri()+'?mode=ro', uri=True) as db:
        db.execute('BEGIN')
        points = db.execute("SELECT event_time_ms,payload_json FROM market_observations WHERE venue='binance' AND market_type='futures' AND dataset='candles' AND symbol='BTCUSDT' AND timeframe='1m' AND event_time_ms>=? AND event_time_ms+60000<=? ORDER BY event_time_ms,ordinal", (min(r['entry_ms'] for r in eligible), cutoff)).fetchall()
        prices = {}
        for t, payload in points:
            candle = json.loads(payload)
            value = float(candle['open'])
            if candle.get('timestamp') != t or candle.get('close_time') != t + MINUTE - 1 or not math.isfinite(value) or value <= 0: raise ValueError('invalid candle')
            if t in prices: raise ValueError('duplicate minute price')
            prices[t] = value
    dump(out / 'frozen_price_labels_input.json', prices)
    report = evaluate(protocol, eligible, split, prices)
    dump(out / 'screen_results.json', report)
    dump(out / 'completion_manifest.json', {'completed_utc': datetime.now(UTC).isoformat(), 'status': 'SCREEN_COMPLETED',
         'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()},
         'limitations': ['No fee/TP-SL/portfolio execution model', 'Exploratory reused period, not independent validation',
                        'Referenced inputs exist; features were not independently reconstructed from all blob contents',
                        'Overlapping labels/decisions and 36 comparisons are not independent evidence',
                        'Existing indicator formulas and raw gate flags are unchanged; this tests weights only']})
    print('Screen complete:', out)
    print('Eligible first decisions:', len(eligible), 'Baseline actions:', report['actions']['baseline'])
    for name, contexts in report['replay_screen_leads'].items():
        for direction, item in contexts.items():
            if item['qualifies_for_replay_screen_only']:
                print('REPLAY SCREEN LEAD (not promotion):', name, direction, item['improved_horizons'])


if __name__ == '__main__':
    main()
