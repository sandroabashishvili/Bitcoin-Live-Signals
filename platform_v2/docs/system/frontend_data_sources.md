# Frontend Data Sources

Status: `active`  
Updated: `2026-09-12`  
Purpose: Show exactly which prepared backend data feeds each dashboard.

## Boundary

Browser HTML/CSS/JavaScript does not open SQLite and does not fetch runtime
JSON. Python page builders run on the backend, read through the labelled
runtime store, assemble a prepared payload, and pass it to renderers. Browser
code only presents that payload and performs visual interactions such as
sorting visible rows, pagination, navigation, and drawers.

```text
SQLite databases
        -> shared/backend/runtime_store
        -> backend services/page builders
        -> prepared page payload
        -> renderer
        -> browser presentation
```

## Page Map

| Dashboard | Store | Main backend families |
|---|---|---|
| Spot Overview | `spot` | `signals`, `denied_entries`, `orders`, `positions`, `metrics`, `daily_summaries`, indicator/orderflow health |
| Spot Portfolio | `spot` | `positions`, `orders`, `metrics` |
| Spot Strategy Edge | `spot` | `signals`, `denied_entries`; strategy evaluation is prepared by Spot backend services |
| Spot Trade Outcomes | `spot` | `signals`, `positions`, `metrics`; outcome evaluation is prepared by Spot backend services |
| Spot Orderbook | `spot` | `orderflow` prepared by the Spot orderbook backend service |
| Futures Overview | `futures` | `futures_signals`, `futures_metrics`, `futures_orders`, `futures_denied_entries`, strategy gate report, candles |
| Futures Portfolio | `futures` | `futures_positions`, `futures_orders`, `futures_metrics` |
| Futures Strategy Edge | `futures` | `futures_signals`, `futures_denied_entries`, `futures_metrics`, `futures_strategy_gate_effectiveness_reports` |
| Futures Trade Outcomes | `futures` | `futures_position_events`, `futures_metrics`, `futures_trade_gate_effectiveness_reports` |
| Futures Orderbook | `futures` | `orderflow_futures` prepared by the Futures orderbook backend service |
| Hedge Overview | `hedge` | `hedge_entries`, `hedge_basket_snapshots` (equity and LONG/SHORT basket PnL charts), `hedge_equity_timeline`, `hedge_daily_summaries` |

The canonical source files are:

```text
platform_v2/runtime/database/smartsignalhub_trading.sqlite3
platform_v2/runtime/database/smartsignalhub_market_data.sqlite3
```

The trading database supplies daily families. The market-data database supplies
candles, indicators, and orderflow. The browser itself does not access SQLite;
Python page builders prepare and render its payload.

`futures_positions` is a virtual latest-event projection, not a separately stored family. All eleven dashboard canonical paths preserve their subsystem `/spot/dashboard/`, `/futures/dashboard/` or `/futures_hedge/dashboard/` prefixes.
