# Futures Simulation Modules

Status: `active`
Created: `2026-06-01`
Updated: `2026-09-12`
Author: Codex
Purpose: Futures simulation module map and execution responsibility boundaries.

ეს ფოლდერი მართავს `platform_v2.futures`-ის simulation ციკლს მოდულებად.

## მოდულები

- `directional_futures_simulation_service.py`
  - მთავარი orchestration ფენა.
  - აერთიანებს state, signal, permission, position updates, metrics და runtime write-ს.

- `entry_permission_context_service.py`
  - Futures entry permission-ის არასაბალანსო context.
  - SHORT market-plan zone permission.
  - SHORT continuation override (disabled in active v5 settings).
  - SHORT `LATE_EXTENSION` entry-quality override.
  - LONG entry-location permission.

- `entry_event_writer_service.py`
  - signal/permission result payloads.
  - denied-entry rows.
  - opened position/order/event rows.
  - open-position state mutation for new entries.

- `position_lifecycle_service.py`
  - არსებული ღია პოზიციების წინასწარი განახლება ახალ signal-მდე.
  - TP/SL/profit-lock close events.

- `position_exit_resolver.py`
  - ფიქსირებული TP/SL და LONG profit-lock candle resolution.
  - conservative stop-first ordering.
  - v5 LONG profit-lock policy მხოლოდ ახალ LONG პოზიციებზე.

- `cycle_summary_builder.py`
  - `FuturesCycleSummary` build.
  - terminal/run-loop summary payload formatting.

- `state_store.py`
  - SQLite `runtime_state/futures/simulation_engine` ჩატვირთვა/შენახვა.
  - ძველი payload-ების migration (მაგ. `open_position` -> `open_positions`, fee backfill).

- `runtime_store.py`
  - candles/metrics/runtime ოჯახების (`futures_positions`, `futures_signals`, ...) read/write.

- `position_service.py`
  - პოზიციის payload და close-calculation helpers:
  - `TP/SL/profit-lock` close event-ის აგება `EXIT_MONITORING_TIMEFRAME` სანთლებზე.
  - open position payload-ის აგება.
  - close event-ების სტატისტიკის დათვლა.

- `metrics_service.py`
  - equity/PnL/exposure/returns და counters აგრეგაცია.
  - minimal metrics fallback (no-data რეჟიმისთვის).

- `permission_text.py`
  - permission reason/checks -> ადამიანური ტექსტი (UI/alerts).

- `common.py`
  - საერთო helper-ები (`coerce_int`, `ms_to_text`, optional parsers, JSON list loader).

- `models.py`
  - `FuturesCycleSummary` dataclass (run-loop/UI-სთვის ციკლის შედეგი).

## ციკლის მოკლე ნაკადი

1. ჩაიტვირთოს candles (`15m`) + exit candles (`1m`).
2. ჩაიტვირთოს state.
3. `position_lifecycle_service` განაახლებს ღია პოზიციებს (`TP/SL/profit-lock`).
4. დაითვალოს signal + permission.
5. `entry_permission_context_service` ამზადებს market-plan/location/override context-ს.
6. `entry_event_writer_service` წერს signal/denied/opened rows-ს.
7. დაითვალოს metrics, ჩაიწეროს runtime-ში, შეინახოს state.
8. `cycle_summary_builder` აბრუნებს run-loop summary-ს.

## დიზაინის წესი

- orchestration ერთ ფაილში, ლოგიკა სერვისებად გაყოფილი.
- runtime/state I/O გამოყოფილია სავაჭრო ლოგიკისგან.
- Spot parity ცვლილებები კეთდება შესაბამის მოდულში, არა მონოლითურ ფაილში.

`futures_positions` is a virtual latest-event projection. Exit evidence is 1m, evaluated inside the 15-minute main cycle. No full trailing TP/SL or independent 1m monitor is active.
