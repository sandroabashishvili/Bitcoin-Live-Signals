"""Render Futures Hedge overview page."""

from __future__ import annotations

import html
import json
from typing import Any

from platform_v2.futures_hedge.dashboard.explanation_system import (
    load_explanation_map,
    render_explanation_anchor,
    render_explanation_host,
    render_explanation_payload,
)
from platform_v2.shared.frontend.components import (
    render_content_hero,
    render_page_head,
    render_runtime_clock_script,
    render_site_footer,
    render_site_navigation,
)


class FuturesHedgeOverviewRenderer:
    """Render the first Hedge dashboard page from replay report data."""

    def render(self, report: dict[str, Any]) -> str:
        snapshot = report.get("final_snapshot") or {}
        decision = report.get("decision_summary") or {}
        source = report.get("source") or {}
        counts = report.get("source_counts") or {}
        entries = list(report.get("entries") or [])
        equity_history_json = json.dumps(report.get("equity_chart_rows") or [], ensure_ascii=True).replace("</", "<\\/")
        basket_history_json = json.dumps(
            report.get("basket_chart_rows") or report.get("basket_snapshots") or [],
            ensure_ascii=True,
        ).replace("</", "<\\/")
        explanation_payload = render_explanation_payload(load_explanation_map())

        return f"""<!DOCTYPE html>
<html lang="en">
  <head>
{render_page_head(
    title="Futures Hedge | SmartSignalHub",
    description="Independent Futures Hedge paper replay with LONG and SHORT basket accounting.",
    canonical_path="/futures_hedge/dashboard/overview_hedge/index.html",
    css_href="./css/styles.css",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    favicon_prefix="../../../public_site/",
)}
  </head>
  <body>
    <main class="page hedge-page">
      <header class="page-chrome">
        {render_content_hero(
          title="Bitcoin Futures Hedge Strategy Dashboard",
          href="../overview_hedge/",
          intro="",
          subline="Mode: simulation | Hedge Strategy | Leverage: x5",
          note="Educational use only. Not financial advice.",
          show_runtime=True,
          show_subnav_toggle=False,
        )}
        {render_site_navigation(active_page="futures_hedge")}
      </header>

      <section class="panel section-panel capital-panel">
        <div class="panel-head">
          {self._render_panel_heading("Capital Snapshot", "hedge.capital_snapshot.panel")}
        </div>
        {self._render_capital_snapshot(snapshot=snapshot, decision=decision, counts=counts, report=report)}
      </section>

      <section class="grid grid-main">
        {self._render_basket(snapshot.get("long_basket") or {})}
        {self._render_basket(snapshot.get("short_basket") or {})}
      </section>

      <section class="panel section-panel chart-panel hedge-equity-chart-panel">
        <div class="panel-head">
          {self._render_panel_heading("Equity Δ% from Start", "hedge.equity_chart.panel")}
        </div>
        <p class="panel-intro">Hedge equity movement from starting capital across Hedge-owned timeline snapshots.</p>
        <div class="chart-shell">
          <div id="overview-equity-chart" class="chart-canvas" aria-label="Hedge equity delta chart"></div>
        </div>
      </section>

      <section class="panel section-panel">
        <div class="section-heading-row">
          {self._render_panel_heading("Hedge Entries", "hedge.entries.panel")}
          <span class="badge neutral">{self._escape(len(entries))}</span>
        </div>
        {self._render_entries_table(entries)}
      </section>
    </main>

    {render_site_footer()}
    {explanation_payload}
    {render_explanation_host(asset_prefix="../../../shared/frontend/explanation_system/")}
    <script>
      window.__SSH_OVERVIEW_EQUITY__ = {equity_history_json};
      window.__SSH_HEDGE_BASKETS__ = {basket_history_json};
    </script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script type="module" src="../../../shared/frontend/charts/equity_delta_chart.js"></script>
    <script type="module" src="./js/basket_pnl_charts.js"></script>
    {render_runtime_clock_script()}
    {self._render_table_script()}
  </body>
</html>
"""

    def _render_basket(self, basket: dict[str, Any]) -> str:
        side = str(basket.get("side") or "Basket")
        explanation_key = "hedge.long_basket.panel" if side == "LONG" else "hedge.short_basket.panel"
        return f"""
        <article class="panel basket basket-{self._escape(side.lower())}">
          {self._render_panel_heading(f"{side} Basket", explanation_key)}
          <div class="basket-chart-heading">
            <span>Unrealized PnL history</span>
            <small>Updated from Hedge basket snapshots</small>
          </div>
          <div class="chart-shell basket-chart-shell">
            <div id="hedge-{self._escape(side.lower())}-basket-chart" class="chart-canvas" aria-label="{self._escape(side)} basket unrealized PnL chart"></div>
          </div>
          <div class="rows">
            {self._render_row("Entries", basket.get("count"), "")}
            {self._render_row("Margin", basket.get("margin_usdt"), "USDT")}
            {self._render_row("Notional", basket.get("notional_usdt"), "USDT")}
            {self._render_row("Quantity", basket.get("quantity"), "BTC")}
            {self._render_row("Average entry", basket.get("average_entry_price"), "USDT")}
            {self._render_row("Mark price", basket.get("mark_price"), "USDT")}
            {self._render_row("Unrealized PnL", basket.get("unrealized_pnl"), "USDT")}
            {self._render_row("Entry Fees", basket.get("entry_fees_usdt"), "USDT")}
            {self._render_row("Exit Fee Estimate", basket.get("estimated_exit_fee_usdt"), "USDT")}
            {self._render_row("ROE", basket.get("roe_pct"), "%")}
          </div>
        </article>
"""

    def _render_capital_snapshot(
        self,
        *,
        snapshot: dict[str, Any],
        decision: dict[str, Any],
        counts: dict[str, Any],
        report: dict[str, Any],
    ) -> str:
        primary_items = (
            ("Starting Capital", snapshot.get("starting_capital_usdt"), "USDT", ""),
            ("Open Equity", snapshot.get("equity_usdt"), "USDT", ""),
            ("If Closed Now", decision.get("if_closed_now_equity_usdt"), "USDT", ""),
            ("Available Capital", snapshot.get("available_capital_usdt"), "USDT", ""),
            ("Used Margin", snapshot.get("used_margin_usdt"), "USDT", ""),
            ("Unrealized PnL", snapshot.get("unrealized_pnl_usdt"), "USDT", ""),
            ("Realized PnL", snapshot.get("realized_pnl_usdt"), "USDT", ""),
            ("Total Fees", snapshot.get("total_fees_usdt"), "USDT", ""),
        )
        secondary_items = (
            ("Peak Capital", report.get("peak_equity_usdt"), "USDT", ""),
            ("Lowest Capital", report.get("lowest_equity_usdt"), "USDT", ""),
            ("Current Mark Price", report.get("final_mark_price"), "USDT", ""),
            ("Entry Capacity", self._next_entry_capacity_label(decision), "", ""),
            ("Net Exposure", self._net_exposure_label(decision), "", ""),
            ("Side Imbalance", self._side_imbalance_label(decision), "", ""),
            ("Margin Used", decision.get("margin_used_pct"), "%", ""),
            ("Worst Basket ROE", decision.get("worst_basket_roe_pct"), "%", ""),
            ("Danger Distance", decision.get("distance_to_danger_zone_pct"), "%", ""),
            ("Liquidation Risk", decision.get("liquidation_risk"), "", ""),
            ("Reset Count", snapshot.get("reset_count"), "", ""),
            ("Accepted Hedge Entries", counts.get("hedge_entries_accepted"), "", ""),
            ("Skipped Hedge Entries", counts.get("hedge_entries_skipped"), "", ""),
        )
        baseline = self._as_float(snapshot.get("starting_capital_usdt"))
        cards = "".join(
            self._render_metric_card(label, value, suffix, explanation_key=key, baseline=baseline)
            for label, value, suffix, key in (*primary_items, *secondary_items)
        )
        return f"""
        <div class="kpi-grid hedge-capital-grid">{cards}</div>
"""

    def _render_metric_card(
        self,
        label: str,
        value: Any,
        suffix: str,
        *,
        explanation_key: str = "",
        baseline: float | None = None,
    ) -> str:
        value_text = self._format_metric_value(label, value, suffix)
        value_class = self._value_class(label=label, value=value_text, baseline=baseline)
        label_html = self._escape(label)
        if explanation_key:
            label_html = (
                f'<span class="metric-label-with-action"><span>{label_html}</span>'
                f'{render_explanation_anchor(key=explanation_key, label_html="")}</span>'
            )
        return (
            '<div class="metric-card">'
            f"<span>{label_html}</span>"
            f'<strong class="{value_class}">{value_text}</strong>'
            "</div>"
        )

    @staticmethod
    def _render_panel_heading(title: str, explanation_key: str) -> str:
        return (
            '<h2 class="panel-title-with-action">'
            f"<span>{html.escape(title)}</span>"
            f'{render_explanation_anchor(key=explanation_key, label_html="")}'
            "</h2>"
        )

    def _render_entries_table(self, entries: list[Any]) -> str:
        if not entries:
            return '<div class="table-shell empty">No Hedge entries recorded yet.</div>'
        rows = "".join(self._render_entry_row(row) for row in entries)
        return f"""
        <div class="table-controls" data-table-controls="hedge-entries">
          <button type="button" class="table-control-button" data-table-prev="hedge-entries">Back</button>
          <button type="button" class="table-control-button" data-table-next="hedge-entries">Next</button>
          <label class="table-page-size-label">
            Rows
            <select class="table-page-size-select" data-table-size="hedge-entries">
              <option value="5" selected>5</option>
              <option value="10">10</option>
              <option value="25">25</option>
            </select>
          </label>
        </div>
        <div class="table-shell">
          <table class="runtime-table hedge-entries-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Hedge ID</th>
                <th>Side</th>
                <th>Source ID</th>
                <th>Entry</th>
                <th>Quantity</th>
                <th>Fee</th>
              </tr>
            </thead>
            <tbody data-table-body="hedge-entries">{rows}</tbody>
          </table>
        </div>
"""

    def _render_entry_row(self, row: Any) -> str:
        entry = row if isinstance(row, dict) else {}
        side = str(entry.get("side") or "")
        side_class = "value-green" if side == "LONG" else "value-red" if side == "SHORT" else "value-muted"
        return f"""
              <tr data-table-item>
                <td>{self._escape(entry.get("time_readable") or "-")}</td>
                <td>{self._escape(entry.get("hedge_entry_id") or "-")}</td>
                <td><strong class="{side_class}">{self._escape(side or "-")}</strong></td>
                <td>{self._escape(entry.get("source_position_id") or "-")}</td>
                <td><strong>{self._format_metric_value("Entry", entry.get("entry_price"), "USDT")}</strong></td>
                <td>{self._format_metric_value("Quantity", entry.get("quantity"), "BTC")}</td>
                <td><strong class="value-red">{self._format_metric_value("Fee", entry.get("entry_fee_usdt"), "USDT")}</strong></td>
              </tr>
"""

    @staticmethod
    def _render_table_script() -> str:
        return """
    <script>
      (() => {
        const body = document.querySelector('[data-table-body="hedge-entries"]');
        if (!body) return;

        const rows = Array.from(body.querySelectorAll('[data-table-item]'));
        const prev = document.querySelector('[data-table-prev="hedge-entries"]');
        const next = document.querySelector('[data-table-next="hedge-entries"]');
        const size = document.querySelector('[data-table-size="hedge-entries"]');
        let page = 0;

        const getPageSize = () => Number(size?.value || 5);
        const render = () => {
          const pageSize = getPageSize();
          const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
          page = Math.min(page, pageCount - 1);
          const start = page * pageSize;
          const end = start + pageSize;

          rows.forEach((row, index) => {
            row.hidden = index < start || index >= end;
          });

          if (prev) prev.disabled = page <= 0;
          if (next) next.disabled = page >= pageCount - 1;
        };

        prev?.addEventListener("click", () => {
          page = Math.max(0, page - 1);
          render();
        });

        next?.addEventListener("click", () => {
          page += 1;
          render();
        });

        size?.addEventListener("change", () => {
          page = 0;
          render();
        });

        render();
      })();
    </script>
"""

    def _render_row(self, label: str, value: Any, suffix: str) -> str:
        value_text = self._format_metric_value(label, value, suffix)
        value_class = self._value_class(label=label, value=value_text)
        return f"""
            <div class="row">
              <span>{self._escape(label)}</span>
              <strong class="{value_class}">{value_text}</strong>
            </div>
"""

    def _net_exposure_label(self, decision: dict[str, Any]) -> str:
        side = str(decision.get("net_exposure_side") or "FLAT")
        exposure = decision.get("net_exposure_usdt")
        return f"{side} {self._format_metric_value('Net Exposure', exposure, 'USDT')}" if side != "FLAT" else "FLAT"

    def _side_imbalance_label(self, decision: dict[str, Any]) -> str:
        side = str(decision.get("side_imbalance_side") or "FLAT")
        ratio = self._as_float(decision.get("side_imbalance_ratio"))
        if side in {"FLAT", "BALANCED"}:
            return side
        if ratio >= 999:
            return f"{side} ONE-SIDED"
        return f"{side} {self._format_number(ratio)}x"

    def _next_entry_capacity_label(self, decision: dict[str, Any]) -> str:
        can_open = bool(decision.get("can_open_next_entry"))
        remaining = self._format_count(decision.get("entries_until_capital_exhaustion_estimate"))
        label = "YES" if can_open else "NO"
        return f"{label} | {remaining} LEFT"

    def _format_metric_value(self, label: str, value: Any, suffix: str) -> str:
        if value in (None, ""):
            return "-"
        normalized_label = label.lower()
        if suffix == "%":
            text = self._format_percent(value)
        elif suffix == "" and any(
            token in normalized_label
            for token in (
                "entries",
                "events",
                "reset count",
                "accepted",
                "skipped",
            )
        ):
            text = self._format_count(value)
        else:
            text = self._format_number(value)
        if suffix == "x":
            return f"{text}x"
        if suffix:
            return f"{self._escape(text)} {self._escape(suffix)}"
        return self._escape(text)

    @staticmethod
    def _value_class(*, label: str, value: str, baseline: float | None = None) -> str:
        normalized_label = label.lower()
        normalized_value = value.upper()
        if normalized_label in {"open equity", "if closed now"} and baseline is not None and baseline > 0:
            number = FuturesHedgeOverviewRenderer._as_float(normalized_value)
            if number > baseline:
                return "value-green"
            if number < baseline:
                return "value-red"
            return "value-muted"
        if normalized_value == "YES":
            return "value-green"
        if normalized_value == "NO":
            return "value-red"
        if normalized_label == "entry capacity":
            return "value-green" if normalized_value.startswith("YES") else "value-red"
        if normalized_label == "liquidation risk":
            if normalized_value == "HIGH":
                return "value-red"
            if normalized_value in {"MEDIUM", "ELEVATED"}:
                return "value-amber"
            if normalized_value == "LOW":
                return "value-green"
            return "value-muted"
        if normalized_label == "peak capital" and baseline is not None and baseline > 0:
            number = FuturesHedgeOverviewRenderer._as_float(normalized_value)
            if number > baseline:
                return "value-green"
            if number < baseline:
                return "value-red"
            return "value-muted"
        if normalized_label == "lowest capital" and baseline is not None and baseline > 0:
            number = FuturesHedgeOverviewRenderer._as_float(normalized_value)
            if number < baseline:
                return "value-red"
            if number > baseline:
                return "value-green"
            return "value-muted"
        if "SHORT" in normalized_value:
            return "value-red"
        if "LONG" in normalized_value:
            return "value-green"
        if normalized_label == "available capital":
            return "value-amber"
        if normalized_label in {"used margin", "margin used"}:
            return "value-amber"
        if normalized_label == "danger distance":
            number = FuturesHedgeOverviewRenderer._as_float(normalized_value)
            if number <= 10:
                return "value-red"
            if number <= 30:
                return "value-amber"
            return "value-green"
        if any(token in normalized_label for token in ("pnl", "roe", "return", "profit", "run-up")):
            stripped = normalized_value.replace("USDT", "").replace("%", "").replace(",", "").strip()
            try:
                number = float(stripped)
            except ValueError:
                return "value-muted"
            if number > 0:
                return "value-green"
            if number < 0:
                return "value-red"
        if "drawdown" in normalized_label:
            return "value-red"
        if "fee" in normalized_label and "cash" not in normalized_label:
            return "value-red"
        return "value-muted"

    @staticmethod
    def _as_float(value: Any) -> float:
        text = str(value or "").replace("USDT", "").replace("%", "").replace(",", "").strip()
        try:
            return float(text or 0.0)
        except ValueError:
            return 0.0

    @staticmethod
    def _format_number(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if abs(number) >= 1000:
            return f"{number:,.2f}"
        if abs(number) >= 1:
            return f"{number:.2f}"
        return f"{number:.8f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_count(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return str(int(number))

    @staticmethod
    def _format_percent(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{number:,.2f}"

    @staticmethod
    def _escape(value: Any) -> str:
        return html.escape(str(value))
