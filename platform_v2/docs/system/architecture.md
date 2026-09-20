# System Architecture

Status: `active baseline - Futures scoring and exit boundaries updated`  
Created: `2026-05-19`  
Updated: `2026-09-12`  
Author: Codex  
Purpose: Current high-level architecture of `platform_v2`.

## System Shape

`platform_v2` is a simulation-first Bitcoin signal, execution, and analytics platform.

The platform has two independent signal systems plus a Futures-derived Hedge basket simulation:

- Spot: BTCUSDT spot simulation, BUY-only.
- Futures: BTCUSDT futures simulation, LONG/SHORT/NO_SIGNAL with x5 isolated context.
- Hedge: paper baskets triggered by Futures OPENED events; own account and reset policy.

Futures signal scoring keeps the six-component decision contract in
`futures_component_score_service.py`. Structure/ATR-distance calculations are
owned by `futures_structure_score_service.py`; the component service remains
the stable facade used by live decisions and historical replay. This split is
organizational only and does not alter score values.

Core layers:

- spot/domain and futures/domain: typed entities and trading contracts.
- spot/services and futures/services: signal logic, position lifecycle, metrics, analytics, and orchestration.
- runtime/database: canonical trading, market-data, and content databases.
- runtime/artifacts and runtime/logs: generated reports and operational logs.
- public_site: public Home, News, Resources, assets, sitemap, and robots.
- spot/dashboard and futures/dashboard: generated static dashboard pages that display prepared data.
- shared/frontend: shared CSS, navigation helpers, page chrome, and chart assets.
- shared/backend: reusable Python contracts, serializers, time helpers, runtime-ledger primitives, persistence, market value objects, and strategy-neutral arithmetic.
- tools: reset, start, backup, publishing, research, reels, and operational utilities.
- tools/ai_assistant: planned SmartSignalHub-aware assistant with deterministic runtime/code readers and optional model explanations.

## Main Boundaries

Spot backend/runtime now lives under:

```text
platform_v2/spot/
```

Futures has a dedicated subsystem under:

```text
platform_v2/futures/
```

Shared services remain at root only when both systems use them. System tools and docs stay at root.

Backend dependency direction is one-way:

```text
Spot / Futures / Hedge / tools -> shared/backend
shared/backend -X-> strategy-specific services
```

The diagnostics suite flags reverse imports, exact cross-file function
duplication, unreachable backend statements, oversized/complex services, and
SQLite health or optional migration-parity drift.

Frontend/dashboard ownership is split:

```text
platform_v2/public_site/          # public static site: Home, News, Resources, assets
platform_v2/spot/dashboard/       # Spot dashboard pages
platform_v2/futures/dashboard/    # Futures dashboard pages
platform_v2/shared/frontend/      # shared frontend components and charts
```

The old mixed `platform_v2/frontend` and `platform_v2/futures/frontend` paths are retired. Permanent compatibility wrappers should not be added back.

## Runtime Outputs

Trading and Hedge ledgers write to:

```text
platform_v2/runtime/database/smartsignalhub_trading.sqlite3
```

Candles, indicators, and orderflow write to:

```text
platform_v2/runtime/database/smartsignalhub_market_data.sqlite3
```

Runtime data is generated output. It is not hand-edited policy.

SQLite is canonical. Trading JSON is created by explicit migration/export, research snapshot or report commands; it is not a second live trading ledger. Public news snapshots are a separate content export.

## Futures Simulation Boundary

Futures simulation orchestration lives in:

```text
platform_v2/futures/services/simulation/directional_futures_simulation_service.py
```

The orchestration file should stay focused on the cycle sequence. Supporting logic is split into focused services:

```text
entry_permission_context_service.py  # market-plan, entry-location, permission override context
entry_event_writer_service.py        # signal, denied-entry, opened-position, and order rows
position_lifecycle_service.py        # existing-position TP/SL/profit-lock close flow
position_exit_resolver.py            # deterministic fixed and managed candle exit resolution
cycle_summary_builder.py             # run-loop summary payload
position_service.py                  # position payloads and close calculations
metrics_service.py                   # equity/PnL/exposure aggregation
runtime_store.py                     # runtime ledger read/write
state_store.py                       # engine state read/write and migration
```

New permission or lifecycle logic should go into the focused service first, not back into the orchestration file.

## Frontend Rule

Backend services prepare metrics and page content. Frontend pages display those prepared values and may only do presentation behavior such as pagination, filtering visible rows, highlighting, or expand/collapse.

Frontend must not calculate trading/accounting truth.

## AI Assistant Boundary

The trusted SmartSignalHub assistant is planned as an internal tool:

```text
platform_v2/tools/ai_assistant/
```

It should read runtime/docs/source files through deterministic Python readers before asking a model to explain anything.

It must not be mixed into:

```text
platform_v2/tools/telegram_bot_system/
```

Telegram may become a transport/UI surface later, but assistant logic should stay in `tools/ai_assistant`.

The assistant may write generated reports/logs only under:

```text
platform_v2/runtime/artifacts/ai_assistant/
platform_v2/runtime/logs/tools/
```

## Archive Source

Older architecture notes are archived at:

```text
/home/sandro/SmartSignalHub/docs_archive_platform_v2/
```

## September 12 clarification

Trading/market business rows are SQLite-primary. Public news generation also writes render-ready `public_site/news/data/news_items_YYYY-MM-DD.json` snapshots; these are an intentional content export, not a second trading ledger. Candle history includes 1m, 5m, 15m and 4h; indicators use 5m/15m/4h. See [runtime flow](runtime_flow.md) for scheduling and [current review](../current/system_review_20260912.md) for verified limits.
