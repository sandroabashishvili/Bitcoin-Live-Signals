"""Render Futures Trade Outcomes page from normalized payload data."""

from __future__ import annotations

import html
import json
from typing import Any

from platform_v2.futures.dashboard.explanation_system import (
    load_explanation_map,
    render_explanation_anchor,
    render_explanation_host,
    render_explanation_payload,
)
from platform_v2.futures.dashboard.components import render_futures_runtime_hero
from platform_v2.shared.frontend.components import (
    metric_value_class,
    render_page_head,
    render_runtime_clock_script,
    render_site_footer,
    render_site_navigation,
)


class TradeOutcomesFuturesPageRenderer:
    """Render the Futures Trade Outcomes page from a prepared payload."""

    def render(self, payload: dict[str, Any]) -> str:
        logic_evaluation = payload["logic_chart_payload"]
        logic_tables_section = payload["logic_tables_section"]
        strategy_outcome_items = payload["strategy_outcome_items"]

        explanation_payload = render_explanation_payload(self._explanations_for_prefix("trade_outcomes."))
        return f"""<!DOCTYPE html>
<!-- ssh-generator: trade_outcomes_futures.py.renderer.v2026-04-18a -->
<html lang="en">
  <head>
{render_page_head(
    title="Bitcoin Futures Trade Outcomes | SmartSignalHub",
    description="Execution-side futures trade results for Bitcoin: denied directional setups, closed-trade outcomes, and gate effectiveness inside SmartSignalHub.",
    canonical_path="/futures/dashboard/trade_outcomes_futures/index.html",
    css_href="./css/styles.css",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    favicon_prefix="../../../public_site/",
    og_description="Inspect Bitcoin futures trade outcomes, denied directional setups, and gate effectiveness inside SmartSignalHub.",
    twitter_description="Inspect Bitcoin futures trade outcomes, denied directional setups, and gate effectiveness inside SmartSignalHub.",
)}
    <style>
      .futures-nav {{
        max-width: 1040px;
        margin: 0 auto;
        padding: 4px 18px 8px;
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }}
      .futures-nav a {{
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 6px 12px;
        text-decoration: none;
        color: var(--text);
        background: color-mix(in oklab, var(--bg-soft) 86%, #050a13 14%);
        font-size: 13px;
      }}
      .futures-nav a.active {{
        border-color: var(--amber);
        color: var(--amber);
      }}
    </style>
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
        return render_futures_runtime_hero(
            title="Bitcoin Futures Trade Outcomes And Performance",
            href="../trade_outcomes_futures/index.html",
            intro="",
            subline=None,
        )

    @staticmethod
    def _render_navigation() -> str:
        return render_site_navigation(active_page="trade_outcomes_futures")
        return """
      <div class="global-nav-shell">

        <nav class="global-nav" aria-label="Primary navigation">

          <a class="global-brand" href="../../../public_site/">SmartSignalHub</a>

          <div class="global-nav-links"><a href="../../../public_site/">Home</a><a href="../../../spot/dashboard/overview_spot/">Spot</a><a class="active" href="../overview_futures/">Futures</a><a href="../../../futures_hedge/dashboard/overview_hedge/">Hedge</a><a href="../../../public_site/news/">News</a><a href="../../../public_site/resources/">Resources</a></div>

        </nav>

      </div>

      <div class="subnav-shell">
        <nav class="subnav-mobile-menu" data-subnav-menu>
          <a class="subnav-link subnav-link-primary" href="../overview_futures/">Overview</a><a class="subnav-link subnav-link-primary" href="../portfolio_futures/">Portfolio</a><a class="subnav-link subnav-link-primary active" href="../trade_outcomes_futures/">Trade</a><a class="subnav-link subnav-link-primary" href="../strategy_edge_futures/">Strategy</a><a class="subnav-link subnav-link-primary" href="../orderbook_futures/">Orderbook</a>
        </nav>
        <nav class="subnav">
          <div class="subnav-row subnav-row-primary"><a class="subnav-link subnav-link-primary" href="../overview_futures/">Overview</a><a class="subnav-link subnav-link-primary" href="../portfolio_futures/">Portfolio</a><a class="subnav-link subnav-link-primary active" href="../trade_outcomes_futures/">Trade</a><a class="subnav-link subnav-link-primary" href="../strategy_edge_futures/">Strategy</a><a class="subnav-link subnav-link-primary" href="../orderbook_futures/">Orderbook</a></div>
        </nav>
      </div>
      <script>
        (() => {
          const shell = document.querySelector(".subnav-shell");
          const menu = shell?.querySelector("[data-subnav-menu]");
          if (!shell || !menu) return;
          let toggle = document.querySelector("[data-subnav-toggle]");
          if (!toggle) {
            const note = document.querySelector(".hero-note");
            if (note) {
              let row = note.closest(".hero-note-row");
              if (!row) {
                row = document.createElement("div");
                row.className = "hero-note-row";
                note.parentNode?.insertBefore(row, note);
                row.appendChild(note);
              }
              toggle = document.createElement("button");
              toggle.className = "subnav-toggle";
              toggle.type = "button";
              toggle.setAttribute("data-subnav-toggle", "");
              toggle.setAttribute("aria-expanded", "false");
              toggle.setAttribute("aria-label", "Open navigation menu");
              toggle.textContent = "☰";
              row.appendChild(toggle);
            }
          }
          if (!toggle) return;
          menu.setAttribute("aria-hidden", "true");
          const setMenuPosition = () => {
            const rect = toggle.getBoundingClientRect();
            const top = Math.round(rect.bottom);
            menu.style.top = `${top}px`;
            menu.style.maxHeight = `calc(100vh - ${top}px)`;
            menu.style.right = "16px";
            menu.style.left = "auto";
          };
          const closeMenu = () => {
            shell.classList.remove("subnav-open");
            toggle.setAttribute("aria-expanded", "false");
            menu.setAttribute("aria-hidden", "true");
          };
          toggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const isOpen = shell.classList.toggle("subnav-open");
            toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
            menu.setAttribute("aria-hidden", isOpen ? "false" : "true");
            if (isOpen) setMenuPosition();
          });
          document.addEventListener("click", (event) => {
            if (!shell.classList.contains("subnav-open")) return;
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (toggle.contains(target) || menu.contains(target)) return;
            closeMenu();
          });
          menu.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (target.closest("a, button")) closeMenu();
          });
          const marketButtons = Array.from(document.querySelectorAll("[data-market-href]"));
          marketButtons.forEach((button) => {
            button.addEventListener("click", (event) => {
              event.preventDefault();
              const href = button.getAttribute("data-market-href");
              if (!href) return;
              window.location.href = href;
            });
          });
          document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeMenu();
          });
        })();
      </script>
