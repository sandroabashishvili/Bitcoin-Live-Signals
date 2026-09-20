"""File: page_builder.py
Folder: platform_v2/public_site/trade_outcomes/py
Created date: 2026-03-28
Last updated date: 2026-04-11
Author: Codex
Purpose: Build a static SEO-friendlier Trade Outcomes page from V2 runtime data.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from platform_v2.spot.dashboard.trade_outcomes.py.renderer import TradeOutcomesPageRenderer
from platform_v2.spot.services.account.position_state_service import PositionStateService
from platform_v2.spot.services.analytics.strategy_effectiveness import (
    ClosedTradeLogicEvaluationPayload,
    StrategyEffectivenessService,
)
from platform_v2.spot.services.metrics_system.grouped_payloads import build_portfolio_trade_outcome_items
from platform_v2.spot.services.metrics_system.strategy_content import StrategyPageContentService
from platform_v2.shared.backend.runtime_store.spot import load_family_rows_all, load_latest_document


class TradeOutcomesPageService:
    """Generate a static HTML trade outcomes page from current V2 runtime data."""

    _TARGET_DIR = Path(__file__).resolve().parents[2] / "trade_outcomes"
    _TARGET_PATH = _TARGET_DIR / "index.html"

    def __init__(
        self,
        effectiveness_service: StrategyEffectivenessService | None = None,
        content_service: StrategyPageContentService | None = None,
        position_state_service: PositionStateService | None = None,
    ) -> None:
        self._effectiveness_service = effectiveness_service or StrategyEffectivenessService()
        self._content_service = content_service or StrategyPageContentService()
        self._position_state_service = position_state_service or PositionStateService()

    def build_and_store(self) -> Path:
        payload = self._load_payload()
        html_text = TradeOutcomesPageRenderer().render(payload)
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        return self._TARGET_PATH

    def _load_payload(self) -> dict[str, Any]:
        signals_file, signals = self._load_all_family_rows("signals")
        metrics_file, metrics = self._load_latest_family("metrics")

        signal_rows: list[dict[str, Any]] = signals if isinstance(signals, list) else []
        metrics_data: dict[str, Any] = metrics if isinstance(metrics, dict) else {}
        closed_positions = [position for position in self._position_state_service.load_latest_positions() if position.is_closed]
        logic_evaluation: ClosedTradeLogicEvaluationPayload = self._effectiveness_service.build_closed_trade_logic_evaluation(
            signal_rows=signal_rows,
            closed_positions=closed_positions,
        )
        logic_evaluation["closed_trade_summary"] = {
            "closed_positions": int(metrics_data.get("closed_positions", 0)),
            "tp_hits": int(metrics_data.get("tp_hits", 0)),
            "sl_hits": int(metrics_data.get("sl_hits", 0)),
            "profit_lock_hits": int(metrics_data.get("profit_lock_hits", 0)),
            "force_close_events": int(metrics_data.get("force_close_events", 0)),
            "win_rate": float(metrics_data.get("win_rate", 0.0)),
            "avg_net_per_trade": float(metrics_data.get("avg_net_per_trade", 0.0)),
        }
        return {
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "signals_file": signals_file,
            "positions_file": "latest_state_positions",
            "metrics_file": metrics_file,
            "metrics": metrics_data,
            "strategy_outcome_items": build_portfolio_trade_outcome_items(metrics_data),
            "logic_tables_section": self._content_service.build_trade_outcomes_logic_tables_section(
                logic_evaluation
            ),
            "logic_chart_payload": {**logic_evaluation, "chart_mode": "outcomes"},
        }

    def _load_latest_family(self, family_name: str) -> tuple[str, list[dict[str, Any]] | dict[str, Any] | None]:
        payload = load_latest_document(family_name)
        return (f"database:{family_name}", payload) if payload is not None else ("No data", None)

    def _load_all_family_rows(self, family_name: str) -> tuple[str, list[dict[str, Any]]]:
        rows = load_family_rows_all(family_name)
        return (f"database:{family_name}:history" if rows else "No data"), rows
