"""Build Futures Strategy Edge page from futures runtime data."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from platform_v2.shared.backend.runtime_store.futures import (
    STRATEGY_GATE_EFFECTIVENESS_REPORTS_FAMILY,
    load_family_rows_all,
    load_latest_document,
)
from platform_v2.futures.services.analytics.futures_strategy_effectiveness import (
    LogicEvaluationPayload,
)
from platform_v2.futures.services.metrics_system.grouped_payloads import build_strategy_activity_evaluation_items
from platform_v2.futures.services.metrics_system.strategy_content import StrategyPageContentService

from .renderer import StrategyEdgeFuturesPageRenderer


class StrategyEdgeFuturesPageService:
    """Generate a static HTML futures strategy edge page from futures runtime data."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"
    _SOURCE_CSS_PATH = Path(__file__).resolve().parents[1] / "css" / "styles.css"
    _TARGET_CSS_PATH = _TARGET_DIR / "css" / "styles.css"

    def __init__(
        self,
        content_service: StrategyPageContentService | None = None,
    ) -> None:
        self._content_service = content_service or StrategyPageContentService()

    def build_and_store(self) -> Path:
        payload = self._load_payload()
        html_text = StrategyEdgeFuturesPageRenderer().render(payload)
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        self._copy_css()
        return self._TARGET_PATH

    def _copy_css(self) -> None:
        if not self._SOURCE_CSS_PATH.exists():
            return
        if self._SOURCE_CSS_PATH.resolve() == self._TARGET_CSS_PATH.resolve():
            return
        self._TARGET_CSS_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._TARGET_CSS_PATH.write_text(self._SOURCE_CSS_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    def _load_payload(self) -> dict[str, Any]:
        signals_file, signals = self._load_all_family_rows("futures_signals")
        denied_file, denied_entries = self._load_all_family_rows("futures_denied_entries")
        metrics_file, metrics = self._load_latest_family_dict("futures_metrics")
        gate_report_file, gate_report = self._load_latest_family_dict(STRATEGY_GATE_EFFECTIVENESS_REPORTS_FAMILY)
        signal_rows: list[dict[str, Any]] = signals if isinstance(signals, list) else []
        denied_rows: list[dict[str, Any]] = denied_entries if isinstance(denied_entries, list) else []
        metrics_data: dict[str, Any] = metrics if isinstance(metrics, dict) else {}

        logic_evaluation = self._strategy_logic_from_report(gate_report)
        signal_activity_summary = self._signal_activity_from_report(gate_report)
        recent_signals_section = self._build_recent_signals_section(signal_rows, denied_rows)
        strategy_activity_items = build_strategy_activity_evaluation_items(signal_activity_summary)

        typed_logic_evaluation = cast(LogicEvaluationPayload, logic_evaluation)
        return {
            "generated_at": datetime.now(tz=UTC).strftime("%d.%m.%Y %H:%M:%S UTC"),
            "signals_file": signals_file,
            "denied_file": denied_file,
            "metrics_file": metrics_file,
            "gate_report_file": gate_report_file,
            "logic_chart_payload": logic_evaluation,
            "logic_tables_section": self._content_service.build_logic_tables_section(typed_logic_evaluation),
            "recent_signals_section": recent_signals_section,
            "strategy_activity_items": strategy_activity_items,
            "strategy_activity_summary": signal_activity_summary,
            "metrics": metrics_data,
        }

    @staticmethod
    def _strategy_logic_from_report(report: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(report, dict):
            return StrategyEdgeFuturesPageService._empty_logic_evaluation()
        payload = report.get("strategy_logic_evaluation")
        return payload if isinstance(payload, dict) else StrategyEdgeFuturesPageService._empty_logic_evaluation()

    @staticmethod
    def _signal_activity_from_report(report: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(report, dict):
            return StrategyEdgeFuturesPageService._empty_signal_activity_summary()
        payload = report.get("signal_activity_summary")
        return payload if isinstance(payload, dict) else StrategyEdgeFuturesPageService._empty_signal_activity_summary()

    @staticmethod
    def _empty_logic_evaluation() -> dict[str, Any]:
        empty_totals = {"tp": 0, "sl": 0, "open": 0, "win_rate": 0.0}
        return {
            "primary_rows": [],
            "confirmation_rows": [],
            "primary_totals": empty_totals,
            "confirmation_totals": empty_totals,
            "long_primary_rows": [],
            "long_confirmation_rows": [],
            "long_primary_totals": empty_totals,
            "long_confirmation_totals": empty_totals,
            "short_primary_rows": [],
            "short_confirmation_rows": [],
            "short_primary_totals": empty_totals,
            "short_confirmation_totals": empty_totals,
        }

    @staticmethod
    def _empty_signal_activity_summary() -> dict[str, Any]:
        return {
            "total_signals": 0,
            "buy_signals": 0,
            "short_signals": 0,
            "no_signal": 0,
            "theoretical_tp_hits": 0,
            "theoretical_sl_hits": 0,
            "theoretical_open_signals": 0,
            "signal_win_rate": 0.0,
        }

    def _build_recent_signals_section(
        self,
        signal_rows: list[dict[str, Any]],
        denied_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        adapted_denied_rows = [
            {
                "signal": {
                    "timestamp_ms": row.get("timestamp_ms"),
                    "timeframe": row.get("timeframe"),
                    "side": row.get("signal_side"),
                },
                "denial_reason": row.get("reason"),
                "live_entry_price": row.get("entry_price"),
                "timestamp_ms": row.get("timestamp_ms"),
            }
            for row in denied_rows
            if isinstance(row, dict)
        ]
        recent_signals = sorted(
            signal_rows,
            key=lambda row: self._content_service.normalized_signal_timestamp_ms(row) or 0,
            reverse=True,
        )
        recent_denied = sorted(
            adapted_denied_rows,
            key=self._denied_timestamp_ms,
            reverse=True,
        )
        return self._content_service.build_recent_signals_section(
            recent_signals=recent_signals,
            denied_rows=recent_denied,
            title="Recent Signal Decisions",
            intro="Full futures signal history with execution result and reason.",
        )

    def _denied_timestamp_ms(self, row: dict[str, Any]) -> int:
        raw_signal = row.get("signal")
        signal = raw_signal if isinstance(raw_signal, dict) else {}
        timestamp_ms = self._content_service.normalized_signal_timestamp_ms(signal)
        if timestamp_ms is None:
            timestamp_ms = self._content_service.parse_int(row.get("timestamp_ms"))
        return int(timestamp_ms or 0)

    def _load_latest_family_dict(self, family_name: str) -> tuple[str, dict[str, Any] | None]:
        payload = load_latest_document(family_name)
        return (f"database:{family_name}", payload) if isinstance(payload, dict) else ("No data", None)

    def _load_all_family_rows(self, family_name: str) -> tuple[str, list[dict[str, Any]]]:
        rows = load_family_rows_all(family_name)
        return (f"database:{family_name}:history" if rows else "No data"), rows
