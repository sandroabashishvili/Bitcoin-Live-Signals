"""File: page_builder.py
Folder: platform_v2/futures/dashboard/portfolio_futures/py
Created date: 2026-05-25
Last updated date: 2026-06-02
Author: Codex
Purpose: Build Futures Portfolio page from futures runtime data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    POSITIONS_FAMILY,
    load_family_rows_all,
    load_latest_document,
)
from platform_v2.futures.services.metrics_system import (
    PortfolioPageContentService,
    build_portfolio_capital_snapshot_items,
)

from .renderer import PortfolioFuturesPageRenderer


class PortfolioFuturesPageService:
    """Generate a static HTML Futures portfolio page from futures runtime data."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"
    _SOURCE_CSS_PATH = Path(__file__).resolve().parents[1] / "css" / "styles.css"
    _TARGET_CSS_PATH = _TARGET_DIR / "css" / "styles.css"

    def build_and_store(self) -> Path:
        payload = self._load_payload()
        html_text = PortfolioFuturesPageRenderer().render(payload)
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
        metrics_file, metrics = self._load_latest_metrics()
        positions_file, position_rows, position_file_count = self._load_futures_positions_history()
        orders_file, orders, order_file_count = self._load_family_history("futures_orders")
        metrics_dict = metrics if isinstance(metrics, dict) else {}
        positions_content = PortfolioPageContentService().build_positions_content(position_rows=position_rows)

        return {
            "generated_at": datetime.now(tz=UTC).strftime("%d.%m.%Y %H:%M:%S UTC"),
            "metrics_file": metrics_file,
            "positions_file": positions_file,
            "orders_file": orders_file,
            "position_file_count": position_file_count,
            "order_file_count": order_file_count,
            "metrics": metrics_dict,
            "open_positions_section": positions_content.get("open_positions_section") or {},
            "closed_positions_section": positions_content.get("closed_positions_section") or {},
            "closed_trade_chart_rows": positions_content.get("closed_trade_chart_rows") or [],
            "capital_snapshot_items": build_portfolio_capital_snapshot_items(metrics_dict),
            "orders_total": len(orders),
            **positions_content,
        }

    def _load_latest_metrics(self) -> tuple[str, dict[str, Any] | None]:
        payload = load_latest_document("futures_metrics")
        return ("database:futures_metrics", payload) if isinstance(payload, dict) else ("No data", None)

    def _load_family_history(self, family_name: str) -> tuple[str, list[dict[str, Any]], int]:
        rows = load_family_rows_all(family_name)
        return (f"database:{family_name}" if rows else "No data"), rows, int(bool(rows))

    def _load_futures_positions_history(self) -> tuple[str, list[dict[str, Any]], int]:
        rows = load_family_rows_all(POSITIONS_FAMILY)
        if not rows:
            return "No data", [], 0
        rows.sort(key=self._position_sort_key)
        return "database:futures_position_events", rows, 1

    @staticmethod
    def _position_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(row.get("opened_at") or ""),
            str(row.get("closed_at") or ""),
            str(row.get("position_id") or ""),
        )
