from collections import defaultdict
from copy import deepcopy
import json
import sqlite3

from platform_v2.tools.diagnostics.checks.sqlite_accounting_checks import check_ledgers, sqlite_accounting_findings


def clean_ledger():
    families = defaultdict(list)
    def add(system, family, row):
        families[system, family].append(('2026-10-26', row))
    position = {'position_id': 'S1', 'symbol': 'BTCUSDT', 'opened_at_ms': 1000, 'status': 'CLOSED',
                'closed_at': 2000, 'exit_price': 110, 'exit_reason': 'tp_hit', 'pnl': 1.1, 'net_pnl': 1.0}
    add('spot', 'positions', position)
    add('spot', 'signals', {'symbol': 'BTCUSDT', 'timeframe': '15m', 'timestamp_ms': 1})
    add('spot', 'orders', {'exchange_order_id': 'O1', 'status': 'FILLED', 'request': {'symbol': 'BTCUSDT'}, 'fill': {'filled_at_ms': 1000}})
    add('spot', 'metrics', {'total_positions': 1, 'open_positions': 0, 'closed_positions': 1,
        'total_net_pnl': 1., 'gross_pnl': 1.1, 'fees_paid': .1, 'starting_capital': 3000.,
        'available_balance': 3001., 'reserved_capital': 0., 'unrealized_pnl': 0., 'equity': 3001., 'force_close_events': 0})
    return families


def issues(families):
    return {item.issue for item in check_ledgers(families, source='test')}


def test_clean_ledger_and_repeated_daily_snapshot_are_not_duplicates():
    ledger = clean_ledger()
    ledger['spot', 'positions'].append(('2026-10-27', deepcopy(ledger['spot', 'positions'][0][1])))
    assert check_ledgers(ledger, source='test') == []


def test_decisions_use_symbol_and_timeframe_not_only_timestamp():
    ledger = clean_ledger()
    ledger['spot', 'signals'].append(('2026-10-26', {'symbol': 'ETHUSDT', 'timeframe': '15m', 'timestamp_ms': 1}))
    assert 'duplicate_signal_decision' not in issues(ledger)
    ledger['spot', 'signals'].append(ledger['spot', 'signals'][0])
    assert 'duplicate_signal_decision' in issues(ledger)


def test_missing_exit_and_orphan_order_are_reported():
    ledger = clean_ledger()
    ledger['spot', 'positions'][0][1]['closed_at'] = None
    ledger['spot', 'orders'][0][1]['fill']['filled_at_ms'] = 999
    assert {'closed_position_missing_exit', 'filled_order_position_link'} <= issues(ledger)


def test_corrupt_money_missing_and_nonfinite_values_are_not_zero():
    for value in (999., None, float('nan')):
        ledger = clean_ledger()
        ledger['spot', 'metrics'][0][1]['equity'] = value
        assert issues(ledger) & {'accounting_missing_value', 'accounting_value_mismatch'}


def test_futures_updates_are_not_new_trades_and_closed_fees_exclude_open_fees():
    ledger = defaultdict(list)
    def add(family, payload):
        ledger['futures', family].append(('2026-10-26', payload))
    add('futures_position_events', {'position_id': 'F1', 'event': 'OPENED', 'timestamp_ms': 1, 'status': 'OPEN'})
    add('futures_position_events', {'position_id': 'F1', 'event': 'POSITION_UPDATE', 'timestamp_ms': 2, 'status': 'OPEN'})
    add('futures_orders', {'position_id': 'F1', 'status': 'FILLED'})
    add('simulation_engine', {'open_positions': [{'position_id': 'F1', 'entry_fee_paid': .25}]})
    add('futures_metrics', {'total_positions': 1, 'open_positions': 1, 'closed_positions': 0,
        'total_net_pnl': 0., 'fees_paid': 0., 'starting_capital': 3000., 'available_balance': 2899.75,
        'reserved_capital': 100., 'unrealized_pnl': 0., 'equity': 2999.75, 'force_close_events': 0, 'trades_opened_since_start': 1})
    ledger['hedge', 'hedge_entries'].append(('2026-10-26', {'hedge_entry_id': 'H1', 'source_position_id': 'F1'}))
    assert check_ledgers(ledger, source='test') == []
    ledger['futures', 'futures_position_events'].append(ledger['futures', 'futures_position_events'][-1])
    assert 'duplicate_position_record' in issues(ledger)


def test_hedge_requires_source_and_unique_entries():
    ledger = clean_ledger()
    entry = ('2026-10-26', {'hedge_entry_id': 'H1', 'source_position_id': 'missing'})
    ledger['hedge', 'hedge_entries'] = [entry, entry]
    assert {'hedge_identity_error', 'hedge_source_position_missing'} <= issues(ledger)


def test_cross_system_checks_live_only_in_diagnostics():
    ledger = clean_ledger()
    ledger['spot', 'metrics'][0][1]['force_close_events'] = 3
    findings = check_ledgers(ledger, source='test')
    assert any('spot/force_close_count' in item.detail for item in findings)
    ledger['futures', 'futures_metrics'].append(('2026-10-26', {'closed_positions': 2, 'trades_opened_since_start': 5}))
    findings = check_ledgers(ledger, source='test')
    assert any('futures/closed_trade_audit_count' in item.detail for item in findings)
    assert any('futures_to_hedge_entries' in item.detail for item in findings)


def test_sqlite_scan_is_read_only_and_does_not_create_missing_database(tmp_path):
    database = tmp_path / 'test.sqlite3'
    assert sqlite_accounting_findings(database) == []
    assert not database.exists()
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE runtime_rows(system, family, date_iso, ordinal, payload_json)')
        connection.execute('CREATE TABLE runtime_state(system, state_key, payload_json)')
        for (system, family), rows in clean_ledger().items():
            connection.executemany('INSERT INTO runtime_rows VALUES (?, ?, ?, ?, ?)',
                [(system, family, day, ordinal, json.dumps(row)) for ordinal, (day, row) in enumerate(rows)])
    before = database.read_bytes()
    assert sqlite_accounting_findings(database) == []
    assert database.read_bytes() == before
