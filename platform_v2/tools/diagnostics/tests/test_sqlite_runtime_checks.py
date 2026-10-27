"""SQLite-primary diagnostics must not depend on optional JSON exports."""

from contextlib import ExitStack
import json
import sqlite3
from unittest.mock import patch

from platform_v2.tools.diagnostics.checks import sqlite_runtime_checks as checks
from platform_v2.tools.diagnostics import orchestrator
from platform_v2.tools.diagnostics.core.models import FileFinding


def test_missing_databases_report_all_three_without_creating_files(tmp_path):
    with ExitStack() as stack:
        for name in ('DEFAULT_DATABASE_PATH', 'MARKET_DATA_DATABASE_PATH', 'CONTENT_DATABASE_PATH'):
            stack.enter_context(patch.object(checks, name, tmp_path / (name + '.sqlite3')))
        stack.enter_context(patch.object(checks, 'iter_runtime_documents', return_value=iter(())))
        findings = checks.sqlite_runtime_parity_findings()
    assert len(findings) == 3
    assert all(item.issue == 'sqlite_runtime_database_missing' and item.severity == 'high' for item in findings)
    assert list(tmp_path.iterdir()) == []


def test_sqlite_rows_checked_without_json_exports(tmp_path):
    database = tmp_path / 'trading.sqlite3'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE runtime_rows(system, family, date_iso, ordinal, payload_json)')
        connection.executemany('INSERT INTO runtime_rows VALUES (?, ?, ?, ?, ?)', [
            ('spot', 'signals', '2026-10-26', 0, json.dumps({'side': 'BUY'})),
            ('futures', 'signals', '2026-10-26', 1, '{broken'),
            ('hedge', 'hedge_entries', '2026-10-26', 2, '[]'),
        ])
    with patch.object(checks, 'DEFAULT_DATABASE_PATH', database):
        findings = checks._sqlite_record_schema_findings()
    assert len(findings) == 3
    assert {item.issue for item in findings} == {'runtime_schema_error', 'runtime_json_decode_error'}


def test_current_nested_order_denial_and_cycle_shapes_are_valid(tmp_path):
    database = tmp_path / 'trading.sqlite3'
    cycle = {'date': '2026-10-26', 'datetime': '2026-10-26 00:00:00', 'cycle_key': 'BTC:15m:1', 'cycle_state': 'ready', 'status': 'ok'}
    rows = [
        ('spot', 'orders', {'request': {}, 'status': 'FILLED', 'fill': {}, 'exchange_order_id': 'paper:1', 'rejection_reason': None}),
        ('spot', 'denied_entries', {'signal': {}, 'permission': {}, 'live_entry_price': 100, 'denial_reason': 'blocked'}),
        ('spot', 'cycle_runs', cycle),
        ('futures', 'futures_cycle_runs', cycle),
    ]
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE runtime_rows(system, family, date_iso, ordinal, payload_json)')
        connection.executemany('INSERT INTO runtime_rows VALUES (?, ?, ?, ?, ?)', [
            (system, family, '2026-10-26', 0, json.dumps(payload)) for system, family, payload in rows
        ])
    with patch.object(checks, 'DEFAULT_DATABASE_PATH', database):
        assert checks._sqlite_record_schema_findings() == []


def test_corrupt_existing_database_is_reported(tmp_path):
    database = tmp_path / 'broken.sqlite3'
    database.write_bytes(b'not a SQLite database')
    def read_status():
        with sqlite3.connect(database) as connection:
            connection.execute('SELECT * FROM runtime_documents')
    with ExitStack() as stack:
        stack.enter_context(patch.object(checks, 'DEFAULT_DATABASE_PATH', database))
        stack.enter_context(patch.object(checks, 'MARKET_DATA_DATABASE_PATH', tmp_path / 'missing-market'))
        stack.enter_context(patch.object(checks, 'CONTENT_DATABASE_PATH', tmp_path / 'missing-content'))
        stack.enter_context(patch.object(checks, 'database_status', side_effect=read_status))
        stack.enter_context(patch.object(checks, 'iter_runtime_documents', return_value=iter(())))
        findings = checks.sqlite_runtime_parity_findings()
    assert sum(item.issue == 'sqlite_database_unreadable' for item in findings) == 1
    assert sum(item.issue == 'sqlite_runtime_database_missing' for item in findings) == 2


def test_diagnostics_exit_status_reflects_high_findings(tmp_path):
    for severity, expected in [('high', 1), ('medium', 0)]:
        with ExitStack() as stack:
            for name in vars(orchestrator):
                if name.endswith('_findings') and name not in {'summarize_findings'}:
                    stack.enter_context(patch.object(orchestrator, name, return_value=[]))
            stack.enter_context(patch.object(orchestrator, 'repo_python_files', return_value=[]))
            stack.enter_context(patch.object(orchestrator, 'sqlite_runtime_parity_findings', return_value=[FileFinding('db', 'test', 'detail', severity)]))
            stack.enter_context(patch.object(orchestrator, 'write_report_files', return_value=(tmp_path / 'a/b/c/d/report.json', tmp_path / 'a/b/c/d/report.md')))
            assert orchestrator.run() == expected
