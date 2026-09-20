"""Build a static SEO-friendlier Strategy Edge page from V2 runtime data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

from platform_v2.spot.dashboard.strategy_edge.py.renderer import StrategyEdgePageRenderer
from platform_v2.spot.services.analytics.strategy_effectiveness import (
    LogicEvaluationPayload,
    SignalActivitySummary,
    StrategyEffectivenessService,
)
from platform_v2.spot.services.metrics_system.strategy_content import (
    StrategyActivityPageContentService,
)
from platform_v2.shared.backend.runtime_store.spot import load_family_rows_all, load_latest_document


class StrategyEdgePageService:
    """Generate a static HTML strategy edge page from current V2 runtime data."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"
    _effectiveness_service: StrategyEffectivenessService
    _content_service: StrategyActivityPageContentService

    def __init__(
        self,
        effectiveness_service: StrategyEffectivenessService | None = None,
        content_service: StrategyActivityPageContentService | None = None,
    ) -> None:
        self._effectiveness_service = effectiveness_service or StrategyEffectivenessService()
        self._content_service = cast(
            StrategyActivityPageContentService,
            content_service or StrategyActivityPageContentService(),
        )

    def build_and_store(self) -> Path:
        payload = self._load_payload()
        html_text = StrategyEdgePageRenderer().render(payload)
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        return self._TARGET_PATH

    def _load_payload(self) -> dict[str, Any]:
        signals_file, signals = self._load_all_family_rows("signals")
        denied_file, denied_entries = self._load_all_family_rows("denied_entries")
        signal_rows: list[dict[str, Any]] = signals if isinstance(signals, list) else []
        denied_rows: list[dict[str, Any]] = denied_entries if isinstance(denied_entries, list) else []
        logic_evaluation: LogicEvaluationPayload = self._effectiveness_service.build_logic_evaluation(
            signal_rows
        )
        signal_activity_summary: SignalActivitySummary = self._effectiveness_service.build_signal_activity_summary(
            signal_rows
        )
        content_service: StrategyActivityPageContentService = self._content_service
        content_payload: dict[str, Any] = {
            "signal_rows": signal_rows,
            "denied_rows": denied_rows,
            "signal_activity_summary": signal_activity_summary,
            "logic_evaluation": logic_evaluation,
        }
        page_content: dict[str, Any] = content_service.build_page_content(content_payload)
        return {
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "signals_file": signals_file,
            "denied_file": denied_file,
            "logic_chart_payload": page_content.get("logic_chart_payload") or {},
            "logic_tables_section": page_content.get("logic_tables_section") or {},
            "recent_signals_section": page_content.get("recent_signals_section") or {},
            "strategy_activity_items": page_content.get("strategy_activity_items") or [],
            "strategy_activity_summary": page_content.get("strategy_activity_summary") or {},
            **page_content,
        }

    def _load_latest_family(self, family_name: str) -> tuple[str, list[dict[str, Any]] | None]:
        payload = load_latest_document(family_name)
        rows = [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else None
        return (f"database:{family_name}" if rows is not None else "No data"), rows

    def _load_all_family_rows(self, family_name: str) -> tuple[str, list[dict[str, Any]]]:
        rows = load_family_rows_all(family_name)
        return (f"database:{family_name}:history" if rows else "No data"), rows
