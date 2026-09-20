"""Build Futures Trade Outcomes page from futures runtime data."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from platform_v2.shared.backend.runtime_store.futures import (
    TRADE_GATE_EFFECTIVENESS_REPORTS_FAMILY,
    load_family_rows_all,
    load_latest_document,
)
from platform_v2.futures.services.analytics.futures_strategy_effectiveness import (
    ClosedTradeLogicEvaluationPayload,
)
from platform_v2.futures.services.metrics_system.grouped_payloads import build_portfolio_trade_outcome_items
from platform_v2.futures.services.metrics_system.strategy_content import StrategyPageContentService

from .renderer import TradeOutcomesFuturesPageRenderer


class TradeOutcomesFuturesPageService:
    """Generate a static HTML futures trade outcomes page from futures runtime data."""

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
        html_text = TradeOutcomesFuturesPageRenderer().render(payload)
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
        metrics_file, metrics = self._load_latest_family_dict("futures_metrics")
        signals_file, signal_rows = self._load_all_family_rows("futures_signals")
        positions_file, position_rows = self._load_all_family_rows("futures_position_events")
        gate_report_file, gate_report = self._load_latest_family_dict(TRADE_GATE_EFFECTIVENESS_REPORTS_FAMILY)
        metrics_data: dict[str, Any] = metrics if isinstance(metrics, dict) else {}
        logic_evaluation = self._logic_evaluation_from_report(gate_report)
        typed_logic_evaluation = cast(ClosedTradeLogicEvaluationPayload, logic_evaluation)
        logic_tables_section = self._content_service.build_trade_outcomes_logic_tables_section(
            typed_logic_evaluation
        )

        return {
            "generated_at": datetime.now(tz=UTC).strftime("%d.%m.%Y %H:%M:%S UTC"),
            "signals_file": signals_file,
            "positions_file": positions_file,
            "metrics_file": metrics_file,
            "gate_report_file": gate_report_file,
            "metrics": metrics_data,
            "strategy_outcome_items": build_portfolio_trade_outcome_items(metrics_data),
            "logic_tables_section": logic_tables_section,
            "logic_chart_payload": {**logic_evaluation, "chart_mode": "outcomes"},
        }

    @staticmethod
    def _logic_evaluation_from_report(report: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(report, dict):
            return TradeOutcomesFuturesPageService._empty_closed_trade_logic_evaluation()
        payload = report.get("trade_outcomes_logic_evaluation")
        return payload if isinstance(payload, dict) else TradeOutcomesFuturesPageService._empty_closed_trade_logic_evaluation()

    @staticmethod
    def _empty_closed_trade_logic_evaluation() -> dict[str, Any]:
        empty_totals = {"tp": 0, "sl": 0, "profit_lock": 0, "force_close": 0, "wins": 0, "participated": 0, "win_rate": 0.0}
        empty_summary = {
            "closed_positions": 0,
            "tp_hits": 0,
            "sl_hits": 0,
            "profit_lock_hits": 0,
            "force_close_events": 0,
            "win_rate": 0.0,
            "avg_net_per_trade": 0.0,
        }
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
            "closed_trade_summary": empty_summary,
        }

    def _load_latest_family_dict(self, family_name: str) -> tuple[str, dict[str, Any] | None]:
        payload = load_latest_document(family_name)
        return (f"database:{family_name}", payload) if isinstance(payload, dict) else ("No data", None)

    def _load_all_family_rows(self, family_name: str) -> tuple[str, list[dict[str, Any]]]:
        rows = load_family_rows_all(family_name)
        return (f"database:{family_name}:history" if rows else "No data"), rows
