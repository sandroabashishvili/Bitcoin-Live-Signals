"""Build a compact daily runtime summary for V2 observability."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from platform_v2.shared.backend.runtime_store.spot import (
    CYCLE_RUNS_FAMILY,
    DAILY_SUMMARIES_FAMILY,
    DENIED_ENTRIES_FAMILY,
    METRICS_FAMILY,
    ORDERS_FAMILY,
    daily_json_path,
    load_family_rows,
    load_json_dict,
    store_runtime_snapshot,
)


class DailyRuntimeSummaryService:
    """Aggregate one-day runtime observability metrics from stored runtime files."""

    def build_summary(self, *, date_iso: str) -> Dict[str, Any]:
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
        blocker_counts = Counter()
        for row in cycle_rows:
            if row.get("status") != "ok" or row.get("signal_side") != "NO_SIGNAL":
                continue
            for blocker in self._normalize_string_list(row.get("failed_gates")):
                blocker_counts[blocker] += 1
            score = row.get("score")
            threshold = row.get("threshold")
            if self._as_float(score) < self._as_float(threshold):
                blocker_counts["threshold"] += 1

        buy_signals = sum(1 for row in cycle_rows if row.get("signal_side") == "BUY")
        no_signal_cycles = sum(1 for row in cycle_rows if row.get("signal_side") == "NO_SIGNAL")
        score_passed_but_no_signal = sum(
            1
            for row in cycle_rows
            if row.get("status") == "ok"
            and row.get("signal_side") == "NO_SIGNAL"
            and bool(row.get("score_passed"))
        )
        opened_orders = sum(1 for row in order_rows if self._read_order_status(row) == "FILLED")

        summary = {
            "date": date_iso,
            "datetime": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "total_cycles": len(cycle_rows),
            "ok_cycles": sum(1 for row in cycle_rows if row.get("status") == "ok"),
            "skipped_cycles": sum(1 for row in cycle_rows if row.get("status") == "skipped"),
            "skip_reasons": dict(skip_reasons),
            "cycle_states": dict(cycle_states),
            "buy_signals": buy_signals,
            "no_signal_cycles": no_signal_cycles,
            "score_passed_but_no_signal": score_passed_but_no_signal,
            "opened_orders": opened_orders,
            "denied_entries": len(denied_rows),
            "blocker_counts": dict(blocker_counts),
            "latest_cycle": cycle_rows[-1] if cycle_rows else None,
            "metrics_snapshot": metrics or None,
        }
        return summary

    def build_and_store(self, *, date_iso: str) -> Path:
        summary = self.build_summary(date_iso=date_iso)
        return store_runtime_snapshot(DAILY_SUMMARIES_FAMILY, date_iso, summary)

    @staticmethod
    def _load_rows(family_name: str, date_iso: str) -> List[Dict[str, Any]]:
        return load_family_rows(family_name, date_iso)

    @staticmethod
    def _load_dict(family_name: str, date_iso: str) -> Dict[str, Any]:
        path = daily_json_path(family_name, date_iso)
        return load_json_dict(path)

    @staticmethod
    def _normalize_string_list(value: object) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, str) and item]

    @staticmethod
    def _read_order_status(row: Dict[str, Any]) -> str:
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
