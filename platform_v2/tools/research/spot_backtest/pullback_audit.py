"""Post-hoc diagnostics of frozen pullback decisions, NOT candidate tuning.

Executed by the offline, source-pinned worker. No new signals/trades are emitted.
"""
import bisect
from collections import Counter
from datetime import datetime, timezone
import json
import sqlite3

if __package__:
    from .compare import load, digest
else:
    from comparison_helpers import load, digest


AUDIT_PROTOCOL = {
    'version': 'pullback-audit-v1', 'reference': 'scenario_pullback_v1',
    'purpose': 'Post-hoc observational diagnosis, not a rule change, optimization or validation.',
    'windows': 'Previous 3 bars (excluding current) for historical EMA9 contact; previous 3 close-to-close changes (excluding current) for downside movement.',
    'recross': 'Current close above its EMA9 AND previous close at/below its own EMA9. Not required by original detector.',
    'forward': '1/4/12h from modeled entry minute open to last 1m close within that horizon; require EVERY 1m candle and stay inside the tested segment. Not trade PnL.',
    'groups': 'Existing six vote patterns, each optional vote, close recross, actual prior EMA9 contact, prior down-close and existing breakout overlap; split by existing segment.',
    'examples': 'Earliest two SL and earliest two TP exits per segment, not hand-picked by price outcome.',
    'limitations': 'Groups overlap, votes correlate, samples are selected and small. Losing trade != false signal. No causal gate benefit or new thresholds inferred.'}


def require(value, message):
    if not value:
        raise ValueError(message)


def utc(ms):
    return datetime.fromtimestamp(ms/1000, timezone.utc).isoformat()


def pullback_features(bars, snapshots):
    require(len(bars) >= 5, 'Insufficient diagnostic history')
    c, p = bars[-1], bars[-2]
    s, prev = snapshots[c.close_time_ms], snapshots[p.close_time_ms]
    historical_touch = any(b.low_price <= snapshots[b.close_time_ms].ema9 for b in bars[-4:-1])
    prior_down = any(b.close_price < a.close_price for a,b in zip(bars[-5:-2], bars[-4:-1]))
    return {'no_prior_down_close': not prior_down, 'no_prior_own_ema9_touch': not historical_touch,
        'close_recross_ema9': p.close_price <= prev.ema9 and c.close_price > s.ema9,
        'distance_above_ema9_ATR': (c.close_price-s.ema9)/s.atr,
        'current_range_ATR': (c.high_price-c.low_price)/s.atr,
        'rsi': s.rsi, 'adx': s.adx}


def forward_change(start_ms, entry_price, horizon_hours, segment_end_ms, minute_stamps, minute_prices):
    require(isinstance(horizon_hours,int) and horizon_hours>0, 'Invalid horizon')
    target = start_ms+horizon_hours*3600000-1
    if target > segment_end_ms:
        return None
    first = bisect.bisect_left(minute_stamps, start_ms+59999)
    end = bisect.bisect_right(minute_stamps, target)
    expected = horizon_hours*60
    tail = minute_stamps[first:end]
    if len(tail) != expected or tail[0] != start_ms+59999 or tail[-1] != target:
        return None
    if any(b-a != 60000 for a,b in zip(tail, tail[1:])):
        return None
    require(entry_price > 0, 'Invalid entry reference')
    return 100*(minute_prices[target]/entry_price-1)


def aggregate(records):
    closed = [r for r in records if r['status'] == 'CLOSED']
    forward = {}
    for hours in (1,4,12):
        values = [r['forward_close_change_pct'][str(hours)+'h'] for r in records
            if r['forward_close_change_pct'][str(hours)+'h'] is not None]
        forward[str(hours)+'h'] = {'covered':len(values), 'excluded':len(records)-len(values),
            'positive':sum(v>0 for v in values), 'mean_pct':sum(values)/len(values) if values else None}
    return {'positions':len(records), 'closed':len(closed), 'open':len(records)-len(closed),
        'closed_net_USDT':round(sum(r['net_pnl'] for r in closed),4),
        'net_positive_closed':sum(r['net_pnl']>0 for r in closed),
        'exit_reasons':dict(Counter(r['exit_reason'] for r in closed)), 'forward_NOT_trade_PnL':forward}


