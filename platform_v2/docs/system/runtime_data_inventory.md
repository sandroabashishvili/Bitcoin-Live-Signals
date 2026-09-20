# Runtime Data Inventory

Status: `active`  
Updated: `2026-09-12`

## Canonical databases

| Database | Canonical data | Long-term role |
|---|---|---|
| `smartsignalhub_trading.sqlite3` | signals, permissions, orders, position events, capital, metrics, analytics and engine state | trading truth and evaluation |
| `smartsignalhub_market_data.sqlite3` | candles, indicators, orderflow, venue and instrument dimensions | reusable market history |
| `smartsignalhub_content.sqlite3` | news batches and articles | public-site content history |

## Trading family classes

| Class | Examples | Why it exists |
|---|---|---|
| source events | signals, denied entries, orders, position events, hedge entries | immutable decision/trade history |
| current state | Futures simulation engine state | restart continuity; Spot derives state and has no separate state record |
| compact summaries | metrics, daily summaries, hedge equity timeline | fast dashboards and operational review |
| analytical outputs | market plans, gate effectiveness, entry audits, failure reports | strategy diagnosis and calibration |
| process control | temporary lock files and database cycle-marker state | duplicate-cycle/concurrency protection; not trade history |
| generated artifacts | replay, diagnostics, Markdown/JSON reports, video | reproducible output; not canonical runtime truth |

## Duplicate controls

`futures_positions` is a virtual projection from the last event for each
`position_id` in `futures_position_events`; it must not be persisted again.
Diagnostics compares top-level runtime families for exact duplicate rows and
raises a finding when the same complete event appears in more than one family.

Metrics and summaries may contain values calculated from events. They are not
duplicates when they have a documented aggregation purpose and do not copy an
entire source event unchanged.

## JSON on demand

Production readers and writers use database facades. A full runtime reset
archives and removes the database plus Spot, Futures, and Hedge runtime roots.
The next cycle recreates the required databases and only small process-control
files. JSON is generated only for an explicit database export, a frozen
research snapshot, or a report whose output format is intentionally JSON.

## September 12 clarification

Trading/market business rows are SQLite-primary. Public news generation also writes render-ready `public_site/news/data/news_items_YYYY-MM-DD.json` snapshots; these are an intentional content export, not a second trading ledger. Candle history includes 1m, 5m, 15m and 4h; indicators use 5m/15m/4h. See [runtime flow](runtime_flow.md) for scheduling and [current review](../current/system_review_20260912.md) for verified limits.
