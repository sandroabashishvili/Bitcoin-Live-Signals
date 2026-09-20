"""File: renderer.py
Folder: platform_v2/public_site/portfolio/py
Created date: 2026-03-28
Last updated date: 2026-03-29
Author: Codex
Purpose: Render the static V2 Portfolio page from normalized payload data.
"""

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


class PortfolioPageRenderer:
    """Render the Portfolio page from a prepared payload."""

    def render(self, payload: dict[str, Any]) -> str:
        metrics = payload["metrics"] or {}
        capital_snapshot_items = payload.get("capital_snapshot_items") or []
        open_positions_section = payload["open_positions_section"]
        closed_positions_section = payload["closed_positions_section"]
        closed_chart_json = json.dumps(payload.get("closed_trade_chart_rows") or [], ensure_ascii=True).replace("</", "<\\/")

        explanation_payload = render_explanation_payload(self._explanations_for_prefix("portfolio."))
        return f"""<!DOCTYPE html>
<!-- ssh-generator: portfolio.py.renderer.v2026-03-29a -->
<html lang="en">
  <head>
{render_page_head(
    title="Bitcoin Portfolio And Positions | SmartSignalHub",
    description="Live Bitcoin capital state, open positions, confirmed exits, and realized portfolio outcomes inside SmartSignalHub.",
    canonical_path="/spot/dashboard/portfolio/index.html",
    css_href="./css/styles.css",
    favicon_prefix="../../../public_site/",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    og_description="Track capital state, open Bitcoin exposure, confirmed exits, and realized portfolio outcomes for SmartSignalHub.",
    twitter_description="Track capital state, open Bitcoin exposure, confirmed exits, and realized portfolio outcomes for SmartSignalHub.",
    schema_json_ld="""      {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/portfolio/#webpage",
        "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/portfolio/",
        "name": "Bitcoin Portfolio And Positions | SmartSignalHub",
        "description": "Live Bitcoin capital state, open positions, confirmed exits, and realized portfolio outcomes inside SmartSignalHub.",
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
        {self._render_hero(metrics)}
        {self._render_navigation()}
      </header>
      {self._render_portfolio_content(capital_snapshot_items=capital_snapshot_items, open_positions_section=open_positions_section, closed_positions_section=closed_positions_section)}
    </main>
    {render_site_footer()}
    {explanation_payload}
    {render_explanation_host(base_prefix="../")}
    <script>window.__SSH_PORTFOLIO_CLOSED__ = {closed_chart_json};</script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script type="module" src="../../../shared/frontend/charts/portfolio_pnl_charts.js"></script>
    {render_runtime_clock_script()}
    {self._render_table_pagination_script()}
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

    def _render_kpi_grid(self, items: tuple[tuple[str, str], ...]) -> str:
        return "".join(
            f'<div class="metric-card"><span>{self._escape(label)}</span>{value_html}</div>'
            for label, value_html in items
        )

    @staticmethod
    def _explanations_for_prefix(prefix: str) -> dict[str, Any]:
        return {key: item for key, item in load_explanation_map().items() if key.startswith(prefix)}

    @staticmethod
    def _render_panel_heading(title: str, explanation_key: str) -> str:
        return (
            f'<h2 class="panel-title-with-action"><span>{html.escape(title)}</span>'
            f'{render_explanation_anchor(key=explanation_key, label_html="")}</h2>'
        )

    def _render_metric_items(self, items: list[dict[str, Any]]) -> str:
        prepared: tuple[tuple[str, str], ...] = tuple(
            (
                self._escape(item.get("label", "—")),
                self._strong(item.get("value", "—"), kind=str(item.get("kind") or "generic")),
            )
            for item in items
        )
        return self._render_kpi_grid(prepared)

    def _render_capital_panel(self, items: list[dict[str, Any]]) -> str:
        return f"""
        <section class="panel panel-wide portfolio-panel portfolio-panel-capital">
          <div class="panel-head">
            {self._render_panel_heading("Capital Snapshot", "portfolio.capital_snapshot.panel")}
          </div>
          <p class="panel-intro">Live capital, realized results, reserved funds, and current exposure.</p>
          <div class="kpi-grid portfolio-kpi-grid portfolio-kpi-grid-capital">
            {self._render_metric_items(items)}
          </div>
        </section>
"""

    def _render_table(self, headers: list[Any], rows: list[Any], empty_text: str, *, table_id: str) -> str:
        if not rows:
            return f'<div class="stack-list empty">{self._escape(empty_text)}</div>'
        head = "".join(self._render_table_header_cell(header) for header in headers)
        body = "".join(self._render_table_row(row, column_count=len(headers)) for row in rows)
        return f"""
        <div class="table-controls" data-table-controls="{self._escape(table_id)}">
          <div class="table-controls-group">
            <button class="table-control-button" type="button" data-table-back="{self._escape(table_id)}">Back</button>
            <button class="table-control-button" type="button" data-table-next="{self._escape(table_id)}">Next</button>
          </div>
        </div>
        <table class="runtime-table">
          <thead><tr>{head}</tr></thead>
          <tbody data-table-body="{self._escape(table_id)}">{body}</tbody>
        </table>
        """

    def _render_table_row(self, row: Any, *, column_count: int) -> str:
        if not isinstance(row, dict):
            return f"<tr data-table-item>{''.join(f'<td>{cell}</td>' for cell in row)}</tr>"

        cells = list(row.get("cells") or [])
        details = list(row.get("details") or [])
        main_row = (
            '<tr class="expandable-table-row" data-table-item data-expandable-row tabindex="0" '
            'role="button" aria-expanded="false">'
            f"{''.join(f'<td>{cell}</td>' for cell in cells)}"
            "</tr>"
        )
        if not details:
            return main_row

        detail_items = "".join(
            '<div class="position-detail-item">'
            f'<span>{self._escape(item.get("label", "—"))}</span>'
            f'{self._strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))}'
            "</div>"
            for item in details
        )
        detail_row = (
            '<tr class="position-detail-row" data-detail-row hidden>'
            f'<td colspan="{max(1, column_count)}">'
            '<div class="position-detail-grid">'
            f"{detail_items}"
            "</div>"
            "</td>"
            "</tr>"
        )
        return main_row + detail_row

    def _render_table_header_cell(self, header: Any) -> str:
        if isinstance(header, dict):
            label = self._escape(header.get("label", "—"))
            explanation_key = str(header.get("explanation_key") or "").strip()
            if explanation_key:
                return (
                    '<th><span class="metric-label-with-action">'
                    f"<span>{label}</span>"
                    f'{render_explanation_anchor(key=explanation_key, label_html="")}'
                    "</span></th>"
                )
            return f"<th>{label}</th>"
        return f"<th>{self._escape(header)}</th>"

    def _render_hero(self, metrics: dict[str, Any]) -> str:
        return render_runtime_hero(
            title="Bitcoin Spot Portfolio Capital And Positions",
            href="../portfolio/",
            intro="",
            subline=None,
        )

    @staticmethod
    def _render_navigation() -> str:
        return render_site_navigation(active_page="portfolio")

    @staticmethod
    def _render_table_pagination_script() -> str:
        return """
    <script>
      (() => {
        const pageSize = 5;
        document.querySelectorAll('[data-table-body]').forEach((tbody) => {
          const tableId = tbody.getAttribute('data-table-body');
          const rows = Array.from(tbody.querySelectorAll('tr[data-table-item]'));
          const backButton = document.querySelector(`[data-table-back="${tableId}"]`);
          const nextButton = document.querySelector(`[data-table-next="${tableId}"]`);
          let page = 0;

          const renderPage = () => {
            const total = rows.length;
            const start = page * pageSize;
            const end = Math.min(start + pageSize, total);
            rows.forEach((row, index) => {
              const visible = index >= start && index < end;
              row.style.display = visible ? '' : 'none';
              const detailRow = row.nextElementSibling;
              if (detailRow?.matches('[data-detail-row]')) {
                if (!visible) {
                  detailRow.hidden = true;
                  row.setAttribute('aria-expanded', 'false');
                }
                detailRow.style.display = visible && !detailRow.hidden ? '' : 'none';
              }
            });
            if (backButton) backButton.disabled = page === 0;
            if (nextButton) nextButton.disabled = end >= total;
          };

          backButton?.addEventListener('click', () => {
            if (page > 0) {
              page -= 1;
              renderPage();
            }
          });

          nextButton?.addEventListener('click', () => {
            const maxPage = Math.max(0, Math.ceil(rows.length / pageSize) - 1);
            if (page < maxPage) {
              page += 1;
              renderPage();
            }
          });

          renderPage();
        });

        document.querySelectorAll('[data-expandable-row]').forEach((row) => {
          const detailRow = row.nextElementSibling;
          if (!detailRow?.matches('[data-detail-row]')) return;
          const toggle = () => {
            const isOpen = row.getAttribute('aria-expanded') === 'true';
            row.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
            detailRow.hidden = isOpen;
            detailRow.style.display = isOpen ? 'none' : '';
          };
          row.addEventListener('click', toggle);
          row.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            toggle();
          });
        });
      })();
    </script>
"""

    def _render_main_tables(self, *, open_positions_section: dict[str, Any], closed_positions_section: dict[str, Any]) -> str:
        return f"""
      <section class="panel panel-wide runtime-panel">
          <div class="panel-head">
            {self._render_panel_heading(
                str(open_positions_section.get("title", "Open Positions")),
                "portfolio.open_positions.panel",
            )}
            <span class="badge neutral">{self._escape(open_positions_section.get("badge", "0"))}</span>
          </div>
          <p class="panel-intro">{self._escape(open_positions_section.get("intro", ""))}</p>
          <div class="table-shell">
            {self._render_table(
                list(open_positions_section.get("headers") or []),
                list(open_positions_section.get("rows") or []),
                str(open_positions_section.get("empty_text") or "No open positions recorded yet."),
                table_id=str(open_positions_section.get("table_id") or "open-positions"),
            )}
          </div>
        </section>

      <section class="panel panel-wide runtime-panel">
          <div class="panel-head">
            {self._render_panel_heading(
                str(closed_positions_section.get("title", "Closed Positions")),
                "portfolio.closed_positions.panel",
            )}
            <span class="badge neutral">{self._escape(closed_positions_section.get("badge", "0"))}</span>
          </div>
          <p class="panel-intro panel-intro-closed">{self._escape(closed_positions_section.get("intro", ""))}</p>
          <div class="table-shell">
            {self._render_table(
                list(closed_positions_section.get("headers") or []),
                list(closed_positions_section.get("rows") or []),
                str(closed_positions_section.get("empty_text") or "No closed positions recorded yet."),
                table_id=str(closed_positions_section.get("table_id") or "closed-positions"),
            )}
          </div>
        </section>
"""

    def _render_charts_section(self) -> str:
        return f"""
        <section class="panel panel-wide chart-panel">
          <div class="panel-head">
            {self._render_panel_heading("Closed Trade PnL", "portfolio.closed_trade_pnl.panel")}
          </div>
          <p class="panel-intro">Per-trade net PnL across confirmed closed positions.</p>
          <div class="chart-shell">
            <div id="portfolio-pnl-chart" class="chart-canvas" aria-label="Closed trade net pnl chart"></div>
          </div>
        </section>
"""

    def _render_portfolio_content(
        self,
        *,
        capital_snapshot_items: list[dict[str, Any]],
        open_positions_section: dict[str, Any],
        closed_positions_section: dict[str, Any],
    ) -> str:
        return f"""
      <section class="runtime-panel-stack">
        {self._render_capital_panel(capital_snapshot_items)}
        {self._render_main_tables(open_positions_section=open_positions_section, closed_positions_section=closed_positions_section)}
        {self._render_charts_section()}
      </section>
"""
