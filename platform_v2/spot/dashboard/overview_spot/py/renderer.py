"""Render the static Overview page from normalized payload data."""

from __future__ import annotations

import json
from typing import Any

from platform_v2.spot.dashboard.explanation_system import render_explanation_host, render_explanation_payload
from platform_v2.spot.dashboard.overview_spot.py.explanations import build_overview_explanations
from platform_v2.spot.dashboard.overview_spot.py.formatting import (
    baseline_strong as format_baseline_strong,
    escape as format_escape,
    fmt_number as format_number,
    strong as format_strong,
    value_class as format_value_class,
)
from platform_v2.spot.dashboard.overview_spot.py.sections import render_footer_status, render_hero, render_main_grid, render_navigation, render_site_footer
from platform_v2.spot.dashboard.overview_spot.py.snapshot_renderers import (
    render_portfolio_snapshot as render_portfolio_snapshot_html,
    render_primary_signal as render_primary_signal_html,
    render_strategy_snapshot as render_strategy_snapshot_html,
    render_trade_outcomes_snapshot as render_trade_outcomes_snapshot_html,
)
from platform_v2.shared.frontend.components import render_page_head, render_runtime_clock_script


class OverviewPageRenderer:
    """Render the Overview page from a prepared payload."""

    def render(self, payload: dict[str, Any]) -> str:
        runtime_health = payload.get("runtime_health") or {}
        metrics_history_json = json.dumps(payload.get("equity_chart_rows") or [], ensure_ascii=True).replace("</", "<\\/")
        explanation_payload = render_explanation_payload(build_overview_explanations(payload).as_dict())
        status_line = (
            f"Updated {self.escape(payload['generated_at'])} · "
            f"Candles {self.escape(runtime_health.get('candles', '—'))} · "
            f"Indicators {self.escape(runtime_health.get('indicators', '—'))} · "
            f"Orderflow {self.escape(runtime_health.get('orderbook', '—'))}"
        )
        return f"""<!DOCTYPE html>
<!-- ssh-generator: overview.py.renderer.v2026-03-29a -->
<html lang="en">
  <head>
{render_page_head(
    title="Bitcoin Live Signals | SmartSignalHub",
    description="Bitcoin Live Signals by SmartSignalHub with live signal context, multi-timeframe analysis, daily runtime summary, and portfolio snapshot.",
    canonical_path="/spot/dashboard/overview_spot/index.html",
    css_href="./css/styles.css",
    favicon_prefix="../../../public_site/",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    og_description="Real-time Bitcoin trade signals with TP/SL, multi-timeframe context, and transparent performance tracking.",
    twitter_description="Real-time Bitcoin trade signals with TP/SL, multi-timeframe context, and transparent performance tracking.",
    schema_json_ld="""      {
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "Organization",
            "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization",
            "name": "SmartSignalHub",
            "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/overview_spot/",
            "description": "Bitcoin signal tracking system with live signal context, spot-only execution, TP/SL planning, and transparent runtime tracking."
          },
          {
            "@type": "WebPage",
            "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/overview_spot/#webpage",
            "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/overview_spot/",
            "name": "Bitcoin Live Signals | SmartSignalHub",
            "description": "Bitcoin Live Signals by SmartSignalHub with live signal context, multi-timeframe analysis, daily runtime summary, and portfolio snapshot.",
            "isPartOf": {
              "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization"
            },
            "about": {
              "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization"
            }
          }
        ]
      }""",
)}
  </head>
  <body>
    <main class="page">
      <header class="page-chrome">
        {render_hero(status_line=status_line)}
        {render_navigation()}
      </header>
      {render_main_grid(self, payload, mtf_direction="NO_SIGNAL")}
      {render_footer_status(status_line=status_line)}
    </main>
    {render_site_footer()}
    {explanation_payload}
    {render_explanation_host(base_prefix="../")}
    <script>window.__SSH_OVERVIEW_EQUITY__ = {metrics_history_json};</script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script type="module" src="../../../shared/frontend/charts/equity_delta_chart.js"></script>
    {render_runtime_clock_script()}
  </body>
</html>
"""

    @staticmethod
    def escape(value: Any) -> str:
        return format_escape(value)

    @staticmethod
    def fmt_number(value: Any, digits: int = 2) -> str:
        return format_number(value, digits)

    @staticmethod
    def value_class(value: Any, *, kind: str = "generic") -> str:
        return format_value_class(value, kind=kind)

    def strong(self, value: Any, *, kind: str = "generic") -> str:
        return format_strong(value, kind=kind)

    def baseline_strong(self, value: Any, baseline: Any) -> str:
        return format_baseline_strong(value, baseline)

    def render_trade_outcomes_snapshot(self, payload: dict[str, Any]) -> str:
        return render_trade_outcomes_snapshot_html(payload)

    def render_primary_signal(self, payload: dict[str, Any]) -> str:
        return render_primary_signal_html(payload)

    def render_strategy_snapshot(self, payload: dict[str, Any]) -> str:
        return render_strategy_snapshot_html(payload)

    def render_portfolio_snapshot(self, payload: dict[str, Any]) -> str:
        return render_portfolio_snapshot_html(payload)
