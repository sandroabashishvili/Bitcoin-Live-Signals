"""Render and store Futures Hedge overview from prepared backend content."""

from __future__ import annotations

from pathlib import Path

from platform_v2.futures_hedge.services.overview_content import FuturesHedgeOverviewContentService
from platform_v2.shared.frontend.components import normalize_generated_html

from .renderer import FuturesHedgeOverviewRenderer


class FuturesHedgeOverviewPageService:
    """Generate a static HTML Futures Hedge overview page."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"

    def __init__(self, content_service: FuturesHedgeOverviewContentService | None = None) -> None:
        self._content_service = (
            content_service if content_service is not None else FuturesHedgeOverviewContentService()
        )

    def build_and_store(self) -> Path:
        report = self._content_service.build_page_content()
        html_text = normalize_generated_html(FuturesHedgeOverviewRenderer().render(report))
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        return self._TARGET_PATH
