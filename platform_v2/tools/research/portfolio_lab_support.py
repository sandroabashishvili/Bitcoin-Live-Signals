"""Adapters for the *pinned production* Futures simulator, not a new trading engine.

Imported by a standalone worker after its frozen-source loader is installed.
All persistence is private to the experiment. No historical state is injected
after initialization: candidate positions, fees and entry timing evolve freely.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from types import SimpleNamespace


class MemoryRuntimeStore:
    def __init__(self, output):
        self.output = output
        self.families = {}
        self.market_plans = []
        self.candles = {}
        self.metrics = []

    def load_candles(self, *, symbol, timeframe):
        return self.candles[timeframe]

    def load_family_rows_all(self, *, family_name):
        if family_name == 'futures_market_plans':
            return self.market_plans
        return [row for date, row in self.families.get(family_name, [])]

    def load_family_rows(self, *, family_name, date_iso):
        return [row for date, row in self.families.get(family_name, []) if date == date_iso]

    def append_daily_row(self, *, family_name, date_iso, row):
        self.families.setdefault(family_name, []).append((date_iso, copy.deepcopy(row)))

    def upsert_daily_row(self, *, family_name, date_iso, row, match_keys):
        rows = self.families.setdefault(family_name, [])
        for index, (date, prior) in enumerate(rows):
            if date == date_iso and all(prior.get(k) == row.get(k) for k in match_keys):
                rows[index] = (date_iso, copy.deepcopy(row))
                return
        self.append_daily_row(family_name=family_name, date_iso=date_iso, row=row)

    def store_metrics(self, *, metrics, date_iso):
        self.metrics.append(copy.deepcopy(metrics))
        return self.output / 'replay.sqlite3'


def flatten_read(blob, manifest):
    values = []
    for ref in manifest['chunks']:
        values.extend(blob(ref))
    if len(values) != 1:
        raise ValueError('Expected one captured read result')
    return values[0]


def captured_reads(blob, refs):
    """Latest captured read per semantic identity; return no live fallback."""
    reads = {}
    for ref in refs:
        manifest = blob(ref)
        identity = manifest.get('identity', [])
        if len(identity) == 2:
            reads[tuple(identity)] = manifest
    return reads


def required_read(blob, reads, operation, **filters):
    matches = []
    for (op, arguments), manifest in reads.items():
        if op == operation:
            args = json.loads(arguments)
            if all(args.get(k) == v for k, v in filters.items()):
                matches.append(manifest)
    if len(matches) != 1:
        raise ValueError('Missing/ambiguous captured read: ' + operation + ' ' + str(filters))
    return flatten_read(blob, matches[0])


def compare_fields(actual, expected, fields):
    return [key for key in fields if actual.get(key) != expected.get(key)]


class PortfolioReplay:
    def __init__(self, *, output, blob, database, protocol, model, baseline):
        from platform_v2.futures.config import load_execution_profile
        from platform_v2.futures.services.simulation.directional_futures_simulation_service import DirectionalFuturesSimulationService
        self.profile = load_execution_profile()
        if self.profile.mode != 'simulation':
            raise ValueError('Only simulation profiles are allowed')
        self.output, self.blob, self.database, self.protocol = output, blob, database, protocol
        self.model, self.baseline = model, baseline
        self.store = MemoryRuntimeStore(output)
        self.engine = DirectionalFuturesSimulationService()
        self.state = None
        self.initial_state = None
        self.cycles, self.mismatches, self.prestate_mismatches = [], [], []
        self.model_missing_quotes = []
        self.clock = 0
        self.indicator = {}
        self._install_adapters()

    def _install_adapters(self):
        from platform_v2.futures.services.simulation import metrics_service, state_store, common
        from platform_v2.futures.services.simulation import directional_futures_simulation_service as simulation
        from platform_v2.futures.services.simulation.entry_permission_context_service import FuturesEntryPermissionContextService
        from platform_v2.futures.services.simulation.entry_event_writer_service import FuturesEntryEventWriterService
        from platform_v2.futures.services.simulation.position_lifecycle_service import FuturesPositionLifecycleService
        from platform_v2.futures.services.simulation.metrics_service import FuturesMetricsService
        production_state = state_store.FuturesSimulationStateStore
        state = SimpleNamespace(load=lambda: self.state, save=lambda value: None,
                                open_positions=production_state.open_positions,
                                set_open_positions=production_state.set_open_positions)
        self.engine._state_store = state
        self.engine._runtime_store = self.store
        self.engine._metrics_service = FuturesMetricsService(runtime_store=self.store)
        self.engine._entry_permission_context_service = FuturesEntryPermissionContextService(runtime_store=self.store)
        self.engine._entry_permission_context_service._latest_indicator_snapshot = lambda **kw: self.indicator
        self.engine._position_lifecycle_service = FuturesPositionLifecycleService(
            runtime_store=self.store, state_store=state, position_service=self.engine._position_service)
        self.engine._entry_event_writer_service = FuturesEntryEventWriterService(
            runtime_store=self.store, state_store=state, position_service=self.engine._position_service)
        for module in (metrics_service, state_store, common, simulation):
            module.utc_now_ms = lambda: self.clock
        replay = self

        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls.fromtimestamp(replay.clock / 1000, tz=UTC)
                return value.astimezone(tz) if tz else value.replace(tzinfo=None)
        metrics_service.datetime = FrozenDatetime

    def step(self, *, observation_id, evidence, manifests, context, tail):
        from platform_v2.shared.backend.market import MarketQuote
        record = evidence['record']
        if record.get('symbol') != self.profile.symbol or record.get('timeframe') != self.profile.timeframe or record.get('leverage') != self.profile.leverage:
            raise ValueError('Recorded execution profile differs from frozen defaults')
        t = record['timestamp_ms']
        reads = captured_reads(self.blob, evidence['input_refs'])
        expected_state = required_read(self.blob, reads, 'futures_resolved_engine_state')
        if self.state is None:
            self.state = copy.deepcopy(expected_state)
            self.initial_state = copy.deepcopy(expected_state)
            prior = required_read(self.blob, reads, 'sqlite_read_gate.py:read_family_rows', family='futures_signals', system='futures')
            self.store.families['futures_signals'] = [(datetime.fromtimestamp(r['timestamp_ms'] / 1000, UTC).date().isoformat(), copy.deepcopy(r)) for r in prior if r['timestamp_ms'] < t]
            # This is inherited accounting, not an evaluation of pre-period outcomes.
            inherited_ids = {r['position_id'] for r in self.state['open_positions']}
            rows = self.database.execute("SELECT date_iso,payload_json FROM runtime_rows WHERE system='futures' AND family='futures_position_events' AND timestamp_ms<? ORDER BY timestamp_ms,ordinal", (t,))
            self.store.families['futures_position_events'] = []
            for date, text in rows:
                row = json.loads(text)
                if row.get('event') == 'CLOSED' and row.get('position_id') not in inherited_ids:
                    self.store.families['futures_position_events'].append((date, row))
            self.seed_counts = {k: len(v) for k, v in self.store.families.items()}
        elif self.baseline and self.model == 'observed' and self.state != expected_state:
            fields = compare_fields(self.state, expected_state, sorted(set(self.state) | set(expected_state)))
            self.prestate_mismatches.append({'observation_id': observation_id, 'fields': fields,
                'actual': {k: copy.deepcopy(self.state.get(k)) for k in fields},
                'expected': {k: expected_state.get(k) for k in fields}})
        symbol, timeframe = self.profile.symbol, self.profile.timeframe
        self.clock = int(datetime.fromisoformat(record['decision_time'].replace('Z', '+00:00')).timestamp() * 1000)
        for tf in (timeframe, '1m'):
            manifest = manifests[('binance', 'crypto', 'futures', 'candles', symbol, tf)]
            # Full available candle history is required to resolve carried positions
            # and profit-lock activation. Do not use just the indicator warmup tail.
            self.store.candles[tf] = [r for r in tail(manifest, manifest['count']) if int(r['close_time']) <= self.clock + 999]
        from platform_v2.futures.services.analytics.market_plan.service import FuturesMarketPlanService
        snapshots = {tf: tail(manifests[('binance', 'crypto', 'futures', 'indicators', symbol, tf)], 1)[-1]
                     for tf in ('5m', '15m', '4h')}
        for snapshot in snapshots.values():
            event_time = snapshot.get('timestamp_ms') or snapshot.get('close_time_ms')
            if not isinstance(event_time, int) or event_time > self.clock + 999:
                raise ValueError('Missing timestamp or future permission indicator')
        self.indicator = snapshots[timeframe]
        planner = FuturesMarketPlanService()
        planner._latest_snapshot = lambda **kw: snapshots[kw['timeframe']]
        plan = planner.build_plan(date_iso=datetime.fromtimestamp(self.clock / 1000, UTC).date().isoformat(), symbol=symbol, timeframe=timeframe)
        if not plan or plan['timestamp_ms'] > t:
            raise ValueError('Missing or future regenerated market plan')
        self.store.market_plans = [plan]
        self.engine._market_context_service = SimpleNamespace(build_context=lambda **kw: context)
        quote_price, quote_time, quote_source = record.get('execution_quote_price'), record.get('execution_quote_time_ms'), record.get('execution_quote_source')
        if self.model == 'next-minute':
            available = max(evidence['available_ms'], self.clock + 999, quote_time or 0)
            entry = (available // 60000 + 1) * 60000
            row = self.price_database.execute("SELECT payload_json FROM market_observations WHERE venue='binance' AND market_type='futures' AND dataset='candles' AND symbol=? AND timeframe='1m' AND event_time_ms=? AND event_time_ms+60000<=?", (symbol, entry, self.protocol['end_ms'])).fetchall()
            if len(row) != 1:
                quote_price = None
                self.model_missing_quotes.append(observation_id)
            else:
                candle = json.loads(row[0][0])
                if candle['timestamp'] != entry or candle['close_time'] != entry + 59999:
                    raise ValueError('Invalid execution model candle')
                quote_price, quote_time, quote_source = float(candle['open']), entry, 'research_next_1m_open'
                if not math.isfinite(quote_price) or quote_price <= 0:
                    raise ValueError('Invalid modeled quote price')
                self.clock = entry
        quote = None if quote_price is None else MarketQuote(symbol=symbol, market_type='futures', price=quote_price,
                                                            observed_at_ms=quote_time, source=quote_source)
        if quote and (not math.isfinite(quote.price) or quote.price <= 0 or not isinstance(quote_time, int)):
            raise ValueError('Invalid captured execution quote')
        # No fabricated quote in observed mode. Candidate comparisons use a
        # separately declared uniform next-minute model for both variants.
        self.engine._execution_quote = lambda **kw: (None, None) if kw['signal_side'] not in ('LONG', 'SHORT') else (quote, None if quote else 'historical_quote_missing')
        date = datetime.fromtimestamp(self.clock / 1000, UTC).date().isoformat()
        before = copy.deepcopy(self.state)
        start_events = len(self.store.families.get('futures_position_events', []))
        summary = self.engine.run(profile=self.profile, date_iso=date)
        actual = self.store.load_family_rows_all(family_name='futures_signals')[-1]
        signal_keys = ('direction_scores', 'direction_component_scores', 'direction_gates', 'selected_direction', 'mtf_signals', 'mtf_direction')
        keys = signal_keys + (('permission_status', 'permission_reason', 'permission_checks', 'entry_quality', 'market_plan_permission', 'entry_location_permission', 'execution_quote_price', 'execution_quote_time_ms') if self.model == 'observed' else ())
        differences = compare_fields(actual, record, keys) if self.baseline else []
        if differences:
            self.mismatches.append({'observation_id': observation_id, 'fields': differences,
                'actual': {k: actual.get(k) for k in differences}, 'expected': {k: record.get(k) for k in differences}})
        self.cycles.append({'observation_id': observation_id, 'timestamp_ms': t, 'decision_clock_ms': self.clock,
            'signal': actual['selected_direction'], 'permission_status': actual['permission_status'],
            'permission_reason': actual['permission_reason'], 'summary': {k: v for k, v in dataclasses.asdict(summary).items() if k != 'metrics_path'},
            'stats_before': before['stats'], 'stats_after': copy.deepcopy(self.state['stats']),
            'events': [copy.deepcopy(r) for _, r in self.store.families.get('futures_position_events', [])[start_events:]],
            'open_positions_after': copy.deepcopy(self.state['open_positions'])})

    def finish(self):
        events = [r for _, r in self.store.families.get('futures_position_events', [])[self.seed_counts.get('futures_position_events', 0):]] if self.state else []
        final = self.store.metrics[-1] if self.store.metrics else {}
        stats_delta = {k: round(float(self.state['stats'].get(k, 0)) - float(self.initial_state['stats'].get(k, 0)), 2)
                       for k in self.state['stats'] if isinstance(self.state['stats'][k], (int, float))} if self.state else {}
        parity = not self.mismatches and not self.prestate_mismatches and bool(self.cycles)
        report = {'model': self.model, 'historical_parity_ok': parity if self.model == 'observed' else None,
            'signal_parity_ok': not self.mismatches if self.baseline else None,
            'cycles': self.cycles, 'initial_state': self.initial_state, 'final_state': self.state,
            'profile': dataclasses.asdict(self.profile), 'final_metrics': final, 'stats_delta': stats_delta,
            'actions': dict(Counter(r['signal'] for r in self.cycles)),
            'event_counts': dict(Counter(r.get('event') for r in events)),
            'denials': dict(Counter(r['permission_reason'] for r in self.cycles if r['permission_status'] == 'DENIED' and r['signal'] != 'NO_SIGNAL')),
            'mismatches': self.mismatches, 'prestate_mismatches': self.prestate_mismatches,
            'missing_modeled_quotes': self.model_missing_quotes,
            'limitations': ['Captured cycle schedule, not continuous intracycle trading',
                'Production stop-first OHLC ordering; no tick-level fill claim',
                'Market plans regenerated with pinned code; location/plan indicators retained as captured exogenous features',
                'Open positions are not force-closed at sample end',
                'Historical observed mode validates recorded quotes; next-minute mode is a separate execution assumption',
                'Inherited accounting and positions preserved; period changes are reported separately',
                'No independent holdout or automatic promotion']}
        with sqlite3.connect(self.output / 'replay.sqlite3') as db:
            db.execute('CREATE TABLE rows(family TEXT,date_iso TEXT,ordinal INTEGER,payload_json TEXT)')
            db.execute('CREATE TABLE state(name TEXT PRIMARY KEY,payload_json TEXT)')
            db.execute('CREATE TABLE metrics(ordinal INTEGER PRIMARY KEY,payload_json TEXT)')
            for family, rows in self.store.families.items():
                db.executemany('INSERT INTO rows VALUES(?,?,?,?)', [(family, date, i, json.dumps(r, sort_keys=True)) for i, (date, r) in enumerate(rows)])
            db.executemany('INSERT INTO state VALUES(?,?)', [('initial', json.dumps(self.initial_state, sort_keys=True)), ('final', json.dumps(self.state, sort_keys=True))])
            db.executemany('INSERT INTO metrics VALUES(?,?)', [(i, json.dumps(r, sort_keys=True)) for i, r in enumerate(self.store.metrics)])
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Output database integrity failure')
        (self.output / 'portfolio.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
        return report
