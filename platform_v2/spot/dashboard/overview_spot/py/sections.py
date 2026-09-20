"""Section render helpers for the Overview page."""

from __future__ import annotations

from typing import Any

from platform_v2.spot.dashboard.explanation_system import render_explanation_anchor
from platform_v2.shared.frontend.components import render_runtime_hero, render_site_navigation
from platform_v2.shared.frontend.components import render_site_footer as render_shared_site_footer


def render_panel_intro(text: str) -> str:
    import html

    return f'<p class="panel-intro">{html.escape(text)}</p>'


def render_panel_note(html_text: str) -> str:
    return f'<p class="panel-note">{html_text}</p>'


def render_panel_heading(title: str, *, explanation_key: str | None = None) -> str:
    if not explanation_key:
        return f"<h2>{title}</h2>"
    trigger = render_explanation_anchor(
        key=explanation_key,
        label_html="",
    )
    return f'<h2 class="panel-title-with-action"><span>{title}</span>{trigger}</h2>'


def render_hero(*, status_line: str) -> str:
    return render_runtime_hero(
        title="Bitcoin Spot Live Trading Signals Dashboard",
        href="../overview_spot/index.html",
        intro="",
        subline=None,
    )


def render_navigation() -> str:
    return render_site_navigation(active_page="overview_spot")


def render_footer_status(*, status_line: str) -> str:
    return ""


def render_site_footer() -> str:
    return render_shared_site_footer()


def render_timeframe_stats(renderer: Any, *, card: dict[str, Any]) -> str:
    return "".join(
        f'<div><span>{renderer.escape(stat.get("label", "—"))}</span>'
        f'{renderer.strong(stat.get("value", "—"), kind=str(stat.get("kind") or "generic"))}</div>'
        for stat in (card.get("stats") or [])[:3]
    )


def render_timeframe_cards(renderer: Any, payload: dict[str, Any]) -> str:
    cards: list[str] = []
    for card in payload.get("timeframe_context_cards") or []:
        if card.get("signal") == "NO DATA":
            cards.append(
                '<article class="timeframe-card"><span>Missing</span><h3 class="value-muted">NO DATA</h3><div class="timeframe-stats"><div>No indicator snapshot available.</div></div></article>'
            )
            continue
        timeframe_label = str(card.get("label") or "—")
        tf_signal = str(card.get("signal") or "NO_SIGNAL")
        stats_html = render_timeframe_stats(renderer, card=card)
        cards.append(
            f"""
                <article class="timeframe-card">
                  <div class="timeframe-card-head">
                    <span>{renderer.escape(timeframe_label)}</span>
                    <h3 class="{renderer.value_class(tf_signal)}">{renderer.escape(tf_signal)}</h3>
                  </div>
                  <p class="timeframe-role">{renderer.escape(card.get('role') or 'Market context for this timeframe.')}</p>
                  <div class="timeframe-stats">{stats_html}</div>
                </article>
                """
        )
    return "".join(cards)


def render_main_grid(
    renderer: Any,
    payload: dict[str, Any],
    *,
    mtf_direction: str,
) -> str:
    return f"""
      <section class="grid">
        <article class="panel overview-primary-panel overview-panel-with-note">
          <div class="panel-head">
            {render_panel_heading("Primary Signal", explanation_key="overview.primary_signal.panel")}
          </div>
          {render_panel_intro("Current Bitcoin signal, price, and trade readiness.")}
          <div id="primary-signal-grid" class="metric-grid overview-metric-grid">
            {renderer.render_primary_signal(payload)}
          </div>
          {render_panel_note('See <a class="panel-note-link" href="../portfolio/">Portfolio</a> for open positions, closed trades, and portfolio outcomes.')}
        </article>

        <article class="panel overview-context-panel">
          <div class="panel-head">
            {render_panel_heading("Timeframe Context", explanation_key="overview.signal_context.panel")}
          </div>
          {render_panel_intro("Fast, primary, and higher-timeframe context in one view.")}
          <div class="timeframe-grid overview-timeframe-grid">
            {render_timeframe_cards(renderer, payload)}
          </div>
        </article>

        <article class="panel overview-snapshot-panel">
          <div class="panel-head">
            {render_panel_heading("Portfolio Snapshot", explanation_key="overview.portfolio_snapshot.panel")}
          </div>
          {render_panel_intro("Equity, return pace, net return, and open exposure.")}
          <div class="metric-grid overview-metric-grid">
            {renderer.render_portfolio_snapshot(payload)}
          </div>
        </article>

        <article class="panel overview-snapshot-panel">
          <div class="panel-head">
            {render_panel_heading("Trade Outcomes Snapshot", explanation_key="overview.trade_outcomes_snapshot.panel")}
          </div>
          {render_panel_intro("Closed-trade totals, hit distribution, and force-close activity.")}
          <div class="metric-grid overview-metric-grid">
            {renderer.render_trade_outcomes_snapshot(payload)}
          </div>
        </article>

        <article class="panel overview-strategy-panel overview-panel-with-note">
          <div class="panel-head">
            {render_panel_heading("Strategy Snapshot", explanation_key="overview.strategy_snapshot.panel")}
          </div>
          {render_panel_intro("Full-history signal mix and conversion, aligned with Strategy Edge.")}
          <div class="metric-grid overview-metric-grid">
            {renderer.render_strategy_snapshot(payload)}
          </div>
          {render_panel_note('See <a class="panel-note-link" href="../strategy_edge/">Strategy Edge</a> for full signal-side diagnostics.')}
        </article>

        <article class="panel overview-compact-chart-panel chart-panel">
          <div class="panel-head">
            {render_panel_heading("Equity Δ% from Start", explanation_key="overview.equity_chart.panel")}
          </div>
          {render_panel_intro("Equity drift from starting capital across recorded daily metric snapshots.")}
          <div class="chart-shell">
            <div id="overview-equity-chart" class="chart-canvas" aria-label="Equity delta chart"></div>
          </div>
        </article>
      </section>
"""
