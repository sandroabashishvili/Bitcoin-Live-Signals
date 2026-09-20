# Futures Hedge

Status: `active paper replay; reviewed 2026-09-12`
Created: `2026-06-08`
Author: Codex
Purpose: Define the Futures Hedge/accumulation strategy as the third SmartSignalHub trading system.

## System Identity

SmartSignalHub now has three separate trading strategy systems:

```text
Spot
Futures
Futures Hedge
```

Futures Hedge is not just a one-off test and it is not a small setting inside the Futures strategy.

It is a separate strategy subsystem with its own:

```text
folder
runtime output
portfolio state
risk rules
reset logic
active overview dashboard
documentation
```

The first implementation stage is read-only replay/paper mode so the strategy can be measured before it affects live or normal Futures behavior.

## Strategy Input And Behavior

Futures Hedge listens to actual Futures entry events, then manages its own independent Hedge entries as two accumulated baskets instead of independent TP/SL trades.

The Hedge system does not consume raw Futures signals directly.

Entry source:

```text
futures_position_events where event == OPENED
```

This means denied Futures signals, blocked setups, and weak signals do not enter Hedge unless the normal Futures engine actually opened a position.

The opened Futures position is not copied as a full position contract. It is used only as an entry trigger:

```text
direction
entry time
entry price
symbol/timeframe context
```

Hedge then creates its own virtual position using Hedge-owned capital, position size, leverage, margin, and fee rules.

This is the key ownership rule:

```text
Futures decides only whether an entry is allowed.
Futures Hedge decides what to do with that entry inside its own account.
```

So Futures Hedge behaves like an independent trader that receives entry permission from Futures, but trades with its own budget and its own risk model.

## Agreed Model

```text
Starting capital: 3000 USDT
Position trigger source: actual Futures OPENED events
Position size: Hedge-owned setting
Leverage: Hedge-owned setting
Margin: Hedge-owned calculation
Fees: Hedge-owned fee model
LONG basket: all copied LONG entries
SHORT basket: all copied SHORT entries
TP: ignored by Hedge
SL: ignored by Hedge
Futures force close: ignored by Hedge
Hedge close: basket-level reset only when the next Hedge entry cannot be opened
```

Hedge keeps two virtual positions:

```text
one aggregated LONG basket
one aggregated SHORT basket
```

Each basket has:

```text
entry count
total notional
total margin
quantity
average entry
unrealized PnL
fees
ROE on used margin
```

## Reset Rule Direction

The first reset rule is portfolio-level, not per-position.

Draft rule:

```text
If the next Hedge entry cannot be opened from Hedge capital,
close both LONG and SHORT baskets,
record realized PnL,
restart with remaining equity.
```

There is no separate max-margin rule and no side-imbalance blocker in the first version.
Side imbalance is visible as a dashboard metric only; it does not block entries.

## Current Quick Check

On `2026-06-08`, the existing Futures history showed this rough aggregated state:

```text
LONG trades: 9
LONG notional: 4500 USDT
LONG average entry: 63704.52
LONG net PnL: about -40.73 USDT

SHORT trades: 15
SHORT notional: 7500 USDT
SHORT average entry: 63954.42
SHORT net PnL: about +89.44 USDT

Net book PnL: about +48.71 USDT
Net exposure: 3000 USDT SHORT
```

This was only a manual calculation from current runtime data. It is not yet a formal replay report.

## Missing Risk Items For First Version

The first paper/replay version must report these as missing until they are implemented:

```text
Liquidation price
Funding fees
Slippage
Exchange hedge-mode behavior
Maximum exposure growth
Side-imbalance blocker
Basket reset logic
Long/short capital allocation
Longer historical sample
```

Current first-pass risk visibility:

```text
Liquidation Risk: heuristic LOW / ELEVATED / MEDIUM / HIGH label based on worst basket ROE.
Side Imbalance: larger LONG/SHORT notional side and ratio.
Margin Used %: used Hedge margin divided by current Hedge open equity.
Worst Basket ROE: weaker LONG/SHORT basket ROE, capped at 0 when both baskets are positive.
Danger Distance: remaining percentage points before the first HIGH-risk threshold at -80% ROE.
```

These are visibility metrics only. They are not exchange-grade liquidation modeling and do not change Hedge entry or reset behavior.

## First Replay Command

```bash
python3 -m platform_v2.futures_hedge replay
```

Result:

```text
Hedge families are refreshed in smartsignalhub_trading.sqlite3.
```

The command reads Futures data, but writes only into Futures Hedge-owned
database families.

Build the browser page:

```bash
python3 -m platform_v2.futures_hedge build-page
```

