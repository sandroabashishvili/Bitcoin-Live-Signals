"""File: renderer.py
Folder: platform_v2/public_site/trade_outcomes/py
Created date: 2026-03-28
Last updated date: 2026-04-11
Author: Codex
Purpose: Render the static V2 Trade Outcomes page from normalized payload data.
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


class TradeOutcomesPageRenderer:
    """Render the Trade Outcomes page from a prepared payload."""

    def render(self, payload: dict[str, Any]) -> str:
        logic_evaluation = payload["logic_chart_payload"]
        logic_tables_section = payload["logic_tables_section"]
        strategy_outcome_items = payload["strategy_outcome_items"]

        explanation_payload = render_explanation_payload(self._explanations_for_prefix("trade_outcomes."))
        return f"""<!DOCTYPE html>
<!-- ssh-generator: trade_outcomes.py.renderer.v2026-04-11b -->
<html lang="en">
  <head>
{render_page_head(
    title="Bitcoin Trade Outcomes | SmartSignalHub",
    description="Execution-side trade results for Bitcoin: denied BUY setups, closed-trade outcomes, and gate effectiveness inside SmartSignalHub.",
    canonical_path="/spot/dashboard/trade_outcomes/index.html",
    css_href="./css/styles.css",
    favicon_prefix="../../../public_site/",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    og_description="Inspect Bitcoin trade outcomes, denied BUY setups, and gate effectiveness inside SmartSignalHub.",
    twitter_description="Inspect Bitcoin trade outcomes, denied BUY setups, and gate effectiveness inside SmartSignalHub.",
    schema_json_ld="""      {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/trade_outcomes/#webpage",
        "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/spot/dashboard/trade_outcomes/",
        "name": "Bitcoin Trade Outcomes | SmartSignalHub",
        "description": "Execution-side trade results for Bitcoin: denied BUY setups, closed-trade outcomes, and gate effectiveness inside SmartSignalHub.",
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
        {self._render_hero(payload)}
        {self._render_navigation()}
      </header>
      {self._render_summary_section(strategy_outcome_items=strategy_outcome_items)}
      {self._render_logic_evaluation_section(logic_evaluation=logic_evaluation, logic_tables_section=logic_tables_section)}
    </main>
      {render_site_footer()}
    {explanation_payload}
    {render_explanation_host(base_prefix="../")}
    <script>window.__SSH_STRATEGY_LOGIC__ = {json.dumps(logic_evaluation, ensure_ascii=True).replace("</", "<\\/")};</script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script type="module" src="../../../shared/frontend/charts/strategy_logic_evaluation.js"></script>
    {render_runtime_clock_script()}
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
    def _fmt_percent_value(value: Any) -> float | None:
        try:
            return float(str(value).replace("%", ""))
        except (TypeError, ValueError):
            return None

    def _rate_html(self, value: Any) -> str:
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

    def _render_hero(self, payload: dict[str, Any]) -> str:
        return render_runtime_hero(
            title="Bitcoin Spot Trade Outcomes And Performance",
            href="../trade_outcomes/index.html",
            intro="",
            subline=None,
        )

    @staticmethod
    def _render_navigation() -> str:
        return render_site_navigation(active_page="trade_outcomes")

    def _render_metric_cards(self, items: list[dict[str, Any]]) -> str:
        return "".join(
            f'<div class="metric-card"><span>{self._escape(item.get("label", "—"))}</span>{self._strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))}</div>'
            for item in items
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

    def _render_summary_section(self, *, strategy_outcome_items: list[dict[str, Any]]) -> str:
        outcome_cards = self._render_metric_cards(strategy_outcome_items)
        return f"""
      <section class="strategy-summary-grid trade-outcomes-summary-grid">
        <section class="panel">
          <div class="panel-head">
            {self._render_panel_heading("Trade Outcomes", "trade_outcomes.summary.panel")}
          </div>
          <p class="panel-intro">Closed-trade summary for executed BUY positions.</p>
          <div class="kpi-grid trade-outcomes-kpi-grid">
            {outcome_cards}
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
                "trade_outcomes.gate_effectiveness.panel",
            )}
          </div>
          <p class="panel-intro">{self._escape(logic_tables_section['intro'])}</p>
          <div class="strategy-logic-grid">
            <div class="strategy-logic-card">
              <div class="chart-shell strategy-donut-shell">
                <div id="strategy-primary-donut" class="chart-canvas" aria-label="Primary gates donut"></div>
              </div>
              <div class="table-shell strategy-logic-table-shell">
                {self._render_logic_table(logic_tables_section['primary_title'], logic_tables_section.get('primary_subtitle', ''), logic_tables_section['headers'], primary_rows)}
              </div>
            </div>
            <div class="strategy-logic-card">
              <div class="chart-shell strategy-donut-shell">
                <div id="strategy-confirmation-donut" class="chart-canvas" aria-label="Confirmation gates donut"></div>
              </div>
              <div class="table-shell strategy-logic-table-shell">
              {self._render_logic_table(logic_tables_section['confirmation_title'], logic_tables_section.get('confirmation_subtitle', ''), logic_tables_section['headers'], confirmation_rows)}
              </div>
            </div>
          </div>
      </section>
"""

    def _render_logic_table(
        self,
        title: str,
        subtitle: str,
        headers: list[str],
        rows: list[dict[str, Any]],
    ) -> str:
        if not rows:
            return '<div class="stack-list empty">No gate data available yet.</div>'
        headers = [*headers[:4], "Lock", *headers[4:]]
        head = "".join(f"<th>{self._escape(header)}</th>" for header in headers)
        body = "".join(
            "<tr>"
            f"<td><strong>{self._escape(row.get('gate', '—'))}</strong></td>"
            f"<td>{self._strong(row.get('participated', '—'), kind='neutral')}</td>"
            f"<td>{self._strong(row.get('tp', '—'), kind='pass')}</td>"
            f"<td>{self._strong(row.get('sl', '—'), kind='fail')}</td>"
            f"<td>{self._strong(row.get('lock', 0), kind='pass')}</td>"
            f"<td>{self._strong(row.get('force_close', '—'), kind='neutral')}</td>"
            f"<td>{self._rate_html(row.get('win_rate'))}</td>"
            "</tr>"
            for row in rows
        )
        return f"""
        <div class="strategy-logic-table-title">{self._escape(title)}</div>
        <div class="strategy-logic-table-subtitle">{self._escape(subtitle)}</div>
        <table class="runtime-table gate-table">
          <thead><tr>{head}</tr></thead>
          <tbody>{body}</tbody>
        </table>
        """
