"""File: runtime_checks.py
Folder: platform_v2/tools/diagnostics/checks
Created date: 2026-04-18
Last updated date: 2026-06-02
Author: Codex
Purpose: Validate runtime structure, schemas, ledgers, and generated trading state.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from platform_v2.spot.domain.models.position import ExitReason
from platform_v2.shared.backend.runtime_store.spot import (
    CYCLE_RUNS_FAMILY,
    DAILY_SUMMARIES_FAMILY,
    DENIED_ENTRIES_FAMILY,
    METRICS_FAMILY,
    ORDERS_FAMILY,
    POSITIONS_FAMILY,
    SIGNALS_FAMILY,
    daily_json_path,
)
from platform_v2.spot.services.account.position_state_service import PositionStateService
from platform_v2.tools.diagnostics.checks.position_exit_trigger_checks import check_position_exit_triggers
from platform_v2.tools.diagnostics.core.config import (
    DENIED_REQUIRED_KEYS,
    METRICS_REQUIRED_KEYS,
    ORDER_REQUEST_KEYS,
    ORDER_REQUIRED_KEYS,
    POSITION_EXECUTION_KEYS,
    POSITION_REQUIRED_KEYS,
    RUNTIME_FAMILY_HIGH_DAYS,
    RUNTIME_FAMILY_WARNING_DAYS,
    RUNTIME_FAMILIES,
    RUNTIME_GROWTH_TRACKED_FAMILIES,
    RUNTIME_JSON_HIGH_BYTES,
    RUNTIME_JSON_HIGH_ROWS,
    RUNTIME_JSON_WARNING_BYTES,
    RUNTIME_JSON_WARNING_ROWS,
    SIGNAL_GATE_KEYS,
    SIGNAL_REQUIRED_KEYS,
    TOP_LEVEL_DIRS,
    V2_ROOT,
)
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


OPTIONAL_CLEAN_STATE_FAMILIES = {
    DENIED_ENTRIES_FAMILY,
    ORDERS_FAMILY,
    POSITIONS_FAMILY,
}


def runtime_structure_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    runtime_data = V2_ROOT / "runtime" / "spot" / "data"
    artifacts_dir = V2_ROOT / "runtime" / "artifacts"
    path_str = "platform_v2/runtime/spot"

    if not runtime_data.exists():
        # SQLite-primary clean state intentionally has no live JSON data tree.
        # The directory appears only for explicit exports or control files.
        return findings
    if not artifacts_dir.exists():
        add_finding(
            findings,
            "platform_v2/runtime",
            "missing_runtime_artifacts_dir",
            "central runtime/artifacts is missing",
            "medium",
        )

    for family in RUNTIME_FAMILIES:
        family_path = runtime_data / family
        if not family_path.exists():
            continue
        for json_path in sorted(family_path.glob("*.json")):
            expected_prefix = f"{family}_"
            if not json_path.name.startswith(expected_prefix):
                add_finding(findings, str(json_path.relative_to(V2_ROOT.parent)), "runtime_file_naming_drift", f"expected prefix {expected_prefix}", "low")
    return findings


def load_runtime_json(path: Path) -> Any:
    payload: Any = None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = None
    return payload


def missing_keys(payload: dict[str, Any], required_keys: tuple[str, ...]) -> list[str]:
    return [key for key in required_keys if key not in payload]


def record_path(path: Path, *, index: int | None = None) -> str:
    base = str(path.relative_to(V2_ROOT.parent))
    return base if index is None else f"{base}#{index}"


def runtime_schema_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    runtime_data = V2_ROOT / "runtime" / "spot" / "data"
    if not runtime_data.exists():
        return findings

    for family in RUNTIME_FAMILIES:
        family_path = runtime_data / family
        if not family_path.exists():
            continue
        for json_path in sorted(family_path.rglob("*.json")):
            payload = load_runtime_json(json_path)
            if payload is None:
                add_finding(findings, record_path(json_path), "runtime_json_decode_error", "could not decode json", "high")
                continue

            if family == "metrics":
                _check_metrics_payload(findings, json_path, payload)
                continue

            if family == "daily_summaries":
                if not isinstance(payload, dict):
                    add_finding(findings, record_path(json_path), "runtime_schema_error", "daily_summaries file must be an object", "high")
                continue

            if not isinstance(payload, list):
                add_finding(findings, record_path(json_path), "runtime_schema_error", f"{family} file must be a list", "high")
                continue

            for index, row in enumerate(payload):
                _check_runtime_row(findings, family, json_path, index, row)

    return findings


def runtime_integrity_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    runtime_data = V2_ROOT / "runtime" / "spot" / "data"
    if not runtime_data.exists():
        return findings

    date_isos = sorted(_collect_runtime_dates(runtime_data))
    position_state_service = PositionStateService()

    _check_runtime_family_growth(findings, runtime_data)

    for date_iso in date_isos:
        _check_duplicate_signal_timestamps(findings, date_iso)
        _check_duplicate_position_ids(findings, date_iso)
        _check_filled_orders_have_positions(findings, date_iso)
        _check_daily_summary_against_runtime_rows(findings, date_iso)
        check_position_exit_triggers(findings, date_iso)
    if date_isos:
        # Historical metric snapshots preserve the calculation rules that were
        # active on their day. Cross-check only the current cumulative state.
        _check_metrics_against_position_state(findings, date_isos[-1], position_state_service)

    return findings


def _check_metrics_payload(findings: list[FileFinding], json_path: Path, payload: Any) -> None:
    if not isinstance(payload, dict):
        add_finding(findings, record_path(json_path), "runtime_schema_error", "metrics file must be an object", "high")
        return
    missing = missing_keys(payload, METRICS_REQUIRED_KEYS)
    if missing:
        add_finding(findings, record_path(json_path), "runtime_missing_keys", ", ".join(missing), "high")
    if any(payload.get(key) is None for key in ("equity", "starting_capital", "available_balance")):
        add_finding(findings, record_path(json_path), "runtime_impossible_state", "metrics contains null capital values", "medium")


def _check_runtime_row(findings: list[FileFinding], family: str, json_path: Path, index: int, row: Any) -> None:
    if not isinstance(row, dict):
        add_finding(findings, record_path(json_path, index=index), "runtime_schema_error", "row must be an object", "high")
        return

    if family == "signals":
        _check_signal_row(findings, json_path, index, row)
    elif family == "positions":
        _check_position_row(findings, json_path, index, row)
    elif family == "orders":
        _check_order_row(findings, json_path, index, row)
    elif family == "denied_entries":
        _check_denied_row(findings, json_path, index, row)


def _check_signal_row(findings: list[FileFinding], json_path: Path, index: int, row: dict[str, Any]) -> None:
    missing = missing_keys(row, SIGNAL_REQUIRED_KEYS)
    if missing:
        add_finding(findings, record_path(json_path, index=index), "runtime_missing_keys", ", ".join(missing), "high")
        return
    gates = row.get("gates")
    if not isinstance(gates, dict):
        add_finding(findings, record_path(json_path, index=index), "runtime_schema_error", "gates must be an object", "high")
        return
    gate_missing = missing_keys(gates, SIGNAL_GATE_KEYS)
    if gate_missing:
        add_finding(findings, record_path(json_path, index=index), "runtime_missing_keys", f"gates: {', '.join(gate_missing)}", "medium")
    if row.get("side") == "BUY" and row.get("theoretical_setup") is None:
        add_finding(findings, record_path(json_path, index=index), "runtime_impossible_state", "BUY signal without theoretical_setup", "medium")


def _check_position_row(findings: list[FileFinding], json_path: Path, index: int, row: dict[str, Any]) -> None:
    missing = missing_keys(row, POSITION_REQUIRED_KEYS)
    if missing:
        add_finding(findings, record_path(json_path, index=index), "runtime_missing_keys", ", ".join(missing), "high")
        return
    execution = row.get("execution")
    if not isinstance(execution, dict):
        add_finding(findings, record_path(json_path, index=index), "runtime_schema_error", "execution must be an object", "high")
        return
    exec_missing = missing_keys(execution, POSITION_EXECUTION_KEYS)
    if exec_missing:
        add_finding(findings, record_path(json_path, index=index), "runtime_missing_keys", f"execution: {', '.join(exec_missing)}", "medium")
    status = row.get("status")
    exit_price = row.get("exit_price")
    closed_at = row.get("closed_at")
    if status == "OPEN" and (exit_price is not None or closed_at):
        add_finding(findings, record_path(json_path, index=index), "runtime_impossible_state", "OPEN position has exit data", "medium")
    if status == "OPEN" and row.get("unrealized_pnl") is None:
        add_finding(findings, record_path(json_path, index=index), "runtime_impossible_state", "OPEN position missing unrealized_pnl", "medium")
    if status == "CLOSED" and exit_price is None:
        add_finding(findings, record_path(json_path, index=index), "runtime_impossible_state", "CLOSED position missing exit_price", "medium")
    if status == "CLOSED" and not row.get("exit_reason"):
        add_finding(findings, record_path(json_path, index=index), "runtime_impossible_state", "CLOSED position missing exit_reason", "medium")


def _check_order_row(findings: list[FileFinding], json_path: Path, index: int, row: dict[str, Any]) -> None:
    missing = missing_keys(row, ORDER_REQUIRED_KEYS)
    if missing:
        add_finding(findings, record_path(json_path, index=index), "runtime_missing_keys", ", ".join(missing), "high")
        return
    request = row.get("request")
    if not isinstance(request, dict):
        add_finding(findings, record_path(json_path, index=index), "runtime_schema_error", "request must be an object", "high")
        return
    request_missing = missing_keys(request, ORDER_REQUEST_KEYS)
    if request_missing:
        add_finding(findings, record_path(json_path, index=index), "runtime_missing_keys", f"request: {', '.join(request_missing)}", "medium")
    if row.get("status") == "FILLED" and not isinstance(row.get("fill"), dict):
        add_finding(findings, record_path(json_path, index=index), "runtime_impossible_state", "FILLED order missing fill object", "medium")


def _check_denied_row(findings: list[FileFinding], json_path: Path, index: int, row: dict[str, Any]) -> None:
    missing = missing_keys(row, DENIED_REQUIRED_KEYS)
    if missing:
        add_finding(findings, record_path(json_path, index=index), "runtime_missing_keys", ", ".join(missing), "high")
        return
    if not isinstance(row.get("signal"), dict):
        add_finding(findings, record_path(json_path, index=index), "runtime_schema_error", "signal must be an object", "high")
    if not isinstance(row.get("permission"), dict):
        add_finding(findings, record_path(json_path, index=index), "runtime_schema_error", "permission must be an object", "high")


def top_level_structure_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    path_str = "platform_v2"

    for directory_name in TOP_LEVEL_DIRS:
        directory = V2_ROOT / directory_name
        if not directory.exists():
            continue
        has_files = any(path.is_file() for path in directory.rglob("*"))
        if not has_files:
            add_finding(findings, path_str, "empty_top_level_dir", directory_name, "medium")

    frontend_dir = V2_ROOT / "public_site"
    web_dir = V2_ROOT / "web"
    if frontend_dir.exists() and web_dir.exists():
        add_finding(findings, path_str, "overlapping_ui_roots", "public_site/ and web/ both exist", "medium")

    engine_dir = V2_ROOT / "engine"
    if engine_dir.exists():
        add_finding(findings, path_str, "ambiguous_top_level_dir", "engine/ exists and needs explicit responsibility or removal", "medium")

    misplaced_archive_dir = V2_ROOT / "runtime_archives"
    if misplaced_archive_dir.exists():
        add_finding(
            findings,
            str(misplaced_archive_dir.relative_to(V2_ROOT.parent)),
            "misplaced_runtime_artifact",
            "runtime reset archives belong in /home/sandro/runtime_archives",
            "medium",
        )

    external_artifacts_dir = V2_ROOT.parent / "SmartSignalHub_artifacts"
    if external_artifacts_dir.exists():
        add_finding(
            findings,
            str(external_artifacts_dir),
            "misplaced_runtime_artifact",
            "generated artifacts belong in platform_v2/runtime/artifacts",
            "medium",
        )

    tools_dir = V2_ROOT / "tools"
    if tools_dir.exists():
        for log_path in sorted(tools_dir.glob("*.log")):
            add_finding(
                findings,
                str(log_path.relative_to(V2_ROOT.parent)),
                "misplaced_runtime_artifact",
                "tool logs belong in platform_v2/runtime/logs/tools",
                "medium",
            )

    app_dir = V2_ROOT / "app"
    run_files = sorted(path for path in app_dir.glob("run_*.py") if path.is_file())
    if len(run_files) > 4:
        add_finding(findings, path_str, "entrypoint_clutter", f"{len(run_files)} run_* files in app/", "medium")

    return findings


def _collect_runtime_dates(runtime_data: Path) -> set[str]:
    date_isos: set[str] = set()
    for family in RUNTIME_FAMILIES:
        family_path = runtime_data / family
        if not family_path.exists():
            continue
        prefix = f"{family}_"
        for json_path in family_path.glob(f"{prefix}*.json"):
            stem = json_path.stem
            if stem.startswith(prefix):
                date_isos.add(stem.removeprefix(prefix))
    return date_isos


def _load_runtime_day_rows(family_name: str, date_iso: str) -> list[dict[str, Any]]:
    payload = load_runtime_json(daily_json_path(family_name, date_iso))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _load_runtime_day_dict(family_name: str, date_iso: str) -> dict[str, Any]:
    payload = load_runtime_json(daily_json_path(family_name, date_iso))
    if isinstance(payload, dict):
        return payload
    return {}


def _check_runtime_family_growth(findings: list[FileFinding], runtime_data: Path) -> None:
    for family_name in RUNTIME_GROWTH_TRACKED_FAMILIES:
        family_path = runtime_data / family_name
        if not family_path.exists():
            continue

        files = sorted(path for path in family_path.glob("*.json") if path.is_file())
        if not files:
            continue

        if len(files) >= RUNTIME_FAMILY_HIGH_DAYS:
            add_finding(
                findings,
                f"platform_v2/runtime/spot/data/{family_name}",
                "runtime_family_growth_high",
                f"{family_name} keeps {len(files)} daily json files without archive/retention split",
                "medium",
            )
        elif len(files) >= RUNTIME_FAMILY_WARNING_DAYS:
            add_finding(
                findings,
                f"platform_v2/runtime/spot/data/{family_name}",
                "runtime_family_growth_warning",
                f"{family_name} already has {len(files)} daily json files",
                "low",
            )

        latest_path = files[-1]
        payload = load_runtime_json(latest_path)
        row_count = len(payload) if isinstance(payload, list) else 1 if isinstance(payload, dict) else 0
        size_bytes = latest_path.stat().st_size
        path_str = record_path(latest_path)

        if row_count >= RUNTIME_JSON_HIGH_ROWS:
            add_finding(
                findings,
                path_str,
                "runtime_file_growth_high",
                f"row_count={row_count} exceeds {RUNTIME_JSON_HIGH_ROWS}",
                "medium",
            )
        elif row_count >= RUNTIME_JSON_WARNING_ROWS:
            add_finding(
                findings,
                path_str,
                "runtime_file_growth_warning",
                f"row_count={row_count} exceeds {RUNTIME_JSON_WARNING_ROWS}",
                "low",
            )

        if size_bytes >= RUNTIME_JSON_HIGH_BYTES:
            add_finding(
                findings,
                path_str,
                "runtime_file_size_high",
                f"size_bytes={size_bytes} exceeds {RUNTIME_JSON_HIGH_BYTES}",
                "medium",
            )
        elif size_bytes >= RUNTIME_JSON_WARNING_BYTES:
            add_finding(
                findings,
                path_str,
                "runtime_file_size_warning",
                f"size_bytes={size_bytes} exceeds {RUNTIME_JSON_WARNING_BYTES}",
                "low",
            )


def _check_duplicate_position_ids(findings: list[FileFinding], date_iso: str) -> None:
    position_rows = _load_runtime_day_rows(POSITIONS_FAMILY, date_iso)
    if not position_rows:
        return

    open_position_counts = Counter(
        str(row.get("position_id") or "").strip()
        for row in position_rows
        if row.get("status") == "OPEN" and str(row.get("position_id") or "").strip()
    )
    duplicate_open_ids = sorted(pid for pid, count in open_position_counts.items() if count > 1)
    if duplicate_open_ids:
        sample = ", ".join(duplicate_open_ids[:3])
        add_finding(
            findings,
            f"platform_v2/runtime/spot/data/{POSITIONS_FAMILY}/{POSITIONS_FAMILY}_{date_iso}.json",
            "duplicate_open_position_rows",
            f"duplicate_open_ids={len(duplicate_open_ids)} sample={sample}",
            "high",
        )


def _check_duplicate_signal_timestamps(findings: list[FileFinding], date_iso: str) -> None:
    signal_rows = _load_runtime_day_rows(SIGNALS_FAMILY, date_iso)
    if not signal_rows:
        return

    timestamp_counts = Counter(
        str(row.get("timestamp_ms") or "").strip()
        for row in signal_rows
        if str(row.get("timestamp_ms") or "").strip()
    )
    duplicate_timestamps = sorted(timestamp for timestamp, count in timestamp_counts.items() if count > 1)
    if not duplicate_timestamps:
        return

    sample = ", ".join(duplicate_timestamps[:3])
    add_finding(
        findings,
        f"platform_v2/runtime/spot/data/{SIGNALS_FAMILY}/{SIGNALS_FAMILY}_{date_iso}.json",
        "duplicate_signal_timestamp_rows",
        f"duplicate_timestamps={len(duplicate_timestamps)} sample={sample}",
        "high",
    )


def _check_filled_orders_have_positions(findings: list[FileFinding], date_iso: str) -> None:
    order_rows = _load_runtime_day_rows(ORDERS_FAMILY, date_iso)
    position_rows = _load_runtime_day_rows(POSITIONS_FAMILY, date_iso)
    if not order_rows:
        return

    filled_orders = [row for row in order_rows if row.get("status") == "FILLED"]
    if not filled_orders:
        return

    opened_position_ids = {
        str(row.get("position_id") or "")
        for row in position_rows
        if str(row.get("opened_at") or "").startswith(date_iso)
    }
    opened_position_ids.discard("")

    if not opened_position_ids:
        add_finding(
            findings,
            f"platform_v2/runtime/spot/data/{ORDERS_FAMILY}/{ORDERS_FAMILY}_{date_iso}.json",
            "filled_order_without_position",
            f"{len(filled_orders)} FILLED orders but no positions opened on {date_iso}",
            "high",
        )
        return

    if len(opened_position_ids) < len(filled_orders):
        add_finding(
            findings,
            f"platform_v2/runtime/spot/data/{ORDERS_FAMILY}/{ORDERS_FAMILY}_{date_iso}.json",
            "filled_order_position_count_mismatch",
            f"FILLED orders={len(filled_orders)} opened_positions={len(opened_position_ids)}",
            "medium",
        )


def _check_metrics_against_position_state(
    findings: list[FileFinding],
    date_iso: str,
    position_state_service: PositionStateService,
) -> None:
    metrics = _load_runtime_day_dict(METRICS_FAMILY, date_iso)
    if not metrics:
        return

    latest_positions = position_state_service.load_latest_positions(
        as_of_date_iso=date_iso,
        lookback_days=None,
    )
    open_positions = [position for position in latest_positions if position.is_open]
    closed_positions = [position for position in latest_positions if position.is_closed]
    tp_hits = sum(position.exit_reason == ExitReason.TP_HIT for position in closed_positions)
    sl_hits = sum(position.exit_reason == ExitReason.SL_HIT for position in closed_positions)
    force_close_events = sum(bool(position.was_force_closed) for position in closed_positions)

    expected_counts = {
        "open_positions": len(open_positions),
        "closed_positions": len(closed_positions),
        "total_positions": len(latest_positions),
        "tp_hits": tp_hits,
        "sl_hits": sl_hits,
        "force_close_events": force_close_events,
    }
    mismatches = [
        f"{key}={metrics.get(key)} expected={expected}"
        for key, expected in expected_counts.items()
        if metrics.get(key) != expected
    ]
    if mismatches:
        add_finding(
            findings,
            f"platform_v2/runtime/spot/data/{METRICS_FAMILY}/{METRICS_FAMILY}_{date_iso}.json",
            "metrics_position_count_mismatch",
            ", ".join(mismatches),
            "high",
        )


def _check_daily_summary_against_runtime_rows(findings: list[FileFinding], date_iso: str) -> None:
    summary = _load_runtime_day_dict(DAILY_SUMMARIES_FAMILY, date_iso)
    if not summary:
        return

    cycle_rows = _load_runtime_day_rows(CYCLE_RUNS_FAMILY, date_iso)
    signal_rows = _load_runtime_day_rows(SIGNALS_FAMILY, date_iso)
    order_rows = _load_runtime_day_rows(ORDERS_FAMILY, date_iso)
    denied_rows = _load_runtime_day_rows(DENIED_ENTRIES_FAMILY, date_iso)

    expected_counts = {
        "total_cycles": len(cycle_rows),
        "ok_cycles": sum(row.get("status") == "ok" for row in cycle_rows),
        "skipped_cycles": sum(row.get("status") != "ok" for row in cycle_rows),
        "buy_signals": sum(row.get("side") == "BUY" for row in signal_rows),
        "no_signal_cycles": sum(row.get("signal_side") == "NO_SIGNAL" for row in cycle_rows),
        "opened_orders": sum(row.get("status") == "FILLED" for row in order_rows),
        "denied_entries": len(denied_rows),
    }
    mismatches = [
        f"{key}={summary.get(key)} expected={expected}"
        for key, expected in expected_counts.items()
        if summary.get(key) != expected
    ]
    if mismatches:
        add_finding(
            findings,
            f"platform_v2/runtime/spot/data/{DAILY_SUMMARIES_FAMILY}/{DAILY_SUMMARIES_FAMILY}_{date_iso}.json",
            "daily_summary_mismatch",
            ", ".join(mismatches),
            "high",
        )
