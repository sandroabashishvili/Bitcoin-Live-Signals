# Runtime Store

Status: `active - three SQLite-primary databases`  
Created: `2026-05-19`  
Updated: `2026-09-12`  
Author: Codex  
Purpose: Document runtime data families, storage ownership, and long-term log policy.

## Current Principle

Runtime families are database records used by:

- backend metrics builders
- simulation state
- frontend page builders
- analytics/audit reports
- Telegram bot summaries

Each family has a clear owner service. A page may read a family, but a frontend
module must not become the owner of analytics calculations.

## Storage Model

The runtime store uses a database-first model:

```text
backend writer -> canonical SQLite store
backend reader -> SQLite query/facade
frontend       -> stable backend payloads rendered into HTML
research       -> immutable JSON snapshot exported on demand
```

SQLite is split by responsibility:

```text
platform_v2/runtime/database/smartsignalhub_trading.sqlite3
platform_v2/runtime/database/smartsignalhub_market_data.sqlite3
platform_v2/runtime/database/smartsignalhub_content.sqlite3
```

`trading` owns decisions, ledgers, strategy/audit outputs, capital, and mutable
engine state. `market_data` owns venue-labelled candles, indicator snapshots,
and orderflow with `venue`, `asset_class`, `market_type`, `symbol`, and
`timeframe` boundaries. `content` owns collected public-site news; images and
rendered HTML remain files.

Each complete runtime row is stored once. The document table keeps only its
identity, type, row count, hash, source label, and update time; the row table
keeps the payload plus small query indexes. Legacy JSON remains importable but
is no longer required beside every database document.

Daily ledgers use the trading database. Candles, indicator snapshots, and
orderflow use the market-data database as the primary repository. News
generation persists normalized items in the content database before rendering
public HTML.

`futures_positions` is no longer a second stored ledger. Current position state
is projected from the latest row per `position_id` in
`futures_position_events`. This removes a fully duplicated data family while
preserving the same consumer contract.

Spot intentionally has no mutable engine-state record: its current portfolio
is reconstructed from position/order history. Futures needs mutable simulation
continuity and stores it in the trading database. A missing Spot `state` folder
is therefore not a defect.

## Runtime Roots

```text
platform_v2/runtime/spot/
platform_v2/runtime/futures/
platform_v2/runtime/hedge/
```

These roots are optional and appear only for small process-control files or
explicitly generated artifacts. Daily business ledgers no longer require JSON
family directories there.

All runtime storage code lives in one package:

```text
platform_v2/shared/backend/runtime_store/
```

Its `spot.py`, `futures.py`, and `hedge.py` modules label ownership without
duplicating reader/writer packages. System roots are defined once in
`system_registry.py`.

## Database Operations

```bash
python3 -m platform_v2.tools.runtime_database_system --import-json
python3 -m platform_v2.tools.runtime_database_system --check-parity
python3 -m platform_v2.tools.runtime_database_system --export-root /tmp/runtime-json-export
```

`--import-json` is a recovery/migration operation. `--check-parity` is useful
when an old JSON dataset is being migrated. `--export-root` is the explicit
way to create a portable JSON copy without enabling routine dual writes.

## Spot Runtime Families

Current Spot family names:

```text
signals
denied_entries
orders
positions
force_closes
metrics
cycle_runs
daily_summaries
candles
orderflow
indicator_snapshots
```

Main frontend-used Spot families:

```text
signals
denied_entries
orders
positions
force_closes
metrics
cycle_runs
daily_summaries
orderflow
indicator_snapshots
```

## Futures Runtime Families

Current Futures family names:

```text
futures_signals
futures_denied_entries
futures_orders
futures_position_events
futures_force_closes
futures_trade_entry_audits
futures_entry_timing_summaries
futures_trade_audit_reports
futures_short_failure_reports
futures_strategy_gate_effectiveness_reports
futures_trade_gate_effectiveness_reports
futures_market_plans
futures_metrics
futures_cycle_runs
futures_daily_summaries
candles_futures
orderflow_futures
indicator_snapshots_futures
engine_state_futures
```

Frontend-used Futures families include signals, denied entries, orders, positions, force closes, metrics, cycle runs, daily summaries, orderflow, and the two gate-effectiveness report families.

Audit/research-focused Futures families include trade entry audits, entry timing summaries, trade audit reports, short failure reports, market plans, and indicator snapshots.

## Futures Hedge Runtime Families

Current Futures Hedge family names:

```text
hedge_entries
hedge_basket_snapshots
hedge_reset_events
hedge_daily_summaries
```

Hedge reads confirmed Futures entry events as triggers:

```text
futures_position_events where event == OPENED
```

Hedge writes only to its own labelled database families:

```text
smartsignalhub_trading.sqlite3 / system=hedge
```

Ownership boundary:

```text
Futures supplies side/time/price from confirmed entries.
Futures Hedge owns capital, sizing, leverage, fees, baskets, reset logic, and runtime/data ledgers.
```

Assistant, Telegram, backup, and dashboard integrations should read the Hedge
families through the shared runtime-store facade.

## Futures Time Fields

Futures runtime rows should keep candle and decision times explicit:

```text
timestamp_ms       canonical event timestamp in milliseconds
time_readable      human-readable form of timestamp_ms
candle_open_time   source candle open label
candle_close_time  source candle close label
decision_time      actual signal permission/quote decision time
opened_at          actual paper fill/open time
opened_at_ms       actual paper fill/open timestamp in milliseconds
signal_reference_price  closed-candle price used by signal logic
entry_price        execution-time Binance quote used by the position
execution_quote_source  quote provenance
```

For 15m signal rows, `candle_open_time` and `candle_close_time` are different by about 15 minutes:

```text
candle_open_time   2026-06-01 23:30:00Z
candle_close_time  2026-06-01 23:44:59Z
decision_time      2026-06-01 23:46:00Z
opened_at          2026-06-01 23:46:00Z
```

Frontend pages may display these fields, but they must not recalculate or reinterpret event timing.

## Strategy vs Trade Gate Reports

These must stay separate:

```text
futures_strategy_gate_effectiveness_reports
futures_trade_gate_effectiveness_reports
```

Strategy report = theoretical/signal-side evaluation.

Trade report = executed-trade outcome evaluation.

Frontend must read these reports. It must not rebuild these analytics inside page builders.

## Naming Rule

Futures files should make their domain visible where ambiguity is likely. For example, futures terminal artifacts were changed toward names such as:

```text
candles_5m.json
candles_15m.json
candles_4h.json
orderflow_futures/BTCUSDT/orderflow_15m.json
```

## Retention

Raw market observations are normally long-lived because they are the basis for
local charts, replay, and future model research. Trading event ledgers are also
normally long-lived. Daily summaries and metrics are compact derived views and
may be rebuilt, but are retained because they make diagnostics and dashboards fast.
Generated research/diagnostic reports are artifacts rather than canonical
business data and may later receive a separate age/count retention policy.

Runtime reset is deliberately stronger than retention: it archives and removes
all three databases plus Spot/Futures/Hedge runtime roots. A restart rebuilds
storage on demand. The archive preserves the previous period for later research.
Backup is the main additional safety boundary until automatic artifact retention
is introduced.

## September 12 clarification

Trading/market business rows are SQLite-primary. Public news generation also writes render-ready `public_site/news/data/news_items_YYYY-MM-DD.json` snapshots; these are an intentional content export, not a second trading ledger. Candle history includes 1m, 5m, 15m and 4h; indicators use 5m/15m/4h. See [runtime flow](runtime_flow.md) for scheduling and [current review](../current/system_review_20260912.md) for verified limits.