Page output:

```text
platform_v2/futures_hedge/dashboard/overview_hedge/index.html
```

Runtime chain:

```text
runtime_start_system
-> futures run loop
-> successful non-skipped Futures cycle
-> Futures analytics/pages
-> Futures Hedge replay
-> Futures Hedge overview page
```

Terminal output:

```text
Futures Cycle
[futures] frontend updated (...) | Futures dashboard pages only
Hedge Replay
[hedge] frontend updated (1) | overview_hedge
```

Hedge is not a third endless runtime process yet. It is refreshed inside the
Futures cycle because it reads confirmed Futures `OPENED` events as triggers.
The terminal output keeps it visually separate so Futures strategy output and
Hedge basket accounting are not mixed.

`runtime_reset_system` also rebuilds the Hedge replay and overview page after resetting Spot/Futures runtime.

Frontend/public chain:

```text
shared frontend CSS/helpers -> Hedge overview page
Spot/Futures/Hedge global navigation -> Hedge link
sitemap_system -> includes Futures Hedge dashboard URLs
github_publish_system -> syncs futures_hedge/dashboard into the Pages repo
```

Manual full refresh:

```bash
python3 -m platform_v2.futures_hedge refresh
```

Current first-pass output fields:

```text
profile
source boundary
source counts
final mark price
final snapshot
estimated close equity after exit fees
decision summary
LONG basket
SHORT basket
max drawdown
reset events
skipped entries
limitations
```

Current overview page sections:

```text
Capital Snapshot: full account and risk snapshot from Hedge runtime/data, including total account fees
LONG Basket: count, margin, notional, quantity, average entry, mark price, unrealized PnL, basket fees, ROE
SHORT Basket: count, margin, notional, quantity, average entry, mark price, unrealized PnL, basket fees, ROE
Basket PnL charts: separate compact LONG and SHORT unrealized-PnL history from Hedge basket snapshots
Hedge Entries: latest copied Futures OPENED entries with Hedge id, side, source id, price, quantity, and fee
Runtime header: system clock, next signal countdown, strategy start, and elapsed runtime
```

The Hedge overview should keep a complete operational picture. It should not hide capital, fee, leverage, source, or entry-level details merely because they are technical. The page is a trading/operator dashboard, not a marketing page.

Hedge Entries table behavior:

```text
Default rows: latest 5 entries
Pagination: Back / Next and row-count selector, without a visible page counter
Row expansion: none on the first-pass overview
Color logic: LONG/positive/YES values use green, SHORT/negative/NO/drawdown values use red
```

Hedge equity chart:

```text
Title: Equity Δ% from Start
Primary source: smartsignalhub_trading.sqlite3 / hedge_basket_snapshots
Fallback source: smartsignalhub_trading.sqlite3 / hedge_equity_timeline
Frontend: platform_v2/shared/frontend/charts/equity_delta_chart.js
```

The chart uses full Hedge-owned basket snapshot history when available and
measures Hedge equity against the configured Hedge starting capital. It falls
back to Hedge-owned `cycle_snapshot` rows only if basket snapshots are missing.
It does not read Spot or Futures portfolio equity.

Each LONG/SHORT basket card also embeds a compact unrealized-PnL history chart.
Both charts read the prepared `hedge_basket_snapshots` payload generated by the
Hedge page builder. Browser code only plots the supplied timestamp, PnL, margin,
and entry count; it does not recompute Hedge accounting.

An empty post-reset rebuild may have no market candle and therefore a zero mark
price. That placeholder is not persisted in `hedge_equity_timeline`; only
market-timed snapshots with a positive mark price belong on the equity time
axis. This prevents a wall-clock reset placeholder from sorting after the first
closed-candle snapshot.

Capital Snapshot color and naming rules:

```text
Open Equity / If Closed Now are green above starting capital, red below starting capital, neutral when equal.
Fees are red because they reduce account value.
Liquidation Risk is green for LOW, amber for ELEVATED/MEDIUM, and red for HIGH.
Side Imbalance follows the larger side: LONG green, SHORT red, balanced neutral.
Margin Used is amber because it is capital pressure.
Worst Basket ROE follows PnL/ROE color logic.
Danger Distance is green above 30%, amber from 10% to 30%, and red at 10% or below.
```

Current explanation layer:

```text
platform_v2/futures_hedge/dashboard/explanation_system/
```

The Hedge overview has a first-pass metric explanation layer. Hedge owns the
explanation data and loader, while the drawer UI, CSS, JavaScript, common models,
and render helpers are reused from:

```text
platform_v2/shared/frontend/explanation_system/
```

Covered first-pass items:

