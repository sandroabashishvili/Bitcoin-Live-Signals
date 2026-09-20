# Telegram Bot

Status: `active baseline - Hedge readers and polling backoff added`  
Created: `2026-05-19`  
Updated: `2026-06-13`  
Author: Codex  
Purpose: Telegram bot commands, alerts, and formatting rules.

## Current Principles

Telegram bot must not calculate trading/accounting truth.

It should use backend/runtime-prepared values for:

- open positions
- ROE
- unrealized PnL
- capital
- net return
- fees

## Verified Scope

This baseline covers active commands, runtime sources, message-builder responsibilities, HTML formatting direction, and local subscriber state.

## Formatting Direction

Telegram messages should be readable on a phone notification:

- event visible in the first line
- Spot/Futures/Hedge context clear
- important values bold where Telegram HTML supports it
- positive/negative values visually distinguishable with simple text markers

Bot output must stay consistent with runtime/frontend metrics.

## AI Assistant Boundary

The Telegram bot is not the AI assistant implementation.

Future Telegram commands may call the planned assistant, for example:

```text
/ask ბოლო ფუჩერს სიგნალზე რას მეტყვი?
```

But assistant logic should live in:

```text
platform_v2/tools/ai_assistant/
```

Telegram should remain a transport and notification layer. It should not own runtime readers, intent routing, model prompts, or assistant reasoning.

## Runtime Source

Telegram reads prepared runtime-store data from SQLite:

Spot:

```text
smartsignalhub_trading.sqlite3: spot/metrics and spot/positions
```

Futures:

```text
smartsignalhub_trading.sqlite3: futures/futures_metrics and projected positions
```

Hedge:

```text
smartsignalhub_trading.sqlite3: hedge/hedge_daily_summaries
```

It should not calculate canonical account metrics. It may format values and choose icons.

The bot poller applies backoff after Telegram API throttling or temporary server errors:

```text
HTTP 429 -> use Retry-After / retry_after when available
HTTP 5xx or timeout -> short local backoff before the next getUpdates call
```

## Commands

Current command menu:

```text
/start     enable alerts
/status    check whether alerts are active
/summary   show short Spot/Futures/Hedge phone summary
/capital   show Spot/Futures/Hedge capital snapshot
/positions show Spot/Futures/Hedge positions
/stop      disable alerts
/help      show available bot commands
```

CLI utility:

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.telegram_bot_system --status
python3 -m platform_v2.tools.telegram_bot_system --set-commands
python3 -m platform_v2.tools.telegram_bot_system --poll-once
python3 -m platform_v2.tools.telegram_bot_system --run-forever
```

## Subscriber State

Subscriber state is local runtime-like bot state:

```text
platform_v2/tools/telegram_bot_system/state/subscribers.json
```

This must stay out of GitHub.

## Message Types

Current message builders support:

- start/stop/status/help replies
- short Spot/Futures/Hedge summary
- capital snapshot
- open positions snapshot
- position opened alert
- position closed alert
- denied/close simple fallback messages

## Formatting Rules

Telegram messages use HTML formatting. Keep the first line meaningful because phone notifications often show only the top of the message.

Alert first lines should be short and event-first:

```text
Spot BUY opened
Futures SHORT closed: tp_hit
BTCUSDT entry denied
```

Futures `OPENED` alerts include a compact Hedge Strategy block because Hedge
only reacts to confirmed Futures opened entries:

```text
Hedge Strategy
Equity / If Closed
LONG entries and PnL
SHORT entries and PnL
Risk label
```

Trade alerts should not include the full capital snapshot. They should include
only a compact Account block:

```text
Account
Equity / PnL / Open
Available / Unrealized / Exposure
```

Open-position message should show:

- position id
- side
- symbol
- entry
- mark
- unrealized PnL
- ROE for Futures
- TP/SL
- margin/notional for Futures
- Hedge LONG/SHORT basket count, average entry, mark, margin, notional, unrealized PnL, and ROE