def run(root, output):
    from platform_v2.spot.infrastructure.market_data.candle_repository import JsonCandleRepository
    from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import JsonIndicatorSnapshotRepository
    from platform_v2.spot.services.analytics.indicator_snapshot_builder import IndicatorSnapshotBuilder
    run_protocol = json.loads((output/'candidate_protocol.json').read_text())
    require(run_protocol['reference_manifest_sha256'] == digest(root/'runs/scenario_pullback_v1/manifest.json'), 'Audit reference changed after sealing')
    result, cycles = load(root, 'scenario_pullback_v1')
    with sqlite3.connect((root/'market.sqlite3').as_uri()+'?mode=ro&immutable=1', uri=True) as db:
        raw = [json.loads(row[0]) for row in db.execute("SELECT payload FROM candles WHERE tf='15m' ORDER BY stamp")]
        bars = [JsonCandleRepository._parse_candle_row('BTCUSDT','15m',row) for row in raw]
        minutes = {stamp:json.loads(payload)['close'] for stamp,payload in db.execute("SELECT close_ms,payload FROM candles WHERE tf='1m'")}
    require(all(b is not None for b in bars), 'Native candle parser rejected audit input')
    stamps = [b.close_time_ms for b in bars];minute_stamps = sorted(minutes)
    snapshots = {};start = 0
    for index in range(len(bars)+1):
        if index<len(bars) and (index==0 or stamps[index] == stamps[index-1]+900000):
            continue
        group = bars[start:index];start = index
        if len(group)<200:
            continue
        for row in IndicatorSnapshotBuilder().build_rows(symbol='BTCUSDT',timeframe='15m',candles=group):
            stamp = int(datetime.fromisoformat(row['datetime']).replace(tzinfo=timezone.utc).timestamp()*1000)+999
            snapshots[stamp] = JsonIndicatorSnapshotRepository._parse_snapshot_row(symbol='BTCUSDT',timeframe='15m',row=row)
    by_quote = {(c['segment'],c['quote_ms']):c for c in cycles}
    features = {}
    buys = [c for c in cycles if c['signal']['side']=='BUY']
    require(bool(buys), 'No BUY observations to audit')
    for cycle in buys:
        stamp = cycle['timestamp_ms'];end = bisect.bisect_right(stamps,stamp)
        require(snapshots[stamp] is not None and snapshots[stamp].price == cycle['signal']['snapshot_price'], 'Recomputed reference differs')
        features[stamp] = pullback_features(bars[max(0,end-22):end], snapshots)
    positions = []
    segment_info = []
    for seg in result['segments']:
        number = seg['segment']
        # Last exit scan at the final decision's quote time minus one millisecond.
        segment_end = seg['last_signal_close_ms']+60000
        segment_info.append({'segment':number, 'start_utc':utc(seg['start_ms']),
            'last_signal_close_utc':utc(seg['last_signal_close_ms']), 'last_exit_scan_utc':utc(segment_end),
            'initial_balance_USDT':seg['initial_balance_USDT'], 'final_account':seg['final_account']})
        for p in seg['positions']:
            cycle = by_quote[(number,p['opened_at_ms'])]
            require(cycle['signal']['side']=='BUY', 'Position without original BUY')
            stamp = cycle['timestamp_ms'];gates = cycle['candidate']['votes']
            forward = {str(hours)+'h':forward_change(p['opened_at_ms'],p['execution']['entry_price'],hours,
                segment_end,minute_stamps,minutes) for hours in (1,4,12)}
            positions.append({'segment':number, 'position_id':p['position_id'], 'signal_close_utc':utc(stamp),
                'entry_utc':utc(p['opened_at_ms']), 'status':p['status'], 'exit_reason':p.get('exit_reason'),
                'net_pnl':p.get('net_pnl',0.), 'gates':gates, 'vote_count':sum(gates.values()),
                'setup_confidence':cycle['signal']['setup_confidence'], 'entry_price':p['execution']['entry_price'],
                'overlaps_breakout':cycle['candidate']['detected']['breakout'],
                'features':features[stamp], 'forward_close_change_pct':forward})
    require(len(positions)==result['new_positions'], 'Position join mismatch')
    always = [name for name in ('mtf','regime','trend','momentum','orderbook','structure')
        if all(c['candidate']['votes'][name] for c in buys)]
    segment_reports = {}
    for number in (s['segment'] for s in result['segments']):
        entries = [r for r in positions if r['segment']==number]
        selected_buys = [c for c in buys if c['segment']==number]
        patterns = {}
        for record in entries:
            key = '+'.join(name for name,passed in record['gates'].items() if passed)
            patterns.setdefault(key,[]).append(record)
        groups = {}
        for name in ('mtf','regime','momentum','orderbook'):
            groups[name] = {str(flag):aggregate([r for r in entries if r['gates'][name]==flag]) for flag in (False,True)}
        for name in ('no_prior_down_close','no_prior_own_ema9_touch','close_recross_ema9'):
            groups[name] = {str(flag):aggregate([r for r in entries if r['features'][name]==flag]) for flag in (False,True)}
        groups['overlaps_breakout'] = {str(flag):aggregate([r for r in entries if r['overlaps_breakout']==flag]) for flag in (False,True)}
        segment_reports[str(number)] = {'overall':aggregate(entries),
            'BUY_candle_feature_counts':{name:sum(features[c['timestamp_ms']][name] for c in selected_buys)
                for name in ('no_prior_down_close','no_prior_own_ema9_touch','close_recross_ema9')},
            'BUY_candles':len(selected_buys), 'vote_patterns':{key:aggregate(group) for key,group in patterns.items()},
            'observational_groups':groups,
            'SL_forward_prices':aggregate([r for r in entries if r['exit_reason']=='sl_hit'])}
        examples=[]
        for reason in ('sl_hit','tp_hit'):
            examples.extend([r for r in entries if r['exit_reason']==reason][:2])
        segment_reports[str(number)]['chronological_examples']=examples
    report = {'format':'pullback-audit-v1', 'protocol':AUDIT_PROTOCOL, 'segments':segment_info,
        'cycles':len(cycles), 'BUY_candles':len(buys), 'always_true_gates_on_BUY':always,
        'records':positions, 'segment_diagnostics':segment_reports,
        'interpretation_limits':['This inspects exploratory simulated history already examined, not an independent validation sample.',
            'Net trade loss can arise despite later positive price movement. Forward horizons ignore fees and do NOT represent reopened trades.',
            'Group differences are descriptive, correlated and selected by native execution permissions, not causal gate-ablation results.',
            'Current detector compares previous lows to CURRENT EMA9; historical own-EMA9 contact and close recross are diagnostics, not new requirements.',
            'Trend and structure repeat mandatory pullback conditions; four votes are not four independent confirmations.',
            'No parameter changes, no replay candidate, no deployment.']}
    (output/'audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    lines = ['# Pullback audit: observational, no rule changes', '',
        f"BUY candles: {len(buys)}; positions: {len(positions)}; always-true BUY votes: {', '.join(always)}.", '',
        '## Covered segments (UTC)', '']
    for seg in segment_info:
        lines.append(f"- Segment {seg['segment']}: {seg['start_utc']} to {seg['last_signal_close_utc']}; separate fresh account.")
    lines += ['', '## Closed outcome by existing vote pattern', '',
        '| Segment | Passed votes | Positions | Closed | Open | Closed net USDT |', '|---|---|---:|---:|---:|---:|']
    for number, data in segment_reports.items():
        for key,group in data['vote_patterns'].items():
            lines.append(f"| {number} | {key} | {group['positions']} | {group['closed']} | {group['open']} | {group['closed_net_USDT']:+.4f} |")
    lines += ['', '## Limits', '']+['- '+line for line in report['interpretation_limits']]
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines),flush=True)
