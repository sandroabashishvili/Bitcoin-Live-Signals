"""Read-only ledger relationships and accounting checks on one SQLite snapshot."""

from collections import Counter, defaultdict
from contextlib import closing
import json
from math import isfinite
from pathlib import Path
import sqlite3

from platform_v2.shared.backend.persistence import DEFAULT_DATABASE_PATH
from platform_v2.tools.diagnostics.core.models import add_finding


def sqlite_accounting_findings(db_path: Path = DEFAULT_DATABASE_PATH):
    if not db_path.exists():
        return []  # Missing/unreadable databases are handled by sqlite_runtime_checks.
    findings = []
    families = defaultdict(list)
    try:
        with closing(sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            connection.execute('BEGIN')
            for system, family, day, ordinal, raw in connection.execute(
                'SELECT system, family, date_iso, ordinal, payload_json FROM runtime_rows '
                'ORDER BY date_iso, ordinal'
            ):
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    families[system, family].append((day, payload))
            for system, key, raw in connection.execute(
                "SELECT system, state_key, payload_json FROM runtime_state WHERE state_key='simulation_engine'"
            ):
                families[system, key].append(('', json.loads(raw)))
    except (sqlite3.Error, ValueError, TypeError) as exc:
        add_finding(findings, str(db_path), 'sqlite_accounting_unreadable', str(exc), 'high')
        return findings
    return check_ledgers(families, source=str(db_path))


def check_ledgers(families, *, source):
    """Pure checks: repeated daily position snapshots are NOT duplicate trades."""
    findings = []

    def issue(code, detail, severity='high'):
        add_finding(findings, source, code, detail, severity)

    def rows(system, family):
        return [row for _, row in families.get((system, family), [])]

    def compare(label, actual, expected, tolerance=0.021):
        if not _number(actual) or not _number(expected):
            issue('accounting_missing_value', f'{label}: actual={actual}, expected={expected}')
        elif abs(float(actual) - float(expected)) > tolerance:
            issue('accounting_value_mismatch', f'{label}: actual={actual}, expected={expected}')

    positions_by_system = {}
    for system, prefix, position_family in (
        ('spot', '', 'positions'), ('futures', 'futures_', 'futures_position_events')
    ):
        signals = rows(system, prefix + 'signals')
        keys = [(r.get('symbol'), r.get('timeframe'), r.get('timestamp_ms')) for r in signals]
        for key, count in Counter(keys).items():
            if key[2] is None:
                issue('signal_identity_missing', f'{system}: symbol/timeframe/timestamp={key}')
            elif count > 1:
                issue('duplicate_signal_decision', f'{system}: {key}, count={count}')
        history = rows(system, position_family)
        latest = {r['position_id']: r for r in history if r.get('position_id')}
        positions_by_system[system] = latest
        # Spot snapshots can legitimately recur on different days. Futures events
        # can legitimately update the same position several times in one day.
        if system == 'spot':
            identities = [(day, r.get('position_id')) for day, r in families.get((system, position_family), [])]
        else:
            identities = [(r.get('position_id'), r.get('event'), r.get('timestamp_ms')) for r in history]
        for key, count in Counter(identities).items():
            if count > 1:
                issue('duplicate_position_record', f'{system}: {key}, count={count}')
        for pid, position in latest.items():
            status = position.get('status')
            if status == 'CLOSED' and any(position.get(key) in (None, '', 'unknown') for key in ('closed_at', 'exit_price', 'exit_reason')):
                issue('closed_position_missing_exit', f'{system}: {pid}')
            if status == 'OPEN' and (position.get('closed_at') or position.get('exit_price') is not None):
                issue('open_position_has_exit', f'{system}: {pid}')
            if status not in {'OPEN', 'CLOSED'}:
                issue('position_status_invalid', f'{system}: {pid}, status={status}')
            if status == 'CLOSED' and system == 'futures':
                compare(f'{system}/{pid}/net_pnl', position.get('net_pnl'),
                        _subtract(position.get('gross_pnl'), position.get('fees_paid')))
                compare(f'{system}/{pid}/fees_paid', position.get('fees_paid'),
                        _sum_required(position.get('entry_fee_paid'), position.get('exit_fee_paid')))
        orders = [r for r in rows(system, prefix + 'orders') if r.get('status') == 'FILLED']
        order_ids = [r.get('position_id') if system == 'futures' else r.get('exchange_order_id') for r in orders]
        for identity, count in Counter(order_ids).items():
            if identity and count > 1:
                issue('duplicate_filled_order', f'{system}: {identity}, count={count}')
        for order in orders:
            if system == 'futures':
                matches = [latest[order['position_id']]] if order.get('position_id') in latest else []
            else:
                request, fill = order.get('request') or {}, order.get('fill') or {}
                matches = [p for p in latest.values() if p.get('opened_at_ms') is not None
                           and p.get('opened_at_ms') == fill.get('filled_at_ms')
                           and p.get('symbol') == request.get('symbol')]
            if len(matches) != 1:
                issue('filled_order_position_link', f'{system}: order={order.get("exchange_order_id") or order.get("position_id")}, matches={len(matches)}')
        for pid, position in latest.items():
            if system == 'futures':
                linked = [r for r in orders if r.get('position_id') == pid]
            else:
                linked = [r for r in orders if (r.get('fill') or {}).get('filled_at_ms') == position.get('opened_at_ms')
                          and (r.get('request') or {}).get('symbol') == position.get('symbol')]
            if len(linked) != 1:
                issue('position_order_link', f'{system}: position={pid}, filled_orders={len(linked)}')
        metrics_rows = rows(system, prefix + 'metrics')
        if not metrics_rows:
            if history or signals:
                issue('accounting_metrics_missing', system)
            continue
        metrics = metrics_rows[-1]
        compare(f'{system}/force_close_count', metrics.get('force_close_events'),
                len(rows(system, prefix + 'force_closes')), tolerance=0)
        if system == 'futures':
            audits = rows(system, 'futures_trade_entry_audits')
            audit_ids = [r.get('position_id') for r in audits]
            compare('futures/closed_trade_audit_count', metrics.get('closed_positions'), len(set(audit_ids)), tolerance=0)
            for pid, count in Counter(audit_ids).items():
                if pid is None or count > 1:
                    issue('futures_trade_audit_identity', f'position_id={pid}, count={count}')
        opened = [p for p in latest.values() if p.get('status') == 'OPEN']
        closed = [p for p in latest.values() if p.get('status') == 'CLOSED']
        for key, expected in [('total_positions', len(latest)), ('open_positions', len(opened)), ('closed_positions', len(closed))]:
            compare(f'{system}/{key}', metrics.get(key), expected, tolerance=0)
        net = _sum_field(closed, 'net_pnl')
        compare(f'{system}/total_net_pnl', metrics.get('total_net_pnl'), net)
        compare(f'{system}/capital_identity', metrics.get('equity'),
                _sum_required(metrics.get('available_balance'), metrics.get('reserved_capital'), metrics.get('unrealized_pnl')))
        if system == 'spot':
            compare('spot/gross_pnl', metrics.get('gross_pnl'), _sum_field(closed, 'pnl'))
        # No hard-coded fee rate: the recorded fees and net/gross difference
        # define the open fee debit, allowing historical fee policies to differ.
        gross = _sum_field(closed, 'pnl' if system == 'spot' else 'gross_pnl')
        if _number(gross) and _number(net) and _number(metrics.get('fees_paid')):
            if system == 'futures':
                compare('futures/closed_fees', metrics.get('fees_paid'), gross - net)
                states = rows(system, 'simulation_engine')
                state = states[-1] if states else {}
                state_open = state.get('open_positions', [])
                if isinstance(state_open, dict):
                    state_open = list(state_open.values())
                if not state_open and state.get('open_position'):
                    state_open = [state['open_position']]
                open_fees = _sum_field(state_open, 'entry_fee_paid')
                if {p.get('position_id') for p in state_open} != {p.get('position_id') for p in opened}:
                    issue('futures_open_state_mismatch', 'engine state and latest position events disagree')
            else:
                open_fees = float(metrics['fees_paid']) - (gross - net)
            if open_fees is None:
                issue('accounting_missing_value', f'{system}: open entry fees')
                continue
            if open_fees < -0.021:
                issue('accounting_negative_open_fees', f'{system}: {open_fees}')
            compare(f'{system}/capital_from_pnl', metrics.get('equity'),
                    _sum_required(metrics.get('starting_capital'), net, metrics.get('unrealized_pnl'), -open_fees))

    entries, resets = rows('hedge', 'hedge_entries'), rows('hedge', 'hedge_reset_events')
    for family_rows, key in [(entries, 'hedge_entry_id'), (resets, 'reset_id')]:
        for identity, count in Counter(r.get(key) for r in family_rows).items():
            if identity is None or count > 1:
                issue('hedge_identity_error', f'{key}={identity}, count={count}')
    for identity, count in Counter(entry.get('source_position_id') for entry in entries).items():
        if identity is None or count > 1:
            issue('hedge_source_identity_error', f'source_position_id={identity}, count={count}')
    for entry in entries:
        if entry.get('source_position_id') not in positions_by_system.get('futures', {}):
            issue('hedge_source_position_missing', str(entry.get('hedge_entry_id')))
    summaries = rows('hedge', 'hedge_daily_summaries')
    future_metrics = rows('futures', 'futures_metrics')
    if future_metrics:
        compare('futures_to_hedge_entries', future_metrics[-1].get('trades_opened_since_start'), len(entries), tolerance=0)
    if summaries:
        summary = summaries[-1]
        compare('hedge/entry_count', summary.get('hedge_entries_accepted'), len(entries), tolerance=0)
        compare('hedge/reset_count', summary.get('reset_count'), len(resets), tolerance=0)
        compare('hedge/equity', summary.get('equity_usdt'),
                _sum_required(summary.get('cash_usdt'), summary.get('unrealized_pnl_usdt')))
        compare('hedge/available', summary.get('available_capital_usdt'),
                _subtract(summary.get('equity_usdt'), summary.get('used_margin_usdt')))
        compare('hedge/fees', summary.get('total_fees_usdt'),
                _sum_required(_sum_field(entries, 'entry_fee_usdt'), _sum_field(resets, 'exit_fees_usdt')))
        compare('hedge/realized', summary.get('realized_pnl_usdt'), _sum_field(resets, 'net_pnl'))
    return findings


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _sum_required(*values):
    return sum(values) if all(_number(value) for value in values) else None


def _sum_field(rows, key):
    return _sum_required(*(row.get(key) for row in rows))


def _subtract(left, right):
    return left - right if _number(left) and _number(right) else None
