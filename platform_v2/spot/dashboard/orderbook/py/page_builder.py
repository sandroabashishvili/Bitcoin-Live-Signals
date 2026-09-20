"""File: page_builder.py
Folder: platform_v2/public_site/orderbook/py
Created date: 2026-03-28
Last updated date: 2026-03-28
Author: Codex
Purpose: Build a static SEO-friendlier Orderbook page from V2 runtime data.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from platform_v2.spot.config import settings
from platform_v2.spot.dashboard.orderbook.py.renderer import OrderbookPageRenderer
from platform_v2.spot.services.metrics_system import OrderbookPageContentService
from platform_v2.spot.storage.paths import orderflow_file_path
from platform_v2.shared.backend.runtime_store.spot import load_json_list
from platform_v2.shared.backend.persistence import read_market_series_safely


class OrderbookPageService:
    """Generate a static HTML orderbook page from current V2 runtime data."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"

    def build_and_store(self, *, symbol: str = settings.DEFAULT_SYMBOL, timeframe: str = settings.DEFAULT_TIMEFRAME) -> Path:
        """Build and persist the Orderbook HTML page."""

        payload = self._load_payload(symbol=symbol, timeframe=timeframe)
        html_text = OrderbookPageRenderer().render(payload)
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        return self._TARGET_PATH

    def _load_payload(self, *, symbol: str, timeframe: str) -> dict[str, Any]:
        path = orderflow_file_path(symbol, timeframe)
        rows = self._load_rows(path)
        page_content = OrderbookPageContentService().build_page_content(
            rows=rows,
            symbol=symbol,
            timeframe=timeframe,
        )
        return {
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "source_file": "database:spot/orderflow" if rows else "No data",
            "orderflow_snapshot_items": page_content.get("orderflow_snapshot_items") or [],
            "orderflow_history_section": page_content.get("orderflow_history_section") or {},
            "orderflow_chart_rows": page_content.get("orderflow_chart_rows") or [],
            "status_summary": page_content.get("status_summary") or {},
            "timeframe": str(page_content.get("timeframe") or timeframe),
            **page_content,
        }

    @staticmethod
    def _load_rows(path: Path) -> list[dict[str, Any]]:
        rows = read_market_series_safely(
            venue="binance",
            asset_class="crypto",
            market_type="spot",
            dataset="orderflow",
            symbol=path.parent.name,
            timeframe=path.stem,
        )
        return rows or load_json_list(path)
