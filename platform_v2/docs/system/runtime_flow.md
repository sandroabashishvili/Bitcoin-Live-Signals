# Runtime Flow

Updated: 2026-09-12. Active simulation behavior verified against code and post-reset SQLite rows.

`python3 -m platform_v2.tools.runtime_start_system` launches Spot, Futures and the Telegram listener. Futures cycles also rebuild Hedge replay. Each trading loop runs once immediately, then on a 15-minute boundary plus 60 seconds. Network and processing time add to this delay; it is not a guaranteed one-minute fill.

Each subsystem fetches its own Binance market: Spot or Futures. Candles are retained for **1m, 5m, 15m and 4h**. Indicators use 5m/15m/4h; 15m is the decision timeframe. A 500-bar fetch limit is a request window, not a retention limit. New observations merge by timestamp into accumulated SQLite history.

Sequence: closed candles → market-data SQLite → indicators/orderflow → directional scores → entry quality and permissions → fresh execution quote for actionable entries → simulated execution/position lifecycle → metrics → HTML. A previously processed candle marker prevents duplicate cycles.

The decision candle closes at `HH:14:59.999`, `HH:29:59.999`, `HH:44:59.999` or `HH:59:59.999` UTC. Human displays omit milliseconds. Decision time, execution quote time and position-open time are later, separate fields. Do not shift candle timestamps to the next minute for display.

An allowed entry uses a fresh Binance ticker price, not a historical candle close. Missing execution quotes block entry. TP/SL is rebuilt from closed-candle context at the execution price.

Exit resolution uses full closed **1m candles**, but runs inside the **15-minute main cycle**. There is no independent one-minute exit-monitor process. The 1m bar that began before entry is excluded. If TP and SL touch in one bar, SL wins. LONG profit protection becomes effective from the next closed 1m bar after activation.

Trading, market-data and content SQLite files live in `platform_v2/runtime/database/`. Trading JSON is an optional export/research artifact; generated news JSON is a public content snapshot and is an explicit exception. Logs and generated reports remain files.

A normal stop/start preserves state. A full reset archives databases and clears trading and market history; it is not required to load ordinary code changes. See [runbook](../operations/runbook.md) and [backup/reset](../operations/backup_and_reset.md).
