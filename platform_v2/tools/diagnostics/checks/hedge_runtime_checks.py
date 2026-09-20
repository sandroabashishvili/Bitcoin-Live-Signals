"""Schema, structure, and cross-family integrity checks for Hedge runtime data."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.hedge import (
    HEDGE_BASKET_SNAPSHOTS_FAMILY,
    HEDGE_DAILY_SUMMARIES_FAMILY,
    HEDGE_ENTRIES_FAMILY,
    HEDGE_EQUITY_TIMELINE_FAMILY,
    HEDGE_RESET_EVENTS_FAMILY,
    runtime_root,
)
from platform_v2.shared.backend.runtime_store.families.hedge import ALL_FAMILIES
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


_RUNTIME_ROOT = runtime_root()
_PATH_PREFIX = "platform_v2/runtime/hedge"

_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    HEDGE_ENTRIES_FAMILY: (
        "hedge_entry_id",
        "source_position_id",
        "timestamp_ms",
        "side",
        "entry_price",
        "margin_usdt",
        "notional_usdt",
        "quantity",
        "leverage",
        "entry_fee_usdt",
    ),
    HEDGE_BASKET_SNAPSHOTS_FAMILY: (
        "snapshot_id",
        "hedge_entry_id",
        "source_position_id",
        "timestamp_ms",
        "mark_price",
        "cash_usdt",
        "equity_usdt",
        "available_capital_usdt",
        "used_margin_usdt",
        "reset_count",
        "long_basket",
        "short_basket",
    ),
    HEDGE_RESET_EVENTS_FAMILY: (
        "reset_id",
        "timestamp_ms",
        "reason",
        "mark_price",
        "gross_pnl",
        "exit_fees_usdt",
        "net_pnl",
        "equity_before_reset",
        "cash_after_reset",
    ),
    HEDGE_DAILY_SUMMARIES_FAMILY: (
        "date",
        "system",
        "mode",
        "generated_at",
        "opened_futures_events",
        "hedge_entries_accepted",
        "hedge_entries_skipped",
        "reset_count",
        "starting_capital_usdt",
        "cash_usdt",
        "equity_usdt",
        "available_capital_usdt",
        "used_margin_usdt",
        "realized_pnl_usdt",
        "total_fees_usdt",
        "liquidation_risk",
    ),
    HEDGE_EQUITY_TIMELINE_FAMILY: (
        "point_type",
        "timestamp_ms",
        "mark_price",
        "equity_usdt",
        "available_capital_usdt",
        "used_margin_usdt",
        "realized_pnl_usdt",
        "total_fees_usdt",
        "reset_count",
        "hedge_entries_accepted",
        "hedge_entries_skipped",
    ),
}


def hedge_runtime_structure_findings(runtime_data: Path | None = None) -> list[FileFinding]:
    data_root = runtime_data or (_RUNTIME_ROOT / "data")
    findings: list[FileFinding] = []
    if not data_root.exists():
        if runtime_data is None:
            # SQLite-primary clean state intentionally has no live JSON tree.
            return findings
        add_finding(findings, _PATH_PREFIX, "missing_runtime_data_dir", "futures_hedge runtime data is missing", "high")
        return findings

    for family in ALL_FAMILIES:
        family_path = data_root / family
        if not family_path.exists():
            if runtime_data is not None:
                add_finding(findings, _PATH_PREFIX, "missing_runtime_family_dir", family, "medium")
            continue
        expected_prefix = f"{family}_"
        for path in sorted(family_path.glob("*.json")):
            if not path.name.startswith(expected_prefix):
                add_finding(
                    findings,
                    _display_path(path, data_root=data_root),
                    "runtime_file_naming_drift",
                    f"expected prefix {expected_prefix}",
                    "low",
                )
    return findings


def hedge_runtime_schema_findings(runtime_data: Path | None = None) -> list[FileFinding]:
    data_root = runtime_data or (_RUNTIME_ROOT / "data")
    findings: list[FileFinding] = []
    if not data_root.exists():
        return findings

    for family in ALL_FAMILIES:
        family_path = data_root / family
        if not family_path.exists():
            continue
        for path in sorted(family_path.glob("*.json")):
            payload = _load_json(path)
            if payload is None:
                add_finding(findings, _display_path(path, data_root=data_root), "runtime_json_decode_error", "could not decode json", "high")
                continue
            if not isinstance(payload, list):
                add_finding(findings, _display_path(path, data_root=data_root), "runtime_schema_error", f"{family} file must be a list", "high")
                continue
            for index, row in enumerate(payload):
                if not isinstance(row, dict):
                    add_finding(findings, _display_path(path, data_root=data_root, index=index), "runtime_schema_error", "row must be an object", "high")
                    continue
                missing = [key for key in _REQUIRED_KEYS[family] if key not in row]
                if missing:
                    add_finding(findings, _display_path(path, data_root=data_root, index=index), "runtime_missing_keys", ", ".join(missing), "high")
    return findings


def hedge_runtime_integrity_findings(runtime_data: Path | None = None) -> list[FileFinding]:
    data_root = runtime_data or (_RUNTIME_ROOT / "data")
    if not data_root.exists():
        return []

    findings: list[FileFinding] = []
    entries = _load_family_rows(data_root, HEDGE_ENTRIES_FAMILY)
    snapshots = _load_family_rows(data_root, HEDGE_BASKET_SNAPSHOTS_FAMILY)
    resets = _load_family_rows(data_root, HEDGE_RESET_EVENTS_FAMILY)
    summaries = _load_family_rows(data_root, HEDGE_DAILY_SUMMARIES_FAMILY)
    equity_points = _load_family_rows(data_root, HEDGE_EQUITY_TIMELINE_FAMILY)

    _check_unique(findings, entries, key="hedge_entry_id", family=HEDGE_ENTRIES_FAMILY)
    _check_unique(findings, entries, key="source_position_id", family=HEDGE_ENTRIES_FAMILY)
    _check_unique(findings, snapshots, key="snapshot_id", family=HEDGE_BASKET_SNAPSHOTS_FAMILY)
    _check_unique(findings, resets, key="reset_id", family=HEDGE_RESET_EVENTS_FAMILY)

    entry_ids = {str(row.get("hedge_entry_id")) for row in entries}
    orphan_snapshots = [
        str(row.get("snapshot_id") or "?")
        for row in snapshots
        if str(row.get("hedge_entry_id")) not in entry_ids
    ]
    if orphan_snapshots:
        add_finding(
            findings,
            f"{_PATH_PREFIX}/data/{HEDGE_BASKET_SNAPSHOTS_FAMILY}",
            "orphan_hedge_snapshot",
            f"count={len(orphan_snapshots)} sample={', '.join(orphan_snapshots[:3])}",
            "high",
        )

    latest_summary = max(summaries, key=lambda row: str(row.get("generated_at") or row.get("date") or ""), default={})
    if latest_summary:
        _compare_count(findings, latest_summary, "hedge_entries_accepted", len(entries))
        _compare_count(findings, latest_summary, "reset_count", len(resets))
        if equity_points:
            latest_equity = max(equity_points, key=lambda row: _as_int(row.get("timestamp_ms")))
            for key in ("hedge_entries_accepted", "reset_count"):
                if key in latest_equity and latest_equity.get(key) != latest_summary.get(key):
                    add_finding(
                        findings,
                        f"{_PATH_PREFIX}/data/{HEDGE_DAILY_SUMMARIES_FAMILY}",
                        "hedge_summary_timeline_mismatch",
                        f"{key}={latest_summary.get(key)} latest_timeline={latest_equity.get(key)}",
                        "high",
                    )
    return findings


def _check_unique(
    findings: list[FileFinding],
    rows: list[dict[str, Any]],
    *,
    key: str,
    family: str,
) -> None:
    counts = Counter(str(row.get(key)) for row in rows if row.get(key) not in (None, ""))
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    if duplicates:
        add_finding(
            findings,
            f"{_PATH_PREFIX}/data/{family}",
            "duplicate_hedge_runtime_id",
            f"key={key} count={len(duplicates)} sample={', '.join(duplicates[:3])}",
            "high",
        )


def _compare_count(findings: list[FileFinding], summary: dict[str, Any], key: str, expected: int) -> None:
    if _as_int(summary.get(key)) != expected:
        add_finding(
            findings,
            f"{_PATH_PREFIX}/data/{HEDGE_DAILY_SUMMARIES_FAMILY}",
            "hedge_summary_count_mismatch",
            f"{key}={summary.get(key)} expected={expected}",
            "high",
        )


def _load_family_rows(data_root: Path, family: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    family_path = data_root / family
    for path in sorted(family_path.glob("*.json")) if family_path.exists() else ():
        payload = _load_json(path)
        if isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _display_path(path: Path, *, data_root: Path, index: int | None = None) -> str:
    try:
        suffix = path.relative_to(data_root)
        value = f"{_PATH_PREFIX}/data/{suffix}"
    except ValueError:
        value = str(path)
    return value if index is None else f"{value}#{index}"
