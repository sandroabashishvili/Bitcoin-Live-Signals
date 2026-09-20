# Frontend Charts

Status: `active`
Created: `2026-05-19`
Updated: `2026-06-12`
Author: Codex
Purpose: Shared frontend chart assets and chart ownership notes.

Current chart layer for `platform_v2`.

Implemented:

- `common.js`
  - shared ECharts bootstrap and theme helpers
- `equity_delta_chart.js`
  - `Overview` chart for `Equity Δ% from Start`
- `orderflow_delta_chart.js`
  - `Orderbook` chart for net delta and cumulative delta
- `portfolio_pnl_charts.js`
  - `Portfolio` chart for net PnL per closed trade
- `strategy_logic_evaluation.js`
  - `Strategy` donuts for primary vs confirmation gate evaluation
- `charts.css`
  - shared chart container styles

Notes:

- Charts are JavaScript-driven and use `ECharts`.
- `ECharts` is loaded from CDN in the generated page HTML.
- The earlier inline SVG draft has been removed.
