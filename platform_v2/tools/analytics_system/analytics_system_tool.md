# Analytics System

Status: `active`
Created: `2026-06-03`
Updated: `2026-10-26`
Author: Codex
Purpose: Safe CLI wrapper for report-generating Spot/Futures analytics services.

## Cross-system baseline

The baseline command defaults to the live trading SQLite database and reads Spot, Futures, and Hedge data without changing
execution state and writes one comparable report under runtime artifacts:

```bash
python3 -m platform_v2.tools.analytics_system baseline
```

It describes retained trading results: current account metrics and timestamps,
latest-state-deduplicated Spot/Futures closed outcomes, wins/losses/breakeven,
net PnL, average net PnL, win rate, profit factor and direction breakdown.
Hedge remains a separate basket/reset account and is not presented as a collection
of independent closed trades.

The report identifies its storage mode and derives the date range from SQLite
document metadata. Missing or non-finite net outcomes are excluded and counted,
not treated as zero or wins. Explicit JSON exports remain supported only
when all three `--spot-data`, `--futures-data`, and `--hedge-data` directories are
provided together; they never silently mix with the live database.
Baseline exits with status `1` for missing subsystem metric inputs, `0` when
all three inputs are present. This is report availability, not a health verdict.
Reports are written in either case; profit or loss does not change the exit code.

Report schema version 2 removes `consistency_checks`. Their responsibility now
belongs to diagnostics: force-close counts, Futures trade-audit coverage,
Futures-to-Hedge links and Hedge summary totals. No integrity checker is imported
from analytics and no diagnostic writes analytics snapshots.

Net win rate uses finite closed net outcomes, including breakeven in its denominator.
Profit factor is positive net PnL divided by absolute negative net PnL; without
losses it is undefined (`null`), not infinity. These descriptive statistics are
neither a backtest nor a deployment recommendation. Live inputs may span a cycle;
diagnostics uses a single SQLite snapshot for ledger comparisons.

Historical strategy testing is a separate tool; see `../research/README.md`.

## Boundary

This tool does not open, close, reset, or publish positions. Baseline only writes
its reports. Other commands persist generated analytics and indicator snapshots
through the normal runtime stores; they are not all read-only database operations.

## Commands

```bash
python3 -m platform_v2.tools.analytics_system futures-audit-suite --date 2026-06-03
python3 -m platform_v2.tools.analytics_system futures-gates --date 2026-06-03
python3 -m platform_v2.tools.analytics_system futures-entry-audit --date 2026-06-03
python3 -m platform_v2.tools.analytics_system futures-entry-timing --date 2026-06-03
python3 -m platform_v2.tools.analytics_system futures-trade-audit --date 2026-06-03
python3 -m platform_v2.tools.analytics_system futures-short-failure --date 2026-06-03
python3 -m platform_v2.tools.analytics_system futures-tuning --date 2026-06-03
python3 -m platform_v2.tools.analytics_system futures-market-plan --date 2026-06-03 --symbol BTCUSDT --timeframe 15m
python3 -m platform_v2.tools.analytics_system futures-indicators --symbol BTCUSDT --timeframes 5m 15m 4h
python3 -m platform_v2.tools.analytics_system spot-indicators --symbol BTCUSDT --timeframes 5m 15m 4h
```

## Assistant Policy

The AI assistant may propose these actions after explicit confirmation and audit logging.
