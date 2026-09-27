"""Additive, append-only SQLite evidence; never edits compatibility projections.

All identifiers are scoped to a recorder epoch. Recovery requires positive evidence
that a former process has exited; age alone is NOT evidence of a crash.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid
import zlib


TABLES = (
    'research_runs', 'cycle_attempt_events', 'decision_observations',
    'market_acquisition_events', 'cycle_gap_events', 'research_input_revisions',
)
TERMINALS = ('COMMITTED', 'FAILED', 'INTERRUPTED', 'ABANDONED')


def now_ms():
    return time.time_ns() // 1_000_000


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Explicit opt-in construction only; no migration on ordinary imports.
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS research_evidence_schema(version INTEGER PRIMARY KEY)')
            db.execute('INSERT OR IGNORE INTO research_evidence_schema VALUES (1)')
            db.execute('INSERT OR IGNORE INTO research_evidence_schema VALUES (2)')
            db.execute('''CREATE TABLE IF NOT EXISTS execution_cycle_receipts (
                system TEXT NOT NULL, cycle_key TEXT NOT NULL, attempt_id TEXT NOT NULL,
                committed_ms INTEGER NOT NULL, write_sha256 TEXT NOT NULL, PRIMARY KEY(system,cycle_key))''')
            db.execute('CREATE TABLE IF NOT EXISTS research_blobs (sha256 TEXT PRIMARY KEY, compressed_json BLOB NOT NULL)')
            for table in TABLES:
                db.execute(f'''CREATE TABLE IF NOT EXISTS {table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL, attempt_id TEXT, system TEXT NOT NULL,
                    cycle_key TEXT, kind TEXT NOT NULL, at_ms INTEGER NOT NULL,
                    payload_json TEXT NOT NULL)''')
                db.execute(f'CREATE INDEX IF NOT EXISTS {table}_attempt ON {table}(attempt_id, kind)')
                db.execute(f'CREATE INDEX IF NOT EXISTS {table}_cycle ON {table}(system, cycle_key, id)')
            db.execute('''CREATE VIEW IF NOT EXISTS research_first_live_decisions AS
                SELECT d.* FROM decision_observations d WHERE d.kind='LIVE_OBSERVED'
                AND d.id=(SELECT min(x.id) FROM decision_observations x
                          WHERE x.system=d.system AND x.cycle_key=d.cycle_key
                            AND x.kind='LIVE_OBSERVED')''')
            db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS research_one_terminal
                ON cycle_attempt_events(attempt_id) WHERE kind IN
                ('COMMITTED','FAILED','INTERRUPTED','ABANDONED')''')
            for table in (*TABLES, 'research_blobs', 'execution_cycle_receipts'):
                for operation in ('UPDATE', 'DELETE'):
                    db.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()}
                        BEFORE {operation} ON {table} BEGIN
                        SELECT RAISE(ABORT, 'research evidence is append-only'); END''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('PRAGMA synchronous=FULL')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _insert(self, db, table, *, run_id, system, kind, payload,
                attempt_id=None, cycle_key=None, event_key=None, at_ms=None):
        if table not in TABLES:
            raise ValueError(table)
        key = event_key or uuid.uuid4().hex
        values = (key, run_id, attempt_id, system, cycle_key, kind,
                  now_ms() if at_ms is None else at_ms, canonical(payload))
        existing = db.execute(f'SELECT * FROM {table} WHERE event_key=?', (key,)).fetchone()
        if existing:
            # Retry of the same event is idempotent, reuse with different content is not.
            if tuple(existing[k] for k in ('run_id','attempt_id','system','cycle_key','kind','payload_json')) != (
                run_id, attempt_id, system, cycle_key, kind, values[-1]):
                raise ValueError('event key reused with different evidence')
            return key
        db.execute(f'''INSERT INTO {table}(event_key,run_id,attempt_id,system,
            cycle_key,kind,at_ms,payload_json) VALUES (?,?,?,?,?,?,?,?)''', values)
        return key

    def append(self, table, **kwargs):
        with self.connection() as db:
            return self._insert(db, table, **kwargs)

    def blobs(self, values):
        prepared = []
        for value in values:
            data = canonical(value).encode()
            prepared.append((hashlib.sha256(data).hexdigest(), zlib.compress(data)))
        with self.connection() as db:
            db.executemany('INSERT OR IGNORE INTO research_blobs VALUES (?,?)', prepared)
        return [digest for digest, _ in prepared]

    def blob(self, value):
        return self.blobs([value])[0]

    def load_blob(self, digest):
        with self.connection() as db:
            row = db.execute('SELECT compressed_json FROM research_blobs WHERE sha256=?', (digest,)).fetchone()
        if row is None:
            raise ValueError('missing input revision: ' + digest)
        data = zlib.decompress(row[0])
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('input revision hash mismatch')
        return json.loads(data)

    def start(self, *, run_id, system, symbol, timeframe, started_ms=None, period_ms=900000):
        start = now_ms() if started_ms is None else started_ms
        boundary = start // period_ms * period_ms
        cycle = f'{symbol}:{timeframe}:{boundary-1}'
        attempt = uuid.uuid4().hex
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('''SELECT attempt_id FROM cycle_attempt_events
                WHERE system=? AND cycle_key=? AND kind='STARTED' ORDER BY id DESC''', (system,cycle)).fetchall()
            self._insert(db, 'cycle_attempt_events', run_id=run_id, system=system,
                attempt_id=attempt, cycle_key=cycle, kind='STARTED', event_key=attempt+':STARTED', at_ms=start,
                payload={'expected_due_ms': boundary+60000, 'candle_close_ms': boundary-1,
                         'actual_start_ms': start, 'attempt_sequence': len(previous)+1,
                         'retry_of': previous[0][0] if previous else None,
                         'schedule_delay_ms': 60000, 'late_budget_ms': 120000,
                         'timeliness': 'LATE' if start > boundary+180000 else 'ON_TIME',
                         'identity_basis': 'wall_clock_expected_slot', 'period_ms': period_ms})
        return attempt, cycle

    def terminal(self, *, run_id, system, attempt_id, cycle_key, kind, payload=None):
        if kind not in TERMINALS:
            raise ValueError(kind)
        return self.append('cycle_attempt_events', run_id=run_id, system=system,
            attempt_id=attempt_id, cycle_key=cycle_key, kind=kind,
            payload=payload or {}, event_key=attempt_id+':'+kind)

    def recover(self, *, dead_run_id, recovery_run_id, system, evidence):
        if not evidence or evidence.get('process_exit_confirmed') is not True:
            raise ValueError('recovery requires confirmed process exit, not age')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute('''SELECT s.* FROM cycle_attempt_events s
                WHERE s.kind='STARTED' AND s.run_id=? AND s.system=? AND NOT EXISTS
                (SELECT 1 FROM cycle_attempt_events t WHERE t.attempt_id=s.attempt_id
                 AND t.kind IN ('COMMITTED','FAILED','INTERRUPTED','ABANDONED'))''', (dead_run_id,system)).fetchall()
            for row in rows:
                self._insert(db, 'cycle_attempt_events', run_id=dead_run_id, system=system,
                    attempt_id=row['attempt_id'], cycle_key=row['cycle_key'], kind='ABANDONED',
                    event_key=row['attempt_id']+':ABANDONED',
                    payload={'recovered_by': recovery_run_id, 'exit_evidence': evidence,
                             'side_effects': 'UNKNOWN_REQUIRES_RECONCILIATION'})
        return len(rows)

    def detect_gaps(self, *, run_id, system, symbol, timeframe, activation_close_ms,
                    through_close_ms, period_ms=900000):
        """Append missing-decision slots only within an explicitly enabled epoch."""
        if activation_close_ms % period_ms != period_ms-1 or through_close_ms % period_ms != period_ms-1:
            raise ValueError('expected candle CLOSE milliseconds')
        found = 0
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for close in range(activation_close_ms, through_close_ms+1, period_ms):
                cycle = f'{symbol}:{timeframe}:{close}'
                observed = db.execute('''SELECT 1 FROM decision_observations
                    WHERE system=? AND cycle_key=? AND kind='LIVE_OBSERVED' LIMIT 1''', (system,cycle)).fetchone()
                if observed:
                    continue
                key = f'gap:{system}:{cycle}:{activation_close_ms}'
                existed = db.execute('SELECT 1 FROM cycle_gap_events WHERE event_key=?', (key,)).fetchone()
                if not existed:
                    self._insert(db,'cycle_gap_events',run_id=run_id,system=system,
                        cycle_key=cycle,kind='DETECTED',event_key=key,
                        payload={'reason':'UNKNOWN','expected_close_ms':close,
                                 'activation_close_ms':activation_close_ms})
                    found += 1
        return found

    def decision(self, *, run_id, system, attempt_id, cycle_key, payload, input_refs,
                 origin='LIVE_OBSERVED', event_key=None, available_ms=None, evidence_complete=True):
        if origin not in ('LIVE_OBSERVED','RESEARCH_RECONSTRUCTED'):
            raise ValueError(origin)
        for ref in input_refs:
            self.load_blob(ref)
        available = now_ms() if available_ms is None else available_ms
        close = int(cycle_key.rsplit(':',1)[1])
        return self.append('decision_observations',run_id=run_id,system=system,
            attempt_id=attempt_id,cycle_key=cycle_key,kind=origin,event_key=event_key,at_ms=available,
            payload={'record':payload,'input_refs':input_refs,'available_ms':available,
                     'timeliness':'LATE' if available > close+180001 else 'ON_TIME',
                     'evidence_complete':bool(input_refs) and evidence_complete,
                     'capture_stage':'before_compatibility_projection_write'})
