# Frontend Pages

Status: `active baseline - reviewed 2026-09-12`  
Created: `2026-05-19`  
Author: Codex  
Purpose: Current frontend page map and page responsibilities.

## Public Site

```text
platform_v2/public_site/index.html
platform_v2/public_site/news/
platform_v2/public_site/resources/
platform_v2/public_site/assets/
platform_v2/public_site/sitemap.xml
platform_v2/public_site/robots.txt
```

## Spot Dashboard

```text
platform_v2/spot/dashboard/overview_spot/
platform_v2/spot/dashboard/portfolio/
platform_v2/spot/dashboard/trade_outcomes/
platform_v2/spot/dashboard/strategy_edge/
platform_v2/spot/dashboard/orderbook/
```

## Futures Dashboard

```text
platform_v2/futures/dashboard/overview_futures/
platform_v2/futures/dashboard/portfolio_futures/
platform_v2/futures/dashboard/trade_outcomes_futures/
platform_v2/futures/dashboard/strategy_edge_futures/
platform_v2/futures/dashboard/orderbook_futures/
```

## Futures Hedge Dashboard

```text
platform_v2/futures_hedge/dashboard/overview_hedge/
```

## Rule

Pages display prepared metrics. They do not compute trading truth.

## Page Responsibilities

Overview: compact current system state and snapshots from deeper pages.

Portfolio: open/closed positions, capital snapshot, expandable row details.

Trade Outcomes: executed trade outcomes and trade-level gate effectiveness.

Strategy Edge: signal/theoretical activity and strategy-level gate effectiveness.

Orderbook: orderflow/orderbook context.

Futures Hedge: independent Hedge account overview with Capital Snapshot, LONG/SHORT basket detail, Decision & Source, and copied-entry table.

News/Resources/Home: public/static product and content pages. Home also exposes
the Telegram bot and Mr.B AI representative as optional product-assistance
entry points.

## Shared Frontend Infrastructure

Shared frontend helpers:

```text
platform_v2/shared/frontend/components/py/
platform_v2/shared/frontend/components/css/
platform_v2/shared/frontend/charts/
```

Shared helpers render:

- page head/meta/OG tags
- global navigation
- dashboard subnavigation
- runtime clock strip
- site footer
- metric formatting

The shared footer includes the developer Portfolio beside the social links.
This footer is rendered into Spot, Futures, Hedge, News, and Resources pages;
the public Home footer mirrors the same link list.

Futures-only dashboard chrome lives in:

```text
platform_v2/futures/dashboard/components/
```

Use it only for Futures-specific runtime presentation such as the Futures hero that reads `futures_metrics`. Generic CSS, chart scripts, footer, page head, and metric formatting must stay in `platform_v2/shared/frontend/`.

Futures Hedge currently reuses shared frontend CSS/helpers and should follow the same table/control conventions as Futures dashboards.

Spot lifecycle metadata in the shared hero reads the latest `metrics` document
through the Spot runtime store. It must not scan compatibility JSON folders,
because SQLite is the canonical runtime source.

Futures Trade Outcomes and Strategy Edge pair each gate chart with one
directional gate table inside the same responsive card. Desktop uses two
columns; mobile stacks chart/table, then chart/table, matching the Spot reading
order.

## Navigation

Global navigation:

```text
Home
Spot
Futures
Hedge
News
Resources
```

Spot/Futures dashboard subnavigation:

```text
Overview
Portfolio
Trade
Strategy
Orderbook
```

Subnavigation exists only on Spot/Futures dashboard pages, not on News/Resources/Home.
Futures Hedge currently has one Overview page, so it uses only global navigation.

## Explanation System

Spot and Futures have explanation systems:

```text
platform_v2/spot/dashboard/explanation_system/
platform_v2/futures/dashboard/explanation_system/
```

Futures Hedge still needs its own explanation-system pass modeled after the Futures explanation system.

Use this for page-specific terms such as:

- Theoretical Open
- Theoretical TP
- Theoretical SL
- Entry Status
- Main Blocker
- Gate Effectiveness

## Public Metadata

`render_page_head` provides canonical URLs, Open Graph tags, Twitter card tags, theme color, favicon links, and optional JSON-LD schema.

Social sharing should use the shared page-head path rather than one-off metadata.

