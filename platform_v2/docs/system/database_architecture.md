# Database Architecture

Status: `active`  
Updated: `2026-09-12`

## Boundaries

```text
smartsignalhub_trading.sqlite3
  decisions, signals, permissions, orders, position events, capital,
  metrics, strategy/diagnostic outputs, Hedge, mutable engine state

smartsignalhub_market_data.sqlite3
  exchange observations keyed by venue, asset class, market type,
  symbol, timeframe, dataset, and event time

smartsignalhub_content.sqlite3
  normalized news batches and public-site content metadata
```

HTML, CSS, JavaScript, images, documentation, process locks, and generated
reports remain files. Process lock files are not business state and must not be
stored in SQLite.

## Expansion Contract

Market data always carries these dimensions:

```text
venue       binance, future exchanges, or data providers
asset_class crypto, equity, forex, commodity, ...
market_type spot, futures, options, cash, ...
symbol      BTCUSDT or a future instrument identifier
timeframe   5m, 15m, 4h, ...
dataset     candles, indicators, orderflow
```

This prevents Binance Spot and Binance Futures observations at the same time
from being mistaken for duplicates and allows future exchanges, crypto assets,
and equities to coexist in one market-data database.

## JSON Migration Rule

Routine runtime writes go only to SQLite. Old JSON can still be imported for
recovery or migration, and the database tool can generate a deliberate JSON
export. Research snapshots also create their own immutable JSON input from the
databases on demand. These exports are artifacts, not a second live store.

## Duplicate-data Rule

Diagnostics scans top-level runtime families for byte-equivalent rows stored in
different families. Derived summaries are allowed when they add a documented
aggregation. A second copy of a source event is not allowed. Futures current
positions are therefore derived from `futures_position_events` instead of
being written again to `futures_positions`.

The databases also avoid storing a full JSON document beside the same rows.
Each complete runtime or market observation is stored once. Small indexed
columns such as event time, symbol, side, status, and PnL are intentionally
kept beside the row payload so queries do not need to decode every record.
Those columns are search indexes, not a second event history.

## Runtime State Rule

Futures has mutable simulation-engine state, so its state is stored in the
trading database under `runtime_state/futures/simulation_engine`. Spot derives
its current portfolio from orders and position history and therefore does not
need an empty or invented `state` directory. Cycle markers are mutable state in
the trading database. Short-lived `fcntl` process-lock files live under the
operating system temporary directory, outside persistent runtime storage.

## Reset and Backup

Runtime reset is a full clean-start operation. It first moves `database`,
`spot`, `futures`, and `hedge` into one recoverable archive and leaves those
runtime roots absent. The next system start recreates only databases, mutable
state, and small process-control files that the active cycle actually needs. Market
history is therefore reset too; research that must retain a period should use
the created archive or an explicit database/JSON export.

Configuration defaults remain in code. Mutable engine state, open positions,
and capital continuity are runtime data and are intentionally cleared by a
full reset. Backup copies every active SQLite database through SQLite's backup
API for a consistent snapshot.

## September 12 clarification

Trading/market business rows are SQLite-primary. Public news generation also writes render-ready `public_site/news/data/news_items_YYYY-MM-DD.json` snapshots; these are an intentional content export, not a second trading ledger. Candle history includes 1m, 5m, 15m and 4h; indicators use 5m/15m/4h. See [runtime flow](runtime_flow.md) for scheduling and [current review](../current/system_review_20260912.md) for verified limits.
