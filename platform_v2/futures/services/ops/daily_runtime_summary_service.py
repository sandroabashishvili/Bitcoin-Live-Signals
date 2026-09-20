"""Build a compact daily runtime summary for Futures observability."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    CYCLE_RUNS_FAMILY,
    DAILY_SUMMARIES_FAMILY,
    DENIED_ENTRIES_FAMILY,
    METRICS_FAMILY,
    ORDERS_FAMILY,
    daily_json_path,
    load_json_dict,
    load_json_list,
    store_runtime_snapshot,
)


class DailyRuntimeSummaryService:
    """Aggregate one-day futures runtime observability metrics from runtime files."""

    def build_summary(self, *, date_iso: str) -> dict[str, Any]:
        cycle_rows = self._load_rows(CYCLE_RUNS_FAMILY, date_iso)
        order_rows = self._load_rows(ORDERS_FAMILY, date_iso)
        denied_rows = self._load_rows(DENIED_ENTRIES_FAMILY, date_iso)
        metrics = self._load_dict(METRICS_FAMILY, date_iso)

        skip_reasons = Counter(
            str(row.get("skip_reason"))
            for row in cycle_rows
            if row.get("status") == "skipped" and row.get("skip_reason")
        )
        cycle_states = Counter(
            str(row.get("cycle_state"))
            for row in cycle_rows
            if row.get("cycle_state")
        )
        permission_reasons = Counter(
            str(row.get("permission_reason"))
            for row in cycle_rows
            if row.get("permission_reason")
        )
        position_events = Counter(
            str(row.get("position_event"))
            for row in cycle_rows
            if row.get("position_event")
        )
        denied_reasons = Counter(str(row.get("reason")) for row in denied_rows if row.get("reason"))
        blocker_counts = Counter()
        for row in cycle_rows:
            if row.get("status") != "ok":
                continue
            if row.get("signal_side") != "NO_SIGNAL":
                continue
            for blocker in self._normalize_string_list(row.get("failed_gates")):
                blocker_counts[blocker] += 1
            score = row.get("score")
            threshold = row.get("threshold")
            if self._as_float(score) < self._as_float(threshold):
                blocker_counts["threshold"] += 1

        long_signals = sum(
            1 for row in cycle_rows if str(row.get("signal_side") or "").upper() in {"LONG", "BUY"}
        )
        short_signals = sum(
            1 for row in cycle_rows if str(row.get("signal_side") or "").upper() in {"SHORT", "SELL"}
        )
        no_signal_cycles = sum(1 for row in cycle_rows if row.get("signal_side") == "NO_SIGNAL")
        score_passed_but_no_signal = sum(
            1
            for row in cycle_rows
            if row.get("status") == "ok"
            and row.get("signal_side") == "NO_SIGNAL"
            and bool(row.get("score_passed"))
        )
        opened_orders = sum(1 for row in order_rows if self._read_order_status(row) == "FILLED")

        return {
            "date": date_iso,
            "datetime": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "total_cycles": len(cycle_rows),
            "ok_cycles": sum(1 for row in cycle_rows if row.get("status") == "ok"),
            "skipped_cycles": sum(1 for row in cycle_rows if row.get("status") == "skipped"),
            "skip_reasons": dict(skip_reasons),
            "cycle_states": dict(cycle_states),
            "permission_reasons": dict(permission_reasons),
            "position_events": dict(position_events),
            "denied_reasons": dict(denied_reasons),
            "buy_signals": long_signals,
            "long_signals": long_signals,
            "short_signals": short_signals,
            "no_signal_cycles": no_signal_cycles,
            "score_passed_but_no_signal": score_passed_but_no_signal,
            "opened_orders": opened_orders,
            "denied_entries": len(denied_rows),
            "blocker_counts": dict(blocker_counts),
            "latest_cycle": cycle_rows[-1] if cycle_rows else None,
            "metrics_snapshot": metrics or None,
        }

    def build_and_store(self, *, date_iso: str) -> Path:
        summary = self.build_summary(date_iso=date_iso)
        return store_runtime_snapshot(DAILY_SUMMARIES_FAMILY, date_iso, summary)

    @staticmethod
    def _load_rows(family_name: str, date_iso: str) -> list[dict[str, Any]]:
        path = daily_json_path(family_name, date_iso)
        return load_json_list(path)

    @staticmethod
    def _load_dict(family_name: str, date_iso: str) -> dict[str, Any]:
        path = daily_json_path(family_name, date_iso)
        return load_json_dict(path)

    @staticmethod
    def _normalize_string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str) and item]

    @staticmethod
    def _read_order_status(row: dict[str, Any]) -> str:
        status = row.get("status")
        return str(status) if status is not None else ""

    @staticmethod
    def _as_float(value: object) -> float:
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0
