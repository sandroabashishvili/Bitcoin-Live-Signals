"""File: page_builder.py
Folder: platform_v2/public_site/portfolio/py
Created date: 2026-03-28
Last updated date: 2026-03-29
Author: Codex
Purpose: Build a static SEO-friendlier Portfolio page from V2 runtime data.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from platform_v2.spot.dashboard.portfolio.py.renderer import PortfolioPageRenderer
from platform_v2.spot.services.metrics_system import (
    PortfolioPageContentService,
    build_portfolio_capital_snapshot_items,
)
from platform_v2.shared.backend.runtime_store.spot import load_family_rows_all, load_latest_document


class PortfolioPageService:
    """Generate a static HTML portfolio page from current V2 runtime data."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"

    def build_and_store(self) -> Path:
        payload = self._load_payload()
        html_text = PortfolioPageRenderer().render(payload)
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        return self._TARGET_PATH

    def _load_payload(self) -> dict[str, Any]:
        metrics_file, metrics = self._load_latest_family("metrics")
        positions_file, position_rows, position_file_count = self._load_family_history("positions")
        orders_file, orders, order_file_count = self._load_family_history("orders")
        metrics_dict = metrics if isinstance(metrics, dict) else {}
        positions_content = PortfolioPageContentService().build_positions_content(position_rows=position_rows)

        return {
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
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

    def _load_latest_family(self, family_name: str) -> tuple[str, list[dict[str, Any]] | dict[str, Any] | None]:
        payload = load_latest_document(family_name)
        return (f"database:{family_name}", payload) if payload is not None else ("No data", None)

    def _load_family_history(self, family_name: str) -> tuple[str, list[dict[str, Any]], int]:
        rows = load_family_rows_all(family_name)
        if family_name == "positions":
            rows.sort(key=self._position_sort_key)
        return (f"database:{family_name}" if rows else "No data"), rows, int(bool(rows))

    @staticmethod
    def _position_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(row.get("opened_at") or ""),
            str(row.get("closed_at") or ""),
            str(row.get("position_id") or ""),
        )
