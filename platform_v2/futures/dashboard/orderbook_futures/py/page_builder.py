"""Build Futures Orderbook page from futures runtime data."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_v2.futures.config import settings
from platform_v2.futures.storage import load_json_list, orderflow_file_path
from platform_v2.futures.services.metrics_system import OrderbookPageContentService

from .renderer import OrderbookFuturesPageRenderer


class OrderbookFuturesPageService:
    """Generate a static HTML futures orderbook page from futures runtime data."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"
    _SOURCE_CSS_PATH = Path(__file__).resolve().parents[1] / "css" / "styles.css"
    _TARGET_CSS_PATH = _TARGET_DIR / "css" / "styles.css"

    def build_and_store(
        self,
        *,
        symbol: str = settings.DEFAULT_SYMBOL,
        timeframe: str = settings.DEFAULT_TIMEFRAME,
    ) -> Path:
        payload = self._load_payload(symbol=symbol, timeframe=timeframe)
        html_text = OrderbookFuturesPageRenderer().render(payload)
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

    def _load_payload(self, *, symbol: str, timeframe: str) -> dict[str, Any]:
        path = orderflow_file_path(symbol, timeframe)
        rows = self._load_rows(path)
        page_content = OrderbookPageContentService().build_page_content(
            rows=rows,
            symbol=symbol,
            timeframe=timeframe,
        )
        return {
            "generated_at": datetime.now(tz=UTC).strftime("%d.%m.%Y %H:%M:%S UTC"),
            "source_file": "database:futures/orderflow" if rows else "No data",
            "orderflow_snapshot_items": page_content.get("orderflow_snapshot_items") or [],
            "orderflow_history_section": page_content.get("orderflow_history_section") or {},
            "orderflow_chart_rows": page_content.get("orderflow_chart_rows") or [],
            "status_summary": page_content.get("status_summary") or {},
            "timeframe": str(page_content.get("timeframe") or timeframe),
            **page_content,
        }

    @staticmethod
    def _load_rows(path: Path) -> list[dict[str, Any]]:
        return load_json_list(path)
