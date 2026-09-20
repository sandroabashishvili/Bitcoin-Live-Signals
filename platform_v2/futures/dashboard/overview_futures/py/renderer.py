"""Render Futures Overview page from normalized payload data."""

from __future__ import annotations

import html
import json
from typing import Any

from platform_v2.futures.dashboard.explanation_system import (
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

from .explanations import build_overview_explanations


class OverviewFuturesPageRenderer:
    """Render the Futures Overview page from a prepared payload."""

    def render(self, payload: dict[str, Any]) -> str:
        metrics_history_json = json.dumps(payload.get("equity_chart_rows") or [], ensure_ascii=True).replace("</", "<\\/")
        profile = payload.get("profile") or {}
        explanation_payload = render_explanation_payload(build_overview_explanations(payload))

        return f"""<!DOCTYPE html>
<!-- ssh-generator: overview_futures.py.renderer.v2026-04-18e -->
<html lang="en">
  <head>
{render_page_head(
    title="Overview Futures | SmartSignalHub",
    description="Bitcoin futures overview with primary signal, timeframe context, snapshot metrics, and equity drift history.",
    canonical_path="/futures/dashboard/overview_futures/index.html",
    css_href="./css/styles.css",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    favicon_prefix="../../../public_site/",
)}
  </head>
  <body>
    <main class="page">
      <header class="page-chrome">
        {self._render_hero(profile=profile)}
        {self._render_navigation()}
      </header>

      <section class="grid">
        <article class="panel overview-primary-panel overview-panel-with-note">
          <div class="panel-head">{self._render_panel_heading("Primary Signal", "overview.primary_signal.panel")}</div>
          <p class="panel-intro">Current Bitcoin signal, price, and trade readiness.</p>
          <div id="primary-signal-grid" class="metric-grid overview-metric-grid">
            {self._render_primary_signal(payload)}
          </div>
          <p class="panel-note">See <a class="panel-note-link" href="../portfolio_futures/">Portfolio</a> for open positions, closed trades, and portfolio outcomes.</p>
        </article>

        <article class="panel overview-context-panel">
          <div class="panel-head">{self._render_panel_heading("Timeframe Context", "overview.signal_context.panel")}</div>
          <p class="panel-intro">Fast, primary, and higher-timeframe context in one view.</p>
          <div class="timeframe-grid overview-timeframe-grid">
            {self._render_timeframe_cards(payload)}
          </div>
        </article>

        <article class="panel overview-snapshot-panel">
          <div class="panel-head">{self._render_panel_heading("Portfolio Snapshot", "overview.portfolio_snapshot.panel")}</div>
          <p class="panel-intro">Equity, return pace, net return, and open exposure.</p>
          <div class="metric-grid overview-metric-grid">
            {self._render_metric_cards(payload.get("portfolio_snapshot_items") or [])}
          </div>
        </article>

        <article class="panel overview-snapshot-panel">
          <div class="panel-head">{self._render_panel_heading("Trade Outcomes Snapshot", "overview.trade_outcomes_snapshot.panel")}</div>
          <p class="panel-intro">Closed-trade totals, hit distribution, and force-close activity.</p>
          <div class="metric-grid overview-metric-grid">
            {self._render_metric_cards(payload.get("trade_outcomes_snapshot_items") or [])}
          </div>
        </article>

        <article class="panel overview-strategy-panel overview-panel-with-note">
          <div class="panel-head">{self._render_panel_heading("Strategy Snapshot", "overview.strategy_snapshot.panel")}</div>
          <p class="panel-intro">Full-history signal mix and conversion, aligned with Strategy Edge.</p>
          <div class="metric-grid overview-metric-grid">
            {self._render_metric_cards(payload.get("strategy_snapshot_items") or [])}
          </div>
          <p class="panel-note">See <a class="panel-note-link" href="../strategy_edge_futures/">Strategy Edge</a> for full signal-side diagnostics.</p>
        </article>

        <article class="panel overview-compact-chart-panel chart-panel">
          <div class="panel-head">{self._render_panel_heading("Equity Δ% from Start", "overview.equity_chart.panel")}</div>
          <p class="panel-intro">Equity drift from starting capital across recorded daily metric snapshots.</p>
          <div class="chart-shell">
            <div id="overview-equity-chart" class="chart-canvas" aria-label="Equity delta chart"></div>
          </div>
        </article>
      </section>
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
    def _escape(value: Any) -> str:
        return html.escape(str(value))

    @staticmethod
    def _value_class(value: Any, *, kind: str = "generic") -> str:
        return metric_value_class(value, kind=kind)

    @staticmethod
    def _render_panel_heading(title: str, explanation_key: str) -> str:
        return (
            f'<h2 class="panel-title-with-action"><span>{html.escape(title)}</span>'
            f'{render_explanation_anchor(key=explanation_key, label_html="")}</h2>'
        )

    def _strong(self, value: Any, *, kind: str = "generic") -> str:
        klass = self._value_class(value, kind=kind)
        safe = self._escape(value if value not in (None, "") else "—")
        if klass:
            return f'<strong class="{klass}">{safe}</strong>'
        return f"<strong>{safe}</strong>"

    def _render_metric_cards(self, items: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for item in items:
            label = str(item.get("label", "—"))
            value_html = self._strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))
            label_html = f"<span>{self._escape(label)}</span>"
            card_class = "metric-card"
            if label == "Entry Status":
                label_html = (
                    '<span class="metric-label-with-action">'
                    f"<span>{self._escape(label)}</span>"
                    f"{render_explanation_anchor(key='overview.primary_signal.entry_status', label_html='')}"
                    "</span>"
                )
                card_class = "metric-card metric-card-entry-status"
            elif label in {"Force Close", "Force Close Events"}:
                label_html = (
                    '<span class="metric-label-with-action">'
                    f"<span>{self._escape(label)}</span>"
                    f"{render_explanation_anchor(key='overview.trade_outcomes_snapshot.force_close', label_html='')}"
                    "</span>"
                )
            parts.append(f'<div class="{card_class}">{label_html}{value_html}</div>')
        return "".join(parts)

    def _render_primary_signal(self, payload: dict[str, Any]) -> str:
        signal = payload.get("latest_signal") or {}
        order = payload.get("latest_order") or {}
        denied = payload.get("latest_denied_entry") or {}
        setup = signal.get("theoretical_setup") or {}

        side = str(signal.get("selected_direction") or signal.get("side") or "—").upper()
        if side == "BUY":
            side = "LONG"
        elif side == "SELL":
            side = "SHORT"
        side_kind = "tp" if side == "LONG" else "sl" if side == "SHORT" else "generic"
        price = signal.get("snapshot_price")
        if price in (None, ""):
            price = setup.get("entry_price")
        if price in (None, ""):
            price = denied.get("entry_price")
        if price in (None, ""):
            price = payload.get("latest_market_price")
        entry = order.get("entry_price") if order.get("status") == "FILLED" else setup.get("entry_price")
        tp = order.get("take_profit") if order.get("status") == "FILLED" else setup.get("take_profit")
        sl = order.get("stop_loss") if order.get("status") == "FILLED" else setup.get("stop_loss")

        entry_status = "No Action"
        if order.get("status") == "FILLED":
            entry_status = "Opened"
        elif denied:
            entry_status = "Denied"
        elif side == "NO_SIGNAL":
            entry_status = "Blocked by Logic"

        cards = [
            {"label": "Signal", "value": side, "kind": side_kind},
            {"label": "Signal Close", "value": signal.get("candle_close_time") or "—"},
            {"label": "Signal Price", "value": self._fmt(price)},
            {"label": "Decision", "value": signal.get("decision_time") or "—"},
            {"label": "Position Opened", "value": order.get("time_readable") or "—"},
            {"label": "Execution Entry", "value": self._fmt(entry)},
            {"label": "TP", "value": self._fmt(tp), "kind": "tp"},
            {"label": "SL", "value": self._fmt(sl), "kind": "sl"},
            {"label": "Entry Status", "value": entry_status},
        ]
        return self._render_metric_cards(cards)

    def _render_timeframe_cards(self, payload: dict[str, Any]) -> str:
        cards = payload.get("timeframe_context_cards") or []
        html_parts: list[str] = []
        for card in cards:
            signal = str(card.get("signal") or "NO_SIGNAL")
            signal_class = "value-green" if signal == "LONG" else "value-red" if signal == "SHORT" else "value-muted"
            stats_html = "".join(
                f'<div><span>{self._escape(stat.get("label", "—"))}</span>'
                f'{self._strong(stat.get("value", "—"), kind=str(stat.get("kind") or "generic"))}</div>'
                for stat in (card.get("stats") or [])[:3]
            )
            html_parts.append(
                f"""
                <article class="timeframe-card">
                  <div class="timeframe-card-head">
                    <span>{self._escape(card.get('label', '—'))}</span>
                    <h3 class="{signal_class}">{self._escape(signal)}</h3>
                  </div>
                  <p class="timeframe-role">{self._escape(card.get('role', 'Market context for this timeframe.'))}</p>
                  <div class="timeframe-stats">{stats_html}</div>
                </article>
                """
            )
        return "".join(html_parts)

    def _render_hero(self, *, profile: dict[str, Any]) -> str:
        return render_futures_runtime_hero(
            title="Bitcoin Futures Long Short Signals And Execution",
            href="../overview_futures/index.html",
            intro="",
            subline=None,
        )

    @staticmethod
    def _render_navigation() -> str:
        return render_site_navigation(active_page="overview_futures")
        return """
      <div class="global-nav-shell">

        <nav class="global-nav" aria-label="Primary navigation">

          <a class="global-brand" href="../../../public_site/">SmartSignalHub</a>

          <div class="global-nav-links"><a href="../../../public_site/">Home</a><a href="../../../spot/dashboard/overview_spot/">Spot</a><a class="active" href="../overview_futures/">Futures</a><a href="../../../futures_hedge/dashboard/overview_hedge/">Hedge</a><a href="../../../public_site/news/">News</a><a href="../../../public_site/resources/">Resources</a></div>

        </nav>

      </div>

      <div class="subnav-shell">
        <nav class="subnav-mobile-menu" data-subnav-menu>
          <a class="subnav-link subnav-link-primary active" href="../overview_futures/">Overview</a><a class="subnav-link subnav-link-primary" href="../portfolio_futures/">Portfolio</a><a class="subnav-link subnav-link-primary" href="../trade_outcomes_futures/">Trade</a><a class="subnav-link subnav-link-primary" href="../strategy_edge_futures/">Strategy</a><a class="subnav-link subnav-link-primary" href="../orderbook_futures/">Orderbook</a>
        </nav>
        <nav class="subnav">
          <div class="subnav-row subnav-row-primary"><a class="subnav-link subnav-link-primary active" href="../overview_futures/">Overview</a><a class="subnav-link subnav-link-primary" href="../portfolio_futures/">Portfolio</a><a class="subnav-link subnav-link-primary" href="../trade_outcomes_futures/">Trade</a><a class="subnav-link subnav-link-primary" href="../strategy_edge_futures/">Strategy</a><a class="subnav-link subnav-link-primary" href="../orderbook_futures/">Orderbook</a></div>
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

    @staticmethod
    def _fmt(value: Any) -> str:
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "—"
