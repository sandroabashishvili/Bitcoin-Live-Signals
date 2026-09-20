"""Render the static Orderbook page from normalized payload data."""

from __future__ import annotations

import html
import json
from typing import Any

from platform_v2.spot.dashboard.explanation_system import (
    load_explanation_map,
    render_explanation_anchor,
    render_explanation_host,
    render_explanation_payload,
)
from platform_v2.shared.frontend.components import (
    metric_value_class,
    render_page_head,
    render_runtime_clock_script,
    render_runtime_hero,
    render_site_footer,
    render_site_navigation,
)


class OrderbookPageRenderer:
    """Render the Orderbook page from a prepared payload."""

    def render(self, payload: dict[str, Any]) -> str:
        status_summary = payload.get("status_summary") or {}
        history_section = payload["orderflow_history_section"]
        chart_rows_json = json.dumps(payload.get("orderflow_chart_rows") or [], ensure_ascii=True).replace("</", "<\\/")
        status_line = (
            f"Updated {self._escape(payload['generated_at'])} · "
            f"Timeframe {self._escape(payload['timeframe'])} · "
            f"Snapshots {self._escape(status_summary.get('snapshots', 0))} · "
            f"Net Δ {self._escape(status_summary.get('net_delta', '—'))}"
        )
        explanation_payload = render_explanation_payload(self._explanations_for_prefix("orderbook."))
        return f"""<!DOCTYPE html>
<!-- ssh-generator: orderbook.py.renderer.v2026-04-11a -->
<html lang="en">
  <head>
{render_page_head(
    title="Bitcoin Orderflow And Trade Pressure | SmartSignalHub",
    description="Bitcoin orderflow pressure, delta, imbalance, and recent buy-versus-sell flow snapshots for SmartSignalHub.",
    canonical_path="/spot/dashboard/orderbook/index.html",
    css_href="./css/styles.css",
    favicon_prefix="../../../public_site/",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    og_description="Monitor Bitcoin orderflow pressure, delta, imbalance, and recent buy-versus-sell flow shifts inside SmartSignalHub.",
    twitter_description="Monitor Bitcoin orderflow pressure, delta, imbalance, and recent buy-versus-sell flow shifts inside SmartSignalHub.",
    schema_json_ld="""      {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/orderbook/#webpage",
        "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/orderbook/",
        "name": "Bitcoin Orderflow And Trade Pressure | SmartSignalHub",
        "description": "Bitcoin orderflow pressure, delta, imbalance, and recent buy-versus-sell flow snapshots for SmartSignalHub.",
        "isPartOf": {
          "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization"
        },
        "about": {
          "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization"
        }
      }""",
)}
  </head>
  <body>
    <main class="page">
      <header class="page-chrome">
        {self._render_hero()}
        {self._render_navigation()}
      </header>
      {self._render_kpi_section(payload.get("orderflow_snapshot_items") or [])}
      {self._render_history_section(history_section)}
      {self._render_chart_section()}
    </main>
      {render_site_footer()}
    {explanation_payload}
    {render_explanation_host(base_prefix="../")}
    <script>window.__ORDERBOOK_ROWS__ = {chart_rows_json};</script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script type="module" src="../../../shared/frontend/charts/orderflow_delta_chart.js"></script>
    {render_runtime_clock_script()}
    {self._render_table_script()}
  </body>
</html>
"""

    @staticmethod
    def _escape(value: Any) -> str:
        return html.escape(str(value))

    @staticmethod
    def _value_class(value: Any, *, kind: str = "generic") -> str:
        return metric_value_class(value, kind=kind)

    def _strong(self, value: Any, *, kind: str = "generic") -> str:
        klass = self._value_class(value, kind=kind)
        safe = self._escape(value if value not in (None, "") else "—")
        if klass:
            return f'<strong class="{klass}">{safe}</strong>'
        return f"<strong>{safe}</strong>"

    @staticmethod
    def _explanations_for_prefix(prefix: str) -> dict[str, Any]:
        return {key: item for key, item in load_explanation_map().items() if key.startswith(prefix)}

    @staticmethod
    def _render_panel_heading(title: str, explanation_key: str) -> str:
        return (
            f'<h2 class="panel-title-with-action"><span>{html.escape(title)}</span>'
            f'{render_explanation_anchor(key=explanation_key, label_html="")}</h2>'
        )

    def _render_kpi_section(self, items: list[dict[str, Any]]) -> str:
        cards_html = "".join(
            f'<div class="metric-card"><span>{self._escape(item.get("label", "—"))}</span>{self._strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))}</div>'
            for item in items
        )
        return f"""
      <section class="panel panel-wide">
        <div class="panel-head">
          {self._render_panel_heading("Orderflow Snapshot", "orderbook.snapshot.panel")}
        </div>
        <p class="panel-intro">Recent flow pressure, cumulative delta, and latest buy/sell imbalance.</p>
        <div class="kpi-grid">
          {cards_html}
        </div>
      </section>
"""

    def _render_history_section(self, section: dict[str, Any]) -> str:
        return f"""
      <section class="panel runtime-panel">
        <div class="panel-head">
          {self._render_panel_heading(
              str(section.get("title", "Orderflow History")),
              "orderbook.history.panel",
          )}
          <span class="badge neutral">{self._escape(section.get('badge', 0))}</span>
        </div>
        <p class="panel-intro">{self._escape(section.get('intro', ''))}</p>
        <div class="table-shell">
          {self._render_table(section)}
        </div>
      </section>
"""

    def _render_chart_section(self) -> str:
        return f"""
      <section class="panel panel-wide chart-panel">
        <div class="panel-head">
          {self._render_panel_heading("Orderflow Delta Chart", "orderbook.delta_chart.panel")}
        </div>
        <p class="panel-intro">Net delta bars and cumulative delta line across same-day orderflow snapshots.</p>
        <div class="chart-shell">
          <div id="orderflow-delta-chart" class="chart-canvas" aria-label="Orderflow delta chart"></div>
        </div>
      </section>
"""

    def _render_table(self, section: dict[str, Any]) -> str:
        rows = list(section.get("rows") or [])
        if not rows:
            return f'<div class="stack-list empty">{self._escape(section.get("empty_text", "No orderbook snapshots recorded yet."))}</div>'
        head = "".join(f"<th>{self._escape(header)}</th>" for header in list(section.get("headers") or []))
        return f"""
        <div class="table-controls" data-orderbook-table>
          <div class="table-controls-group">
            <button class="table-control-button" type="button" data-orderbook-back>Back</button>
            <button class="table-control-button" type="button" data-orderbook-next>Next</button>
          </div>
        </div>
        <table class="runtime-table">
          <thead>
            <tr>{head}</tr>
          </thead>
          <tbody data-orderbook-body></tbody>
        </table>
        """

    @staticmethod
    def _render_hero() -> str:
        return render_runtime_hero(
            title="Bitcoin Spot Orderflow Pressure And Market Depth",
            href="../orderbook/index.html",
            intro="",
            subline=None,
        )

    @staticmethod
    def _render_navigation() -> str:
        return render_site_navigation(active_page="orderbook")

    @staticmethod
    def _render_table_script() -> str:
        return """
    <script>
      (() => {
        const shell = document.querySelector('[data-orderbook-table]');
        const body = document.querySelector('[data-orderbook-body]');
        const backButton = document.querySelector('[data-orderbook-back]');
        const nextButton = document.querySelector('[data-orderbook-next]');
        if (!shell || !body || !backButton || !nextButton) {
          return;
        }

        const rows = Array.isArray(window.__ORDERBOOK_ROWS__) ? window.__ORDERBOOK_ROWS__ : [];
        const pageSize = 5;
        let pageIndex = 0;
        const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));

        const classMap = {
          bullish: 'green',
          bearish: 'red',
          neutral: 'neutral',
        };

        const valueClass = (value, kind) => {
          if (kind === 'buy') return 'value-green';
          if (kind === 'sell') return 'value-red';
          const number = Number(value);
          if (Number.isNaN(number)) return 'value-muted';
          if (number > 0) return 'value-green';
          if (number < 0) return 'value-red';
          return 'value-muted';
        };

        const render = () => {
          const start = pageIndex * pageSize;
          const end = Math.min(start + pageSize, rows.length);
          const visible = rows.slice(start, end);
          body.innerHTML = visible.map((row) => `
            <tr>
              <td>${row.timestamp_text}</td>
              <td><strong class="${valueClass(row.buyers, 'buy')}">${row.buyers}</strong></td>
              <td><strong class="${valueClass(row.sellers, 'sell')}">${row.sellers}</strong></td>
              <td><strong class="${valueClass(row.delta, 'delta')}">${row.delta}</strong></td>
              <td><strong class="${valueClass(row.cumulative_delta, 'delta')}">${row.cumulative_delta}</strong></td>
              <td><strong class="orderbook-class-text value-${classMap[row.momentum_classification] || 'neutral'}">${row.momentum_classification}</strong></td>
            </tr>
          `).join('');
          backButton.disabled = pageIndex === 0;
          nextButton.disabled = pageIndex >= pageCount - 1;
        };

        backButton.addEventListener('click', () => {
          if (pageIndex > 0) {
            pageIndex -= 1;
            render();
          }
        });

        nextButton.addEventListener('click', () => {
          if (pageIndex < pageCount - 1) {
            pageIndex += 1;
            render();
          }
        });

        render();
      })();
    </script>
"""
