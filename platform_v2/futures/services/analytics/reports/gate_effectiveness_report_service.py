"""File: gate_effectiveness_report_service.py
Folder: platform_v2/futures/services/analytics/reports
Created date: 2026-05-13
Last updated date: 2026-05-14
Author: Codex
Purpose: Persist backend-computed Futures gate effectiveness reports to runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    POSITION_EVENTS_FAMILY,
    SIGNALS_FAMILY,
    STRATEGY_GATE_EFFECTIVENESS_REPORTS_FAMILY,
    TRADE_GATE_EFFECTIVENESS_REPORTS_FAMILY,
    load_family_rows_all,
    store_runtime_snapshot,
)
from platform_v2.futures.services.analytics.futures_strategy_effectiveness import (
    StrategyEffectivenessService,
)


class FuturesGateEffectivenessReportService:
    """Build and store Futures gate effectiveness snapshots from runtime source rows."""

    def __init__(self, effectiveness_service: StrategyEffectivenessService | None = None) -> None:
        self._effectiveness_service = effectiveness_service or StrategyEffectivenessService()

    def build_and_store(self, *, date_iso: str) -> tuple[Path, Path]:
        strategy_path = store_runtime_snapshot(
            STRATEGY_GATE_EFFECTIVENESS_REPORTS_FAMILY,
            date_iso,
            self.build_strategy_report(date_iso=date_iso),
        )
        trade_path = store_runtime_snapshot(
            TRADE_GATE_EFFECTIVENESS_REPORTS_FAMILY,
            date_iso,
            self.build_trade_outcomes_report(date_iso=date_iso),
        )
        return strategy_path, trade_path

    def build_strategy_report(self, *, date_iso: str) -> dict[str, Any]:
        signal_rows = [
            row for row in load_family_rows_all(SIGNALS_FAMILY)
            if self._is_on_or_before(row, date_iso)
        ]
        signal_rows.sort(key=self._timestamp_ms)

        strategy_logic = self._effectiveness_service.build_logic_evaluation(signal_rows)
        signal_activity = self._effectiveness_service.build_signal_activity_summary(signal_rows)

        return {
            "date": date_iso,
            "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
            "source_families": {
                "signals": SIGNALS_FAMILY,
            },
            "source_counts": {
                "signals": len(signal_rows),
            },
            "strategy_logic_evaluation": strategy_logic,
            "signal_activity_summary": signal_activity,
        }

    def build_trade_outcomes_report(self, *, date_iso: str) -> dict[str, Any]:
        signal_rows = [
            row for row in load_family_rows_all(SIGNALS_FAMILY)
            if self._is_on_or_before(row, date_iso)
        ]
        position_rows = [
            row for row in load_family_rows_all(POSITION_EVENTS_FAMILY)
            if self._is_on_or_before(row, date_iso)
        ]
        signal_rows.sort(key=self._timestamp_ms)
        position_rows.sort(key=self._timestamp_ms)

        trade_outcomes_logic = self._effectiveness_service.build_closed_trade_logic_evaluation_from_events(
            signal_rows=signal_rows,
            position_rows=position_rows,
        )

        return {
            "date": date_iso,
            "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
            "source_families": {
                "signals": SIGNALS_FAMILY,
                "position_events": POSITION_EVENTS_FAMILY,
            },
            "source_counts": {
                "signals": len(signal_rows),
                "position_events": len(position_rows),
            },
            "trade_outcomes_logic_evaluation": trade_outcomes_logic,
        }

    def _is_on_or_before(self, row: dict[str, Any], date_iso: str) -> bool:
        row_date = self._row_date(row)
        return row_date is not None and row_date <= date_iso

    @staticmethod
    def _row_date(row: dict[str, Any]) -> str | None:
        parsed_ms = FuturesGateEffectivenessReportService._timestamp_ms(row)
        if parsed_ms <= 0:
            return None
        return datetime.fromtimestamp(parsed_ms / 1000, tz=UTC).date().isoformat()

    @staticmethod
    def _timestamp_ms(row: dict[str, Any]) -> int:
        try:
            return int(row.get("timestamp_ms") or 0)
        except (TypeError, ValueError):
            return 0
