# Analytics System

Status: `active`
Created: `2026-06-03`
Updated: `2026-07-30`
Author: Codex
Purpose: Safe CLI wrapper for report-generating Spot/Futures analytics services.

## Cross-system baseline

The baseline command reads Spot, Futures, and Hedge data without changing
execution state and writes one comparable report under runtime artifacts:

```bash
python3 -m platform_v2.tools.analytics_system baseline
```

It checks the accounting boundary between metrics and raw ledgers, including:

- Spot force-close counts
- Futures closed trades and trade-audit rows
- Futures entries and Hedge entries
- Hedge entry/reset summary totals

For strategy research, prefer a frozen snapshot:

```bash
python3 -m platform_v2.tools.research snapshot
python3 -m platform_v2.tools.research baseline /home/sandro/research_snapshots/<snapshot>
```

## Boundary

This tool generates analytics snapshots/reports only. It does not open, close, reset, or publish trading runtime state.

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
