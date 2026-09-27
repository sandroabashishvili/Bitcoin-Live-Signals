"""Atomic publication of SIMULATION projections, independent of durable evidence.

Work against a consistent in-memory snapshot; publish its write set plus a unique
cycle receipt in one SQLite transaction. HTTP and evidence writes never hold the
trading writer lock. This is not an exchange-order exactly-once mechanism.
"""
from __future__ import annotations
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import sqlite3

from .ledger import now_ms

STAGED = ContextVar('simulation_projection_stage', default=None)
TABLE_KEYS = {'runtime_documents':(0,1,2), 'runtime_rows':(0,1,2,3), 'runtime_state':(0,1)}


class ConcurrentProjectionChange(RuntimeError):
    pass


class AlreadyCommitted(RuntimeError):
    pass


class BorrowedConnection:
    """Existing store helpers close/commit each operation; only own the local DB."""
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, key):
        return getattr(self.connection, key)

    def close(self):
        pass


def staged_connection(path):
    stage = STAGED.get()
    if stage and Path(path).resolve() == stage.path:
        return BorrowedConnection(stage.memory)
    return None


def committed(path, system, cycle_key):
    path = Path(path)
    if not path.exists():
        return False
    db = sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='execution_cycle_receipts'").fetchone():
            return False
        return bool(db.execute('SELECT 1 FROM execution_cycle_receipts WHERE system=? AND cycle_key=?',
                               (system,cycle_key)).fetchone())
    finally:
        db.close()


class ProjectionStage:
    def __init__(self, path, system, cycle_key, attempt_id, before_commit=None):
        self.path=Path(path).resolve()
        self.system=system
        self.cycle_key=cycle_key
        self.attempt_id=attempt_id
        self.before_commit=before_commit
        self.memory=None
        self.token=None
        self.published=False

    @staticmethod
    def snapshot(db,table):
        indices=TABLE_KEYS[table]
        return {tuple(row[i] for i in indices):tuple(row) for row in db.execute(f'SELECT * FROM {table}')}

    def __enter__(self):
        if STAGED.get() is not None:
            raise RuntimeError('nested projection stage')
        from platform_v2.shared.backend.persistence.sqlite_schema import SCHEMA_SQL, initialize_database
        initialize_database(self.path)
        self.memory=sqlite3.connect(':memory:')
        self.memory.execute('PRAGMA foreign_keys=ON')
        self.memory.executescript(SCHEMA_SQL)
        source=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        try:
            source.execute('BEGIN')
            self.base={table:self.snapshot(source,table) for table in TABLE_KEYS}
            self.columns={table:[r[1] for r in source.execute(f'PRAGMA table_info({table})')] for table in TABLE_KEYS}
            for table,values in self.base.items():
                marks=','.join('?' for _ in self.columns[table])
                self.memory.executemany(f'INSERT INTO {table} VALUES ({marks})',values.values())
            self.memory.commit()
        finally:
            source.close()
        self.token=STAGED.set(self)
        return self

    def publish(self):
        if self.published:
            raise RuntimeError('projection stage already published')
        if self.before_commit:
            self.before_commit() # cycle marker joins the same staged transaction
        target={table:self.snapshot(self.memory,table) for table in TABLE_KEYS}
        changes={table:[key for key in set(self.base[table])|set(target[table])
                        if self.base[table].get(key)!=target[table].get(key)] for table in TABLE_KEYS}
        for keys in changes.values():
            if any(key[0] != self.system for key in keys):
                raise RuntimeError('simulation attempted cross-system projection write')
        db=sqlite3.connect(self.path,timeout=10)
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM execution_cycle_receipts WHERE system=? AND cycle_key=?',
                          (self.system,self.cycle_key)).fetchone():
                raise AlreadyCommitted(self.cycle_key)
            # Validate the system's entire read snapshot as well as the write set.
            # A concurrent capital/config/reset write must not permit a decision
            # based on stale state, even if this cycle would not overwrite that row.
            for table in TABLE_KEYS:
                baseline={k:v for k,v in self.base[table].items() if k[0]==self.system}
                indices=TABLE_KEYS[table]
                current={tuple(row[i] for i in indices):tuple(row) for row in
                         db.execute(f'SELECT * FROM {table} WHERE system=?',(self.system,))}
                if current != baseline:
                    raise ConcurrentProjectionChange(f'{table}: system read snapshot changed')
            # Optimistic conflict detection: no writer's changed rows are overwritten.
            for table,keys in changes.items():
                where=' AND '.join(self.columns[table][i]+'=?' for i in TABLE_KEYS[table])
                for key in keys:
                    current=db.execute(f'SELECT * FROM {table} WHERE {where}',key).fetchone()
                    if current!=self.base[table].get(key):
                        raise ConcurrentProjectionChange(f'{table}:{key}')
            # Avoid parent deletion cascading into unchanged child rows.
            for table in ('runtime_rows','runtime_documents','runtime_state'):
                where=' AND '.join(self.columns[table][i]+'=?' for i in TABLE_KEYS[table])
                for key in changes[table]:
                    if key not in target[table]:
                        db.execute(f'DELETE FROM {table} WHERE {where}',key)
            for table in TABLE_KEYS:
                cols=self.columns[table]
                key_indices=TABLE_KEYS[table]
                conflict=','.join(cols[i] for i in key_indices)
                updates=','.join(f'{col}=excluded.{col}' for i,col in enumerate(cols) if i not in key_indices)
                sql=f"INSERT INTO {table} VALUES ({','.join('?' for _ in cols)}) ON CONFLICT({conflict}) DO UPDATE SET {updates}"
                db.executemany(sql,[target[table][key] for key in changes[table] if key in target[table]])
            digest=hashlib.sha256(json.dumps({t:[target[t].get(k) for k in sorted(changes[t])] for t in TABLE_KEYS},
                                             sort_keys=True,separators=(',',':')).encode()).hexdigest()
            db.execute('INSERT INTO execution_cycle_receipts VALUES (?,?,?,?,?)',
                       (self.system,self.cycle_key,self.attempt_id,now_ms(),digest))
            db.commit()
            self.published=True
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
        STAGED.reset(self.token)
        self.token=None

    def __exit__(self, *error):
        if self.token is not None:
            STAGED.reset(self.token)
            self.token=None
        if self.memory is not None:
            self.memory.close()
