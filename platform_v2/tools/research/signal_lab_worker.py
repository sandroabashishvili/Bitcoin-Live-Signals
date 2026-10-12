"""Standalone stdlib bootstrap: imports only frozen project source."""
import dataclasses
import functools
import gzip
import hashlib
import importlib.util
import json
import sqlite3
import sys
import zlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


def main():
    root, name, limit, component = Path(sys.argv[1]).resolve(), sys.argv[2], int(sys.argv[3]), sys.argv[4]
    model = sys.argv[5] if len(sys.argv) > 5 else None
    out = root / 'portfolio_runs' / sys.argv[6] if model else root / 'runs' / name
    protocol = json.loads((root / 'protocol.json').read_text())
    raw = gzip.decompress((root / 'source/source.json.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest() != protocol['source_sha256']:
        raise ValueError('source hash mismatch')
    payload = json.loads(raw)
    paths = {'scores': 'platform_v2/futures/services/signal/futures_component_score_service.py',
             'mtf': 'platform_v2/futures/services/signal/futures_mtf_context_service.py'}
    overlays = {}
    if name != 'baseline':
        for key, path in paths.items():
            code = (out / (key + '.py')).read_text()
            compile(code, path, 'exec')
            payload['files'][path] = code
            overlays[key] = hashlib.sha256(code.encode()).hexdigest()
    # Relocate __file__-derived runtime paths away from production.
    payload['project_root'] = str(root / 'isolated_project')
    spec = importlib.util.spec_from_file_location('frozen_loader', root / 'source/run.py')
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    sys.meta_path.insert(0, loader.PinnedSource(payload))
    sys.dont_write_bytecode = True

    def guard(event, args):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            raise PermissionError('Research worker cannot use network or spawn processes')
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = Path(args[0]).resolve()
            live_runtime = Path('/home/sandro/SmartSignalHub/platform_v2/runtime')
            if path.is_relative_to(live_runtime):
                raise PermissionError('Live runtime access denied')
            mode, flags = args[1], args[2]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & 3 != 0)
            if writing and not path.is_relative_to(out):
                raise PermissionError('Write outside experiment denied: ' + str(path))
        mutations = {'os.remove': (0,), 'os.rmdir': (0,), 'os.mkdir': (0,), 'os.chmod': (0,),
                     'os.rename': (0, 1), 'os.link': (0, 1), 'os.symlink': (1,)}
        if event in mutations:
            for index in mutations[event]:
                if not isinstance(args[index], (str, bytes)) or not Path(args[index]).resolve().is_relative_to(out):
                    raise PermissionError('Filesystem mutation outside experiment denied')
        if event == 'sqlite3.connect':
            frozen = str(args[0]).startswith((root / 'data').as_uri() + '/') and 'mode=ro' in str(args[0])
            output_database = model and Path(str(args[0])).resolve() == out / 'replay.sqlite3'
            if not frozen and not output_database:
                raise PermissionError('Only frozen read-only databases allowed')
    sys.addaudithook(guard)
    from platform_v2.futures.services.signal.futures_market_context_service import FuturesMarketContextService
    from platform_v2.futures.services.signal.futures_signal_decision_service import SignalDecisionService
    from platform_v2.futures.infrastructure.market_data.candle_repository import JsonCandleRepository
    from platform_v2.futures.domain.models.orderbook_snapshot import OrderbookSnapshot

    db = sqlite3.connect((root / 'data/trading.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True)

    @functools.lru_cache(maxsize=256)
    def blob(sha):
        row = db.execute('SELECT compressed_json FROM research_blobs WHERE sha256=?', (sha,)).fetchone()
        if row is None:
            raise ValueError('missing evidence blob')
        data = zlib.decompress(row[0])
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError('evidence hash mismatch')
        return json.loads(data)

    def tail(manifest, count):
        rows = []
        for ref in reversed(manifest['chunks']):
            rows = blob(ref) + rows
            if len(rows) >= count:
                break
        return rows

    context_service, decision_service = FuturesMarketContextService(), SignalDecisionService()
    portfolio = None
    if model:
        from portfolio_lab_support import PortfolioReplay
        portfolio = PortfolioReplay(output=out, blob=blob, database=db, protocol=protocol, model=model, baseline=name == 'baseline')
        portfolio.price_database = sqlite3.connect((root / 'data/market.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True)
    results, exclusions, mismatches = [], [], []
    rows = db.execute("SELECT id,payload_json FROM research_first_live_decisions WHERE system='futures' ORDER BY id")
    keys = ('direction_scores', 'direction_component_scores', 'direction_gates', 'mtf_signals', 'mtf_direction', 'selected_direction')
    for oid, text in rows:
        evidence = json.loads(text)
        record = evidence.get('record') or {}
        t = record.get('timestamp_ms', 0)
        if not protocol['start_ms'] <= t < protocol['end_ms']:
            continue
        if evidence.get('timeliness') != 'ON_TIME' or not evidence.get('evidence_complete'):
            if model:
                if not evidence.get('evidence_complete') or evidence.get('timeliness') not in ('ON_TIME', 'LATE'):
                    raise ValueError('Incomplete cycle cannot be skipped in a stateful replay')
            else:
                exclusions.append(oid)
                continue
        if limit and len(results) >= limit:
            break
        manifests = {}
        for ref in evidence['input_refs']:
            item = blob(ref)
            identity = item.get('identity', [])
            if len(identity) == 6:
                manifests[tuple(identity)] = item
        symbol, tf = record.get('symbol', 'BTCUSDT'), record.get('timeframe', '15m')
        cutoff = int(datetime.fromisoformat(record['decision_time'].replace('Z', '+00:00')).timestamp() * 1000) + 999
        candles = {}
        for timeframe in ('5m', '15m', '4h'):
            manifest = manifests[('binance', 'crypto', 'futures', 'candles', symbol, timeframe)]
            candles[timeframe] = [JsonCandleRepository._parse_candle_row(symbol=symbol, timeframe=timeframe, row=r)
                                  for r in tail(manifest, 256) if int(r['close_time']) <= cutoff][-240:]
        context_service._candle_repository = SimpleNamespace(get_closed_candles=lambda **kw: candles[kw['timeframe']][-kw['limit']:])
        order_manifest = manifests.get(('binance', 'crypto', 'futures', 'orderflow', symbol, tf))
        orderbook = None
        if order_manifest:
            r = tail(order_manifest, 1)[-1]
            orderbook = OrderbookSnapshot(symbol=symbol, timeframe=tf,
                timestamp_text=str(r.get('timestamp_text') or r.get('datetime') or ''),
                buyers=float(r.get('buyers', 0) or 0), sellers=float(r.get('sellers', 0) or 0),
                dominance_ratio=float(r.get('dominance_ratio', 0) or 0), imbalance=float(r.get('imbalance', 0) or 0),
                momentum_classification=str(r.get('momentum_classification') or r.get('classification') or 'neutral'),
                period_count=int(r.get('period_count', 0) or 0), source=str(r.get('source') or 'binance_futures_aggtrades'))
        context_service._orderbook_repository = SimpleNamespace(get_latest_snapshot=lambda **kw: orderbook)
        context = context_service.build_context(symbol=symbol, timeframe=tf)
        if context is None:
            raise ValueError('Cannot reconstruct context: ' + str(oid))
        decision = dataclasses.asdict(decision_service.build_signal(context, timestamp_ms=t))
        result = {'observation_id': oid, 'timestamp_ms': t, 'available_ms': max(evidence['available_ms'], cutoff, record.get('execution_quote_time_ms') or 0),
                  **{k: decision[k] for k in keys}}
        different = [k for k in keys if decision[k] != record.get(k)]
        if name == 'baseline' and different:
            mismatches.append({'observation_id': oid, 'fields': different, 'expected': {k: record.get(k) for k in different},
                               'actual': {k: decision[k] for k in different}})
        results.append(result)
        if portfolio:
            portfolio.step(observation_id=oid, evidence=evidence, manifests=manifests, context=context, tail=tail)
        if len(results) % 100 == 0:
            print('Replayed', len(results), flush=True)
    if not results:
        raise ValueError('No eligible decisions')
    if name != 'baseline':
        baseline_path = root / ('portfolio_runs/baseline-next-minute/result.json' if model else 'runs/baseline/result.json')
        baseline = json.loads(baseline_path.read_text())['decisions']
        if [r['observation_id'] for r in results] != [r['observation_id'] for r in baseline]:
            raise ValueError('Candidate cohort differs from baseline')
        for a, b in zip(results, baseline):
            for direction in ('long', 'short'):
                for key, value in a['direction_component_scores'][direction].items():
                    if key != component and value != b['direction_component_scores'][direction][key]:
                        raise ValueError('Undeclared component changed: ' + key)
    report = {'parity_ok': not mismatches, 'limit': limit, 'component': component or None,
              'overlays': overlays, 'decisions': results, 'excluded_observations': exclusions,
              'mismatches': mismatches, 'actions': dict(Counter(r['selected_direction'] for r in results))}
    (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    if portfolio:
        full_report = portfolio.finish()
        print('Portfolio:', len(full_report['cycles']), 'historical parity:', full_report['historical_parity_ok'],
              'period stats:', full_report['stats_delta'], flush=True)
        if model == 'observed' and not full_report['historical_parity_ok']:
            return 2
    print('Replay:', len(results), 'parity:', report['parity_ok'], 'actions:', report['actions'], flush=True)
    if mismatches:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
