"""Render the static Strategy Edge page from normalized payload data."""

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


class StrategyEdgePageRenderer:
    """Render the Strategy Edge page from a prepared payload."""

    def render(self, payload: dict[str, Any]) -> str:
        logic_evaluation = payload["logic_chart_payload"]
        logic_tables_section = payload["logic_tables_section"]
        recent_signals_section = payload["recent_signals_section"]
        strategy_activity_items = payload["strategy_activity_items"]
        status_summary = payload["strategy_activity_summary"] or {}
        status_line = (
            f"Updated {self._escape(payload['generated_at'])} · "
            f"BUY Signals {self._escape(status_summary.get('buy_signals', 0))} · "
            f"Theoretical TP {self._escape(status_summary.get('theoretical_tp_hits', 0))} · "
            f"Theoretical SL {self._escape(status_summary.get('theoretical_sl_hits', 0))}"
        )

        explanation_payload = render_explanation_payload(self._explanations_for_prefix("strategy_edge."))
        return f"""<!DOCTYPE html>
<!-- ssh-generator: strategy_edge.py.renderer.v2026-04-11a -->
<html lang="en">
  <head>
{render_page_head(
    title="Bitcoin Strategy Edge | SmartSignalHub",
    description="Signal-side strategy evaluation for Bitcoin: theoretical TP/SL outcomes, signal quality, and gate effectiveness inside SmartSignalHub.",
    canonical_path="/spot/dashboard/strategy_edge/index.html",
    css_href="./css/styles.css",
    favicon_prefix="../../../public_site/",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    og_description="Inspect strategy edge, theoretical TP/SL outcomes, and gate effectiveness inside SmartSignalHub.",
    twitter_description="Inspect strategy edge, theoretical TP/SL outcomes, and gate effectiveness inside SmartSignalHub.",
    schema_json_ld="""      {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/strategy_edge/#webpage",
        "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/strategy_edge/",
        "name": "Bitcoin Strategy Edge | SmartSignalHub",
        "description": "Signal-side strategy evaluation for Bitcoin: theoretical TP/SL outcomes, signal quality, and gate effectiveness inside SmartSignalHub.",
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
      {self._render_summary_section(strategy_activity_items=strategy_activity_items)}
      {self._render_logic_evaluation_section(logic_evaluation=logic_evaluation, logic_tables_section=logic_tables_section)}
      {self._render_recent_section(recent_signals_section=recent_signals_section)}
    </main>
      {render_site_footer()}
    {explanation_payload}
    {render_explanation_host(base_prefix="../")}
    <script>window.__SSH_STRATEGY_LOGIC__ = {json.dumps(logic_evaluation, ensure_ascii=True).replace("</", "<\\/")};</script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script type="module" src="../../../shared/frontend/charts/strategy_logic_evaluation.js"></script>
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

    @staticmethod
    def _fmt_percent_value(value: Any) -> float | None:
        try:
            return float(str(value).replace("%", ""))
        except (TypeError, ValueError):
            return None

    def _pass_rate_html(self, value: Any) -> str:
        numeric = self._fmt_percent_value(value)
        if numeric is None:
            return self._strong("—")
        if numeric >= 60.0:
            kind = "pass"
        elif numeric <= 40.0:
            kind = "fail"
        else:
            kind = "neutral"
        return self._strong(f"{numeric:.2f}%", kind=kind)

    def _render_hero(self) -> str:
        return render_runtime_hero(
            title="Bitcoin Spot Strategy Edge And Signal Diagnostics",
            href="../strategy_edge/index.html",
            intro="",
            subline=None,
        )

    @staticmethod
    def _render_navigation() -> str:
        return render_site_navigation(active_page="strategy_edge")

    def _metric_label_html(self, item: dict[str, Any]) -> str:
        label = self._escape(item.get("label", "—"))
        explanation_key = str(item.get("explanation_key") or "")
        if not explanation_key:
            return f"<span>{label}</span>"
        return (
            '<span class="metric-label-with-action">'
            f"<span>{label}</span>"
            f'{render_explanation_anchor(key=explanation_key, label_html="")}'
            "</span>"
        )

    def _render_metric_cards(self, items: list[dict[str, Any]]) -> str:
        return "".join(
            f'<div class="metric-card">{self._metric_label_html(item)}{self._strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))}</div>'
            for item in items
        )

    def _render_summary_section(self, *, strategy_activity_items: list[dict[str, Any]]) -> str:
        activity_cards = self._render_metric_cards(strategy_activity_items)
        return f"""
      <section class="strategy-summary-grid">
        <section class="panel">
          <div class="panel-head">
            {self._render_panel_heading("Strategy Edge", "strategy_edge.summary.panel")}
          </div>
          <p class="panel-intro">Full-history signal activity and theoretical TP/SL results for BUY setups.</p>
          <div class="kpi-grid">
            {activity_cards}
          </div>
        </section>
      </section>
"""

    def _render_logic_evaluation_section(
        self,
        *,
        logic_evaluation: dict[str, Any],
        logic_tables_section: dict[str, Any],
    ) -> str:
        primary_rows = logic_tables_section["primary_rows"]
        confirmation_rows = logic_tables_section["confirmation_rows"]
        return f"""
      <section class="panel panel-wide chart-panel">
          <div class="panel-head">
            {self._render_panel_heading(
                str(logic_tables_section.get("title") or "Gate Effectiveness"),
                "strategy_edge.gate_effectiveness.panel",
            )}
          </div>
          <p class="panel-intro">{self._escape(logic_tables_section['intro'])}</p>
          <div class="strategy-logic-grid">
            <div class="strategy-logic-card">
              <div class="chart-shell strategy-donut-shell">
                <div id="strategy-primary-donut" class="chart-canvas" aria-label="Primary gates donut"></div>
              </div>
              <div class="table-shell strategy-logic-table-shell">
                {self._render_logic_table(logic_tables_section['primary_title'], logic_tables_section['headers'], primary_rows)}
              </div>
            </div>
            <div class="strategy-logic-card">
              <div class="chart-shell strategy-donut-shell">
                <div id="strategy-confirmation-donut" class="chart-canvas" aria-label="Confirmation gates donut"></div>
              </div>
              <div class="table-shell strategy-logic-table-shell">
              {self._render_logic_table(logic_tables_section['confirmation_title'], logic_tables_section['headers'], confirmation_rows)}
              </div>
            </div>
          </div>
      </section>
"""

    def _render_logic_table(self, title: str, headers: list[str], rows: list[dict[str, Any]]) -> str:
        if not rows:
            return '<div class="stack-list empty">No gate data available yet.</div>'
        head = "".join(f"<th>{self._escape(header)}</th>" for header in headers)
        body_rows: list[str] = []
        for row in rows:
            body_rows.append(
                "<tr>"
                f"<td><strong>{self._escape(row['gate'])}</strong></td>"
                f"<td>{self._strong(row['participated'], kind='neutral')}</td>"
                f"<td>{self._strong(row['tp'], kind='pass')}</td>"
                f"<td>{self._strong(row['sl'], kind='fail')}</td>"
                f"<td>{self._strong(row['open'], kind='neutral')}</td>"
                f"<td>{self._pass_rate_html(row['win_rate'])}</td>"
                "</tr>"
            )
        body = "".join(body_rows)
        return f"""
        <div class="strategy-logic-table-title">{self._escape(title)}</div>
        <table class="runtime-table gate-table">
          <thead><tr>{head}</tr></thead>
          <tbody>{body}</tbody>
        </table>
        """

    def _render_recent_section(self, *, recent_signals_section: dict[str, Any]) -> str:
        return f"""
      <section class="panel panel-wide">
          <div class="panel-head">
            {self._render_panel_heading(
                str(recent_signals_section.get("title") or "Recent Signal Decisions"),
                "strategy_edge.recent_signals.panel",
            )}
          </div>
          <p class="panel-intro">{self._escape(recent_signals_section['intro'])}</p>
          <div class="table-shell">
            {self._render_paginated_table(
                table_id=recent_signals_section["table_id"],
                headers=recent_signals_section["headers"],
                rows=recent_signals_section["rows"],
                empty_text=recent_signals_section["empty_text"],
                page_size=int(recent_signals_section.get("page_size", 5)),
            )}
          </div>
      </section>
"""

    def _render_paginated_table(
        self,
        *,
        table_id: str,
        headers: list[str],
        rows: list[list[str]],
        empty_text: str,
        page_size: int = 5,
    ) -> str:
        if not rows:
            return f'<div class="stack-list empty">{self._escape(empty_text)}</div>'
        table_class = "runtime-table paginated-runtime-table"
        if table_id == "recent-signals":
            table_class += " recent-signals-table"
        head = "".join(f"<th>{self._escape(header)}</th>" for header in headers)
        serialized_rows = json.dumps(rows, ensure_ascii=True).replace("</", "<\\/")
        initial_rows = "".join(
            f"<tr>{''.join(f'<td>{cell}</td>' for cell in row)}</tr>"
            for row in rows[:page_size]
        )
        return f"""
        <div class="table-controls" data-strategy-table="{table_id}">
          <div class="table-controls-group">
            <button class="table-control-button" type="button" data-strategy-back="{table_id}">Back</button>
            <button class="table-control-button" type="button" data-strategy-next="{table_id}">Next</button>
          </div>
        </div>
        <table class="{table_class}">
          <thead><tr>{head}</tr></thead>
          <tbody data-strategy-body="{table_id}">{initial_rows}</tbody>
        </table>
        <script>window.__STRATEGY_TABLES__ = window.__STRATEGY_TABLES__ || {{}}; window.__STRATEGY_TABLES__["{table_id}"] = {serialized_rows};</script>
        """

    @staticmethod
    def _render_table_script() -> str:
        return """
    <script>
      (() => {
        const pageSize = 5;
        const tableState = window.__STRATEGY_TABLES__ || {};
        const currentPageByTable = {};
        const renderTable = (tableId, page) => {
          const rows = tableState[tableId] || [];
          const body = document.querySelector(`[data-strategy-body="${tableId}"]`);
          if (!body) return;
          const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
          const safePage = Math.min(Math.max(page, 0), pageCount - 1);
          const slice = rows.slice(safePage * pageSize, safePage * pageSize + pageSize);
          body.innerHTML = slice.map(
            (row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`
          ).join("");
          currentPageByTable[tableId] = safePage;
        };
        document.querySelectorAll("[data-strategy-table]").forEach((control) => {
          const tableId = control.dataset.strategyTable;
          if (!tableId) return;
          renderTable(tableId, 0);
          control.querySelector(`[data-strategy-back="${tableId}"]`)?.addEventListener("click", () => {
            const current = Number(currentPageByTable[tableId] || 0);
            renderTable(tableId, current - 1);
          });
          control.querySelector(`[data-strategy-next="${tableId}"]`)?.addEventListener("click", () => {
            const current = Number(currentPageByTable[tableId] || 0);
            renderTable(tableId, current + 1);
          });
        });
      })();
    </script>
"""
