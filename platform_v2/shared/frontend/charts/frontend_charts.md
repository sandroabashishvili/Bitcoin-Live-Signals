# Frontend Charts

Status: `active`
Created: `2026-05-19`
Updated: `2026-10-10`
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
  - Spot Primary/Confirmation and Futures LONG/SHORT gate-participation donuts
- `charts.css`
  - shared chart container styles

Notes:

- Charts are JavaScript-driven and use `ECharts`.
- `ECharts` is loaded from CDN in the generated page HTML.
- The earlier inline SVG draft has been removed.
- Backend `shared/backend/chart_payloads.py` owns chart counts, percentages,
  denominators, win rates, equity changes/extrema and orderflow chart values.
- JavaScript only maps prepared values to chart primitives, formats labels and
  handles themes, geometry and interactions. No metric-recalculation fallback.
- Gate counts are overlapping participations, not unique trades/signals. Closed
  win rates use net-positive participation counts; theoretical win rates exclude
  open setups. Zero counts remain zero; missing outcomes get an empty state.
- Equity shows recorded observations only, without a fabricated zero point.
- Orderflow charts consume supplied delta/cumulative values, preserving the
  backend baseline even when only a history window is displayed.