"""

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
          <p class="panel-intro">Closed-trade summary for executed futures positions.</p>
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
        long_primary_rows = logic_tables_section.get("long_primary_rows") or primary_rows
        long_confirmation_rows = logic_tables_section.get("long_confirmation_rows") or confirmation_rows
        short_primary_rows = logic_tables_section.get("short_primary_rows") or []
        short_confirmation_rows = logic_tables_section.get("short_confirmation_rows") or []
        long_rows = self._direction_gate_rows(
            primary_rows=long_primary_rows,
            confirmation_rows=long_confirmation_rows,
        )
        short_rows = self._direction_gate_rows(
            primary_rows=short_primary_rows,
            confirmation_rows=short_confirmation_rows,
        )
        direction_headers = ["Type", *logic_tables_section["headers"]]
        return f"""
      <section class="panel panel-wide chart-panel">
          <div class="panel-head">
            {self._render_panel_heading(
                str(logic_tables_section.get("title") or "Gate Effectiveness"),
                "trade_outcomes.gate_effectiveness.panel",
            )}
          </div>
          <p class="panel-intro">{self._escape(logic_tables_section['intro'])}</p>
          <div class="strategy-logic-grid strategy-logic-paired-grid">
            <div class="strategy-logic-card">
              <div class="chart-shell strategy-donut-shell">
                <div id="strategy-primary-donut" class="chart-canvas" aria-label="Primary gates donut"></div>
              </div>
              <section class="strategy-gate-direction-card">
                <div class="strategy-gate-direction-head">
                  <h3 class="panel-title-with-action"><span>LONG Gates</span>{render_explanation_anchor(key="trade_outcomes.gates.long", label_html="")}</h3>
                  <p>Closed LONG trades by gate type, outcome, and win rate.</p>
                </div>
                {self._render_direction_logic_table(direction_headers, long_rows)}
              </section>
            </div>
            <div class="strategy-logic-card">
              <div class="chart-shell strategy-donut-shell">
                <div id="strategy-confirmation-donut" class="chart-canvas" aria-label="Confirmation gates donut"></div>
              </div>
              <section class="strategy-gate-direction-card">
                <div class="strategy-gate-direction-head">
                  <h3 class="panel-title-with-action"><span>SHORT Gates</span>{render_explanation_anchor(key="trade_outcomes.gates.short", label_html="")}</h3>
                  <p>Closed SHORT trades by gate type, outcome, and win rate.</p>
                </div>
                {self._render_direction_logic_table(direction_headers, short_rows)}
              </section>
            </div>
          </div>
      </section>
"""

    @staticmethod
    def _direction_gate_rows(
        *,
        primary_rows: list[dict[str, Any]],
        confirmation_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend({**row, "gate_type": "Primary"} for row in primary_rows)
        rows.extend({**row, "gate_type": "Confirm"} for row in confirmation_rows)
        return rows

    def _render_direction_logic_table(self, headers: list[str], rows: list[dict[str, Any]]) -> str:
        if not rows:
            return '<div class="stack-list empty">No gate data available yet.</div>'
        head = "".join(f"<th>{self._escape(header)}</th>" for header in headers)
        body = "".join(
            "<tr>"
            f"<td><strong>{self._escape(row.get('gate_type', '—'))}</strong></td>"
            f"<td><strong>{self._escape(row.get('gate', '—'))}</strong></td>"
            f"<td>{self._strong(row.get('participated', '—'), kind='neutral')}</td>"
            f"<td>{self._strong(row.get('tp', '—'), kind='pass')}</td>"
            f"<td>{self._strong(row.get('sl', '—'), kind='fail')}</td>"
            f"<td>{self._strong(row.get('profit_lock', '—'), kind='pass')}</td>"
            f"<td>{self._strong(row.get('force_close', '—'), kind='neutral')}</td>"
            f"<td>{self._rate_html(row.get('win_rate'))}</td>"
            "</tr>"
            for row in rows
        )
        return f"""
        <div class="table-shell strategy-logic-table-shell">
          <table class="runtime-table gate-table direction-gate-table">
            <thead><tr>{head}</tr></thead>
            <tbody>{body}</tbody>
          </table>
        </div>
        """