## Frontend Allowed Behavior

Allowed:

- pagination
- row expand/collapse
- visible-row filtering
- dropdown UI
- formatting/display classes
- mobile menu interaction

Not allowed:

- calculating PnL
- calculating fees
- calculating win rate
- calculating gate effectiveness
- rebuilding missing backend reports
- deciding permission/trading truth

## Page Ownership

Frontend page builders may assemble display payloads from prepared runtime families and backend content services. They must not invent trading/accounting values.

Spot page ownership:

| Page | Builder | Backend/content service | Runtime source |
| --- | --- | --- | --- |
| Home | `platform_v2/public_site/index.html` | static/shared frontend helpers | static page |
| News | `platform_v2/public_site/news/` | news pipeline builders | generated/static news content |
| Resources | `platform_v2/public_site/resources/py/page_builder.py` | shared frontend helpers | static curated content |
| Overview | `platform_v2/spot/dashboard/overview_spot/py/page_builder.py` | `OverviewPageContentService`, grouped payload helpers | `signals`, `denied_entries`, `orders`, `positions`, `metrics`, `daily_summaries` |
| Portfolio | `platform_v2/spot/dashboard/portfolio/py/page_builder.py` | `PortfolioPageContentService`, grouped payload helpers | `metrics`, `positions`, `orders` |
| Trade | `platform_v2/spot/dashboard/trade_outcomes/py/page_builder.py` | `StrategyPageContentService`, Spot strategy effectiveness services | `signals`, `metrics`, latest deduped `positions` |
| Strategy | `platform_v2/spot/dashboard/strategy_edge/py/page_builder.py` | `StrategyPageContentService`, `StrategyActivityPageContentService` | `signals`, `denied_entries`, `metrics` |
| Orderbook | `platform_v2/spot/dashboard/orderbook/py/page_builder.py` | `OrderbookPageContentService` | `orderflow/BTCUSDT/15m.json` |

Futures page ownership:

| Page | Builder | Backend/content service | Runtime source |
| --- | --- | --- | --- |
| Overview | `platform_v2/futures/dashboard/overview_futures/py/page_builder.py` | grouped payload helpers, Futures strategy content | `futures_metrics`, `futures_signals`, `futures_strategy_gate_effectiveness_reports` |
| Portfolio | `platform_v2/futures/dashboard/portfolio_futures/py/page_builder.py` | `PortfolioPageContentService`, grouped payload helpers | `futures_metrics`, `futures_positions`, `futures_orders` |
| Trade | `platform_v2/futures/dashboard/trade_outcomes_futures/py/page_builder.py` | `StrategyPageContentService`, grouped payload helpers | `futures_metrics`, `futures_signals`, `futures_position_events`, `futures_trade_gate_effectiveness_reports` |
| Strategy | `platform_v2/futures/dashboard/strategy_edge_futures/py/page_builder.py` | `StrategyPageContentService`, `StrategyActivityPageContentService` | `futures_signals`, `futures_denied_entries`, `futures_metrics`, `futures_strategy_gate_effectiveness_reports` |
| Orderbook | `platform_v2/futures/dashboard/orderbook_futures/py/page_builder.py` | `OrderbookPageContentService` | `orderflow_futures/BTCUSDT/orderflow_15m.json` |

Futures Hedge page ownership:

| Page | Builder | Backend/content service | Runtime source |
| --- | --- | --- | --- |
| Overview | `platform_v2/futures_hedge/dashboard/overview_hedge/py/page_builder.py` | `FuturesHedgeReplayService`, basket portfolio services | Hedge families in `smartsignalhub_trading.sqlite3`, sourced from Futures `OPENED` position events |

## Ownership Rule

If a page needs a metric that is not present in its runtime source, fix the backend content service or runtime report first.

Do not add frontend-side calculations for:

- net PnL
- gross PnL
- fees
- ROE
- win rate
- gate effectiveness
- theoretical TP/SL/open totals

## Publication identity

The public base is `https://sandro-abashishvili.de/Bitcoin-Live-Signals/`. Dashboard paths retain their subsystem prefix. Canonical, Open Graph URL and JSON-LD page identity must agree with this final path. Public root-level Spot dashboard aliases are retired. See [SEO/publishing](seo_and_publishing.md).
