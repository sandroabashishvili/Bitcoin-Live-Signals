"""Futures runtime diagnostics checks."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    CYCLE_RUNS_FAMILY,
    DAILY_SUMMARIES_FAMILY,
    DENIED_ENTRIES_FAMILY,
    ENTRY_TIMING_SUMMARIES_FAMILY,
    MARKET_PLANS_FAMILY,
    daily_json_path,
    METRICS_FAMILY,
    ORDERS_FAMILY,
    POSITION_EVENTS_FAMILY,
    POSITIONS_FAMILY,
    SIGNALS_FAMILY,
    TRADE_AUDIT_REPORTS_FAMILY,
    TRADE_ENTRY_AUDITS_FAMILY,
    load_family_rows,
    load_family_rows_all,
    runtime_root,
)
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


_RUNTIME_ROOT = runtime_root()
_RUNTIME_DATA = _RUNTIME_ROOT / "data"
_PATH_PREFIX = "platform_v2/runtime/futures"
_FAMILIES: tuple[str, ...] = (
    "candles_futures",
    "orderflow_futures",
    SIGNALS_FAMILY,
    POSITION_EVENTS_FAMILY,
    ORDERS_FAMILY,
    METRICS_FAMILY,
    DENIED_ENTRIES_FAMILY,
    TRADE_ENTRY_AUDITS_FAMILY,
    ENTRY_TIMING_SUMMARIES_FAMILY,
    TRADE_AUDIT_REPORTS_FAMILY,
    MARKET_PLANS_FAMILY,
    CYCLE_RUNS_FAMILY,
    DAILY_SUMMARIES_FAMILY,
)
_LIST_FAMILIES: tuple[str, ...] = (
    SIGNALS_FAMILY,
    POSITION_EVENTS_FAMILY,
    ORDERS_FAMILY,
    DENIED_ENTRIES_FAMILY,
    TRADE_ENTRY_AUDITS_FAMILY,
    MARKET_PLANS_FAMILY,
    CYCLE_RUNS_FAMILY,
)
_DICT_FAMILIES: tuple[str, ...] = (
    METRICS_FAMILY,
    DAILY_SUMMARIES_FAMILY,
    ENTRY_TIMING_SUMMARIES_FAMILY,
    TRADE_AUDIT_REPORTS_FAMILY,
)

_SIGNAL_REQUIRED_KEYS: tuple[str, ...] = (
    "timestamp_ms",
    "symbol",
    "timeframe",
    "side",
    "score",
    "threshold",
    "gates",
)
_POSITION_REQUIRED_KEYS: tuple[str, ...] = (
    "position_id",
    "symbol",
    "side",
    "status",
    "opened_at",
)
_POSITION_EVENT_REQUIRED_KEYS: tuple[str, ...] = (
    "position_id",
    "symbol",
    "side",
    "status",
    "event",
    "timestamp_ms",
)
_ORDER_REQUIRED_KEYS: tuple[str, ...] = (
    "timestamp_ms",
    "symbol",
    "timeframe",
    "status",
    "side",
)
_DENIED_REQUIRED_KEYS: tuple[str, ...] = (
    "timestamp_ms",
    "symbol",
    "timeframe",
    "reason",
)
_TRADE_ENTRY_AUDIT_REQUIRED_KEYS: tuple[str, ...] = (
    "position_id",
    "side",
    "outcome",
    "entry_timing_type",
)
_ENTRY_TIMING_SUMMARY_REQUIRED_KEYS: tuple[str, ...] = (
    "date",
    "total_trades",
    "by_timing",
    "by_side_timing",
)
_TRADE_AUDIT_REPORT_REQUIRED_KEYS: tuple[str, ...] = (
    "date",
    "window_start",
    "window_end",
    "sample_size",
    "sample_status",
)
_MARKET_PLAN_REQUIRED_KEYS: tuple[str, ...] = (
    "date",
    "timestamp_ms",
    "symbol",
    "timeframe",
    "bias",
    "current_price",
)
_CYCLE_REQUIRED_KEYS: tuple[str, ...] = (
    "date",
    "datetime",
    "status",
    "signal_side",
    "score",
    "threshold",
)
_METRICS_REQUIRED_KEYS: tuple[str, ...] = (
    "date",
    "datetime",
    "equity",
    "starting_capital",
    "total_net_pnl",
    "open_positions",
    "closed_positions",
    "total_positions",
    "tp_hits",
    "sl_hits",
    "force_close_events",
)
_SUMMARY_REQUIRED_KEYS: tuple[str, ...] = (
    "date",
    "datetime",
    "total_cycles",
    "ok_cycles",
    "skipped_cycles",
    "buy_signals",
    "no_signal_cycles",
    "opened_orders",
    "denied_entries",
)


def futures_runtime_structure_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    if not _RUNTIME_DATA.exists():
        # Runtime business data is SQLite-primary; a JSON tree is optional.
        return findings

    for family in _FAMILIES:
        family_path = _RUNTIME_DATA / family
        if not family_path.exists():
            continue

        expected_prefix = f"{family}_"
        for json_path in sorted(family_path.glob("*.json")):
            if not json_path.name.startswith(expected_prefix):
                add_finding(
                    findings,
                    _path_str(json_path),
                    "runtime_file_naming_drift",
                    f"expected prefix {expected_prefix}",
                    "low",
                )

    return findings


def futures_runtime_schema_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    if not _RUNTIME_DATA.exists():
        return findings

    for family in _FAMILIES:
        family_path = _RUNTIME_DATA / family
        if not family_path.exists():
            continue
        for json_path in sorted(family_path.rglob("*.json")):
            payload = _load_json(json_path)
            if payload is None:
                add_finding(findings, _path_str(json_path), "runtime_json_decode_error", "could not decode json", "high")
                continue

            if family in _LIST_FAMILIES:
                if not isinstance(payload, list):
                    add_finding(findings, _path_str(json_path), "runtime_schema_error", f"{family} file must be a list", "high")
                    continue
                for index, row in enumerate(payload):
                    _check_list_row(findings, family, json_path, index, row)
                continue

            if family in _DICT_FAMILIES and not isinstance(payload, dict):
                add_finding(findings, _path_str(json_path), "runtime_schema_error", f"{family} file must be an object", "high")

            if family == METRICS_FAMILY and isinstance(payload, dict):
                missing = _missing_keys(payload, _METRICS_REQUIRED_KEYS)
                if missing:
                    add_finding(findings, _path_str(json_path), "runtime_missing_keys", ", ".join(missing), "high")

            if family == DAILY_SUMMARIES_FAMILY and isinstance(payload, dict):
                missing = _missing_keys(payload, _SUMMARY_REQUIRED_KEYS)
                if missing:
                    add_finding(findings, _path_str(json_path), "runtime_missing_keys", ", ".join(missing), "high")

            if family == ENTRY_TIMING_SUMMARIES_FAMILY and isinstance(payload, dict):
                missing = _missing_keys(payload, _ENTRY_TIMING_SUMMARY_REQUIRED_KEYS)
                if missing:
                    add_finding(findings, _path_str(json_path), "runtime_missing_keys", ", ".join(missing), "high")

            if family == TRADE_AUDIT_REPORTS_FAMILY and isinstance(payload, dict):
                missing = _missing_keys(payload, _TRADE_AUDIT_REPORT_REQUIRED_KEYS)
                if missing:
                    add_finding(findings, _path_str(json_path), "runtime_missing_keys", ", ".join(missing), "high")

    return findings


def futures_runtime_integrity_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    _check_entry_audit_signal_coverage(findings)
    if not _RUNTIME_DATA.exists():
        return findings

    date_isos = sorted(_collect_dates())
    for date_iso in date_isos:
        _check_duplicate_signal_timestamps(findings, date_iso)
        _check_duplicate_position_ids(findings, date_iso)
        _check_daily_summary_counts(findings, date_iso)
    return findings


def _check_entry_audit_signal_coverage(findings: list[FileFinding]) -> None:
    # Use the canonical store: SQLite-primary installs have no daily JSON tree.
    rows = load_family_rows_all(TRADE_ENTRY_AUDITS_FAMILY)
    missing = [row for row in rows if not isinstance(row.get("entry_signal"), dict)
               or not row["entry_signal"]]
    if missing:
        add_finding(
            findings, "platform_v2/runtime/database/smartsignalhub_trading.sqlite3#futures_trade_entry_audits",
            "futures_entry_audit_signal_missing",
            f"{len(missing)}/{len(rows)} entry audits have no source signal; gate/timing attribution is unreliable",
            "medium",
        )


def _check_list_row(findings: list[FileFinding], family: str, json_path: Path, index: int, row: Any) -> None:
    if not isinstance(row, dict):
        add_finding(findings, _path_str(json_path, index=index), "runtime_schema_error", "row must be an object", "high")
        return

    required_by_family: dict[str, tuple[str, ...]] = {
        SIGNALS_FAMILY: _SIGNAL_REQUIRED_KEYS,
        POSITION_EVENTS_FAMILY: _POSITION_EVENT_REQUIRED_KEYS,
        ORDERS_FAMILY: _ORDER_REQUIRED_KEYS,
        DENIED_ENTRIES_FAMILY: _DENIED_REQUIRED_KEYS,
        TRADE_ENTRY_AUDITS_FAMILY: _TRADE_ENTRY_AUDIT_REQUIRED_KEYS,
        MARKET_PLANS_FAMILY: _MARKET_PLAN_REQUIRED_KEYS,
        CYCLE_RUNS_FAMILY: _CYCLE_REQUIRED_KEYS,
    }
    missing = _missing_keys(row, required_by_family.get(family, tuple()))
    if missing:
        add_finding(findings, _path_str(json_path, index=index), "runtime_missing_keys", ", ".join(missing), "high")
        return

    if family == SIGNALS_FAMILY and not isinstance(row.get("gates"), dict):
        add_finding(findings, _path_str(json_path, index=index), "runtime_schema_error", "gates must be an object", "high")


def _check_duplicate_signal_timestamps(findings: list[FileFinding], date_iso: str) -> None:
    signal_rows = _load_day_rows(SIGNALS_FAMILY, date_iso)
    if not signal_rows:
        return
    timestamp_counts = Counter(
        str(row.get("timestamp_ms") or "").strip()
        for row in signal_rows
        if str(row.get("timestamp_ms") or "").strip()
    )
    duplicates = sorted(value for value, count in timestamp_counts.items() if count > 1)
    if duplicates:
        add_finding(
            findings,
            _family_day_path(SIGNALS_FAMILY, date_iso),
            "duplicate_signal_timestamp_rows",
            f"duplicate_timestamps={len(duplicates)} sample={', '.join(duplicates[:3])}",
            "medium",
        )


def _check_duplicate_position_ids(findings: list[FileFinding], date_iso: str) -> None:
    position_rows = load_family_rows(POSITIONS_FAMILY, date_iso)
    if not position_rows:
        return

    open_position_counts = Counter(
        str(row.get("position_id") or "").strip()
        for row in position_rows
        if row.get("status") == "OPEN" and str(row.get("position_id") or "").strip()
    )
    duplicate_open_ids = sorted(value for value, count in open_position_counts.items() if count > 1)
    if duplicate_open_ids:
        add_finding(
            findings,
            _family_day_path(POSITION_EVENTS_FAMILY, date_iso),
            "duplicate_open_position_rows",
            f"duplicate_open_ids={len(duplicate_open_ids)} sample={', '.join(duplicate_open_ids[:3])}",
            "high",
        )

    closed_position_counts = Counter(
        str(row.get("position_id") or "").strip()
        for row in position_rows
        if row.get("status") == "CLOSED" and str(row.get("position_id") or "").strip()
    )
    duplicate_closed_ids = sorted(value for value, count in closed_position_counts.items() if count > 1)
    if duplicate_closed_ids:
        add_finding(
            findings,
            _family_day_path(POSITION_EVENTS_FAMILY, date_iso),
            "duplicate_closed_position_rows",
            f"duplicate_closed_ids={len(duplicate_closed_ids)} sample={', '.join(duplicate_closed_ids[:3])}",
            "medium",
        )


def _check_daily_summary_counts(findings: list[FileFinding], date_iso: str) -> None:
    summary = _load_day_dict(DAILY_SUMMARIES_FAMILY, date_iso)
    if not summary:
        return
    cycle_rows = _load_day_rows(CYCLE_RUNS_FAMILY, date_iso)
    order_rows = _load_day_rows(ORDERS_FAMILY, date_iso)
    denied_rows = _load_day_rows(DENIED_ENTRIES_FAMILY, date_iso)

    long_signals = sum(
        str(row.get("signal_side") or "").upper() in {"LONG", "BUY"} for row in cycle_rows
    )
    short_signals = sum(
        str(row.get("signal_side") or "").upper() in {"SHORT", "SELL"} for row in cycle_rows
    )
    expected = {
        "total_cycles": len(cycle_rows),
        "ok_cycles": sum(row.get("status") == "ok" for row in cycle_rows),
        "skipped_cycles": sum(row.get("status") != "ok" for row in cycle_rows),
        "buy_signals": long_signals,
        "long_signals": long_signals,
        "short_signals": short_signals,
        "no_signal_cycles": sum(row.get("signal_side") == "NO_SIGNAL" for row in cycle_rows),
        "opened_orders": sum(row.get("status") == "FILLED" for row in order_rows),
        "denied_entries": len(denied_rows),
    }
    mismatches = [
        f"{key}={summary.get(key)} expected={value}"
        for key, value in expected.items()
        if key in summary and summary.get(key) != value
    ]
    if mismatches:
        add_finding(
            findings,
            _family_day_path(DAILY_SUMMARIES_FAMILY, date_iso),
            "daily_summary_mismatch",
            ", ".join(mismatches),
            "high",
        )


def _collect_dates() -> set[str]:
    date_isos: set[str] = set()
    for family in _FAMILIES:
        family_path = _RUNTIME_DATA / family
        if not family_path.exists():
            continue
        prefix = f"{family}_"
        for json_path in family_path.glob(f"{prefix}*.json"):
            stem = json_path.stem
            if stem.startswith(prefix):
                date_isos.add(stem.removeprefix(prefix))
    return date_isos


def _load_day_rows(family_name: str, date_iso: str) -> list[dict[str, Any]]:
    payload = _load_json(daily_json_path(family_name, date_iso))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _load_day_dict(family_name: str, date_iso: str) -> dict[str, Any]:
    payload = _load_json(daily_json_path(family_name, date_iso))
    if isinstance(payload, dict):
        return payload
    return {}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _missing_keys(payload: dict[str, Any], required_keys: tuple[str, ...]) -> list[str]:
    return [key for key in required_keys if key not in payload]


def _path_str(path: Path, *, index: int | None = None) -> str:
    base = str(path.relative_to(_RUNTIME_ROOT.parents[2]))
    return base if index is None else f"{base}#{index}"


def _family_day_path(family_name: str, date_iso: str) -> str:
    return f"{_PATH_PREFIX}/data/{family_name}/{family_name}_{date_iso}.json"