```text
Capital Snapshot
Open Equity
If Closed Now
Entry Capacity
Peak Capital / Lowest Capital
Net Exposure
Side Imbalance
Margin Used
Worst Basket ROE
Danger Distance
Liquidation Risk
LONG Basket
SHORT Basket
Hedge Entries
```

The explanation layer is informational only. It does not change Hedge replay,
entry handling, reset behavior, or risk rules.

Hedge-owned database families:

```text
hedge_entries
hedge_basket_snapshots
hedge_reset_events
hedge_daily_summaries
hedge_equity_timeline
```

These families are rebuilt from replay and are the integration source for future Hedge readers, assistant answers, Telegram summaries, backup checks, and dashboard expansion. The replay artifact remains a report artifact, not the only source of Hedge state.

The Hedge overview dashboard reads these Hedge database ledgers. If the ledgers
are empty, it rebuilds replay once and reads them again.

`hedge_equity_timeline` stores Hedge-owned live cycle snapshots:

```text
point_type: cycle_snapshot
timestamp_ms / time_readable
mark_price
equity_usdt
estimated_close_equity_usdt
available_capital_usdt
used_margin_usdt
unrealized_pnl_usdt
realized_pnl_usdt
total_fees_usdt
reset_count
entry counts
net exposure
side imbalance
margin used %
worst basket ROE
danger distance
liquidation risk label
```

Peak Capital, Lowest Capital, Max Drawdown, and the chart use Hedge-owned basket snapshots when available, not Futures candle history. The live equity timeline is a fallback source. Futures candles are still used for the current mark price in replay.

## Why Separate System

Futures and Futures Hedge have different jobs.

```text
Futures = entry filter plus normal independent TP/SL lifecycle
Futures Hedge = separate basket-level position management strategy
```

Keeping Hedge separate prevents accidental changes to the working Futures runtime.

## Shared Folder Boundaries

Futures Hedge should use existing systems deliberately, not mix ownership.

### `platform_v2/futures/`

Used only as the source of confirmed entry triggers and market marks:

```text
futures_position_events where event == OPENED for side/time/price
futures 15m candles for current/replay mark prices
existing Futures dashboard style as a visual reference
```

Not allowed in the first stage:

```text
changing Futures TP/SL behavior
rewriting Futures positions
writing Hedge output into Futures runtime
inheriting Futures capital
inheriting Futures position size
inheriting Futures leverage/margin
inheriting Futures fee model
```

### `platform_v2/shared/`

Used only for reusable non-strategy code:

```text
frontend helpers
shared visual components
shared formatting helpers if truly domain-neutral
```

Hedge trading logic must not live in `shared`.

### `platform_v2/tools/`

Used only for cross-system operational wrappers.

Hedge strategy commands live in the Hedge subsystem:

```text
python3 -m platform_v2.futures_hedge replay
python3 -m platform_v2.futures_hedge build-page
python3 -m platform_v2.futures_hedge refresh
```

Tools can call Hedge services later for diagnostics, assistant, Telegram, backup, sitemap, or publishing integration. Tools must not own Hedge strategy logic.

### `platform_v2/docs/`

Used for documentation only:

```text
strategy rules
architecture decisions
runbook
active tasks
known limitations
```

Docs describe the system; they do not implement it.

### `platform_v2/public_site/`

Used later only for public navigation and SEO/shared website pages.

The Hedge dashboard source should live under:

```text
platform_v2/futures_hedge/dashboard/
```

The public site may link to that page, but does not own Hedge strategy logic.

## Current Folder

```text
platform_v2/futures_hedge/
```

Initial areas:

```text
config/
services/replay/
services/portfolio/
services/risk/
services/
dashboard/
dashboard/overview_hedge/
```

## First Implementation Status

The first read-only replay command now:

```text
1. Loads Futures OPENED events.
2. Loads 15m Futures candles as the final mark price.
3. Converts each Futures OPENED event into a Hedge-owned virtual entry.
4. Rebuilds LONG and SHORT baskets over time.
5. Ignores original Futures closes.
6. Applies the selected basket reset rule.
7. Writes Hedge runtime families into `smartsignalhub_trading.sqlite3`.
8. Keeps JSON as an explicit export/research format only.
9. Upserts one Hedge-owned `cycle_snapshot` into hedge_equity_timeline.
10. Builds the Hedge overview dashboard under futures_hedge/dashboard/overview_hedge/.
```

No live trading and no normal Futures runtime change in the first implementation.

The active Futures cycle rebuilds Hedge replay and its overview. Policy was not changed during the September 12 maintenance pass. Its Futures OPENED-event dependency is intentional.
