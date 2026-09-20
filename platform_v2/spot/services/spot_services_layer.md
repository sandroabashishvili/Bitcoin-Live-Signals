# Services Layer

Status: `active`
Created: `2026-05-19`
Updated: `2026-09-12`
Author: Codex
Purpose: Spot services layer ownership map for operational business logic.

ეს ფოლდერი არის `platform_v2`-ის **სამუშაო სერვისების ფენა**.

აქ არ უნდა ცხოვრობდეს:
- raw domain models
- storage path contracts
- HTML renderer-ები
- CLI entrypoints

აქ უნდა ცხოვრობდეს:
- ბაზრის მონაცემების წაკითხვა/აგება
- indicator assembly
- signal assembly
- permission evaluation orchestration
- order/position runtime flow
- metrics and runtime summaries
- სრული cycle orchestration

ადამიანურად:
- `domain` ამბობს: **რა ობიექტებია**
- `services` ამბობს: **რა სამუშაო სრულდება ამ ობიექტებზე**
- `ops/main_cycle_service.py` ამბობს: **რა რიგით სრულდება ეს სამუშაო ერთ ციკლში**


## Folder Map

`services/` ამ ეტაპზე იყოფა ასეთ ოჯახებად:

1. `account`
2. `analytics`
3. `market`
4. `ops`
5. `permission`
6. `signal`
7. `trading`


## 1. account

ფოლდერი:
- [account](/home/sandro/SmartSignalHub/platform_v2/spot/services/account)

ეს ოჯახი მართავს:
- position state
- position lifecycle update
- portfolio state
- summary metrics

### ფაილები

- [position_state_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/account/position_state_service.py)
  - runtime `positions` SQLite family-დან latest მდგომარეობას კითხულობს
  - dedupe-ს აკეთებს `position_id`-ზე
  - აბრუნებს open/closed პოზიციების ნორმალიზებულ სიას

- [position_runtime_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/account/position_runtime_service.py)
  - ახალი გახსნილი position record-ს აგებს
  - execution setup-ს იღებს trading ფენიდან
  - runtime `positions` family-ში წერს

- [position_update_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/account/position_update_service.py)
  - open position-ს candles-ზე ატარებს
  - ამოწმებს TP/SL hit-ს
  - force-close path-საც მართავს
  - ახლა exit metadata-საც ავსებს

- [position_batch_update_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/account/position_batch_update_service.py)
  - ყველა open position-ს ერთად ანახლებს
  - ამ ეტაპზე TP/SL monitoring `5m` closed candles-ზე გადაჰყავს
  - updated rows runtime-ში წერს

- [portfolio_state_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/account/portfolio_state_service.py)
  - current open positions-იდან ითვლის:
  - available balance
  - open exposure
  - open positions count
  - last open entry price

- [metrics_system/summary_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/metrics_system/summary_service.py)
  - aggregate summary-ს აგებს
  - portfolio snapshot
  - trade outcomes snapshot
  - win rate / tp hits / sl hits / force close counts
  - metrics family-ში ინახავს

### account ფენის დანიშნულება

ეს ფენა არის:
- **runtime state management**
- **position lifecycle**
- **portfolio truth**

აქ არ უნდა ჩავყაროთ:
- signal scoring
- Binance API fetch
- HTML rendering


## 2. analytics

ფოლდერი:
- [analytics](/home/sandro/SmartSignalHub/platform_v2/spot/services/analytics)

ეს ოჯახი აგებს indicator მხარეს.

### ფაილები

- [indicator_builder_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/analytics/indicator_builder_service.py)
  - candles-იდან indicator snapshot-ებს აგებს
  - high-level orchestrator-ია analytics ოჯახში

- [indicator_snapshot_builder.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/analytics/indicator_snapshot_builder.py)
  - ერთი timeframe-ის snapshot row-ს აგებს
  - normalized indicator payload-ს აბრუნებს

- [shared indicator_series.py](/home/sandro/SmartSignalHub/platform_v2/shared/backend/market/indicator_series.py)
  - series-based indicator formulas
  - მაგალითად EMA/RSI/MACD/ATR ტიპის გათვლები

- [indicator_structure_math.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/analytics/indicator_structure_math.py)
  - structure/liquidity/resistance/swing მხარის helper-ები
  - candle series-ზე უფრო “market structure” აზროვნების ფენა

- [strategy_effectiveness/](/home/sandro/SmartSignalHub/platform_v2/spot/services/analytics/strategy_effectiveness)
  - strategy quality / effect summary package
  - gate stats, signal activity, closed-trade stats და theoretical outcome helper-ები ცალკე modules-შია

### analytics ფენის დანიშნულება

ეს ფენა არის:
- **market feature engineering**
- **indicator truth building**

აქ არ უნდა ჩავყაროთ:
- signal permission
- order execution
- runtime persistence orchestration


## 3. market

ფოლდერი:
- [market](/home/sandro/SmartSignalHub/platform_v2/spot/services/market)

ეს ოჯახი ბაზრის ნედლ მონაცემებთან მუშაობს.

### ფაილები

- [binance_candle_fetch_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/market/binance_candle_fetch_service.py)
  - Binance-დან closed candles მოაქვს
  - runtime candle storage-ში ინახავს

- [binance_orderbook_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/market/binance_orderbook_service.py)
  - orderflow proxy/orderbook snapshot-ს აგებს
  - Binance aggTrades/orderflow მხარეს ემსახურება

- [candle_reader_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/market/candle_reader_service.py)
  - candle repository-ს thin wrapper-ია
  - service-side reads-ისთვის გამოიყენება

- [market_context_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/market/market_context_service.py)
  - candles + indicators + orderbook/context ნაწილებს ერთ normalized market context-ად აწყობს

### market ფენის დანიშნულება

ეს ფენა არის:
- **data acquisition**
- **data reading**
- **market context assembly**

აქ არ უნდა ჩავყაროთ:
- permission rules
- portfolio counting
- UI logic


## 4. ops

ფოლდერი:
- [ops](/home/sandro/SmartSignalHub/platform_v2/spot/services/ops)

ეს ოჯახი არის ოპერაციული orchestration ფენა.

### ფაილები

- [main_cycle_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/ops/main_cycle_service.py)
  - ერთი სრული cycle-ის დირიჟორია
  - fetch
  - indicators
  - open position update
  - signal/permission
  - order/position creation
  - Telegram event hook
  - metrics
  - page refresh
  - cycle marker

- [runtime_write_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/ops/runtime_write_service.py)
  - runtime JSON families-ში write entrypoint
  - signals
  - orders
  - positions
  - denied entries
  - force closes

- [cycle_run_runtime_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/ops/cycle_run_runtime_service.py)
  - თითო cycle-ის მოკლე audit row-ს წერს `cycle_runs` family-ში

- [daily_runtime_summary_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/ops/daily_runtime_summary_service.py)
  - დღიური aggregate summary-ს აგებს
  - latest cycle + latest metrics snapshot-საც აერთებს

### ops ფენის დანიშნულება

ეს ფენა არის:
- **runtime orchestration**
- **runtime summaries**
- **one-cycle operational control**

აქ არ უნდა ჩავყაროთ:
- indicator formulas
- stop-loss formula დეტალები
- pure domain model parsing


## 5. permission

ფოლდერი:
- [permission](/home/sandro/SmartSignalHub/platform_v2/spot/services/permission)

ეს ოჯახი წყვეტს, actionable signal-ს რეალური entry უფლება აქვს თუ არა.

### ფაილები

- [permission_decision_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/permission/permission_decision_service.py)
  - pure-ish permission evaluation layer
  - capital / exposure / cooldown / duplicate / proximity / weak-open-position checks

- [denied_entry_runtime_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/permission/denied_entry_runtime_service.py)
  - denied entry row-ს აგებს და ინახავს

- [signal_permission_runtime_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/permission/signal_permission_runtime_service.py)
  - signal runtime + permission evaluation + denied entry persistence + allowed path orchestration
  - ამ ოჯახში ყველაზე მძიმე runtime coordinator-ია

### permission ფენის დანიშნულება

ეს ფენა არის:
- **execution gatekeeper**
- **entry allow/deny truth**

აქ არ უნდა ჩავყაროთ:
- signal scoring math
- raw market fetch
- page rendering


## 6. signal

ფოლდერი:
- [signal](/home/sandro/SmartSignalHub/platform_v2/spot/services/signal)

ეს ოჯახი პასუხობს კითხვაზე:
- „ამ candle/context-ზე BUY არის თუ NO_SIGNAL?“

### ფაილები

- [mtf_context_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/signal/mtf_context_service.py)
  - multi-timeframe alignment/direction context-ს აგებს

- [signal_decision_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/signal/signal_decision_service.py)
  - market context-იდან normalized `SignalDecision`-ს აგებს
  - scoring + gate evaluation აქ არის თავმოყრილი

- [signal_runtime_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/signal/signal_runtime_service.py)
  - context build + signal build + signal persistence
  - signal family-ში ჩაწერის runtime wrapper

### signal ფენის დანიშნულება

ეს ფენა არის:
- **strategy-side decision making**
- **BUY vs NO_SIGNAL truth**

აქ არ უნდა ჩავყაროთ:
- order placement
- position state updates
- account summaries


## 7. trading

ფოლდერი:
- [trading](/home/sandro/SmartSignalHub/platform_v2/spot/services/trading)

ეს ოჯახი execution setup და order მხარეს ემსახურება.

### ფაილები

- [execution_setup_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/trading/execution_setup_service.py)
  - live entry price-იდან execution-time SL/TP setup-ს აგებს

- [order_execution_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/trading/order_execution_service.py)
  - normalized order request/result boundary
  - ამ ეტაპზე paper/dry-run execution მხარეს ემსახურება

- [sl_tp_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/trading/sl_tp_service.py)
  - thin bridge-ია
  - SL/TP-ის domain-side logic-ს execution layer-ს აძლევს

### trading ფენის დანიშნულება

ეს ფენა არის:
- **execution setup**
- **order boundary**
- **live position setup build**

აქ არ უნდა ჩავყაროთ:
- full cycle orchestration
- indicator building
- portfolio summaries


## Current End-to-End Flow

დღევანდელი მთავარი runtime გზა ასეთია:

1. `market`
   - candles/orderflow/context
2. `analytics`
   - indicators/snapshot build
3. `signal`
   - BUY or NO_SIGNAL
4. `permission`
   - allowed or denied
5. `trading`
   - execution setup / order request
6. `account`
   - position state / updates / metrics
7. `ops`
   - ამ ყველაფერს ერთ cycle-ში რიგით აძრობს


## Practical Rules

`services/`-ში კოდის წერისას ეს წესები გვინდა:

- orchestration და calculation ერთმანეთში არ ავურიოთ
- low-level math/helper-ები დიდ runtime coordinator-ში არ ჩავყაროთ
- ერთი service რაც შეიძლება ერთ პასუხისმგებლობაზე იყოს
- runtime write side-effect ცალკე მკაფიოდ ჩანდეს
- `ops` ფაილები არ უნდა გადაიქცეს formula dumps-ად
- `signal_permission_runtime_service.py` და `main_cycle_service.py` განსაკუთრებით ფრთხილად უნდა დაიშალოს helper-ებად, თუ იზრდება


## Known Sensitive Files

ამ ფენაში განსაკუთრებით ფრთხილად შესაცვლელია:

- [main_cycle_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/ops/main_cycle_service.py)
- [signal_permission_runtime_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/permission/signal_permission_runtime_service.py)
- [signal_decision_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/signal/signal_decision_service.py)
- [position_batch_update_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/account/position_batch_update_service.py)
- [position_update_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/account/position_update_service.py)
- [execution_setup_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/trading/execution_setup_service.py)

აქ პატარა ცვლილებაც კი ხშირად პირდაპირ ახდენს გავლენას:
- live entries-ზე
- TP/SL closing-ზე
- metrics truth-ზე
- Telegram alerts-ზე
- frontend snapshots-ზე


## Short Version

თუ ერთ წინადადებაში უნდა შევაჯამოთ:

- `services/` არის **სისტემის სამუშაო ძრავი**
- `ops` არის **დირიჟორი**
- `signal` და `permission` წყვეტს **ვაჭრობა იწყება თუ არა**
- `trading` აწყობს **entry/SL/TP/order მხარეს**
- `account` ინახავს **position/account truth-ს**
- `analytics` აგებს **indicator truth-ს**
- `market` აწვდის **ბაზრის ნედლ და შუალედურ მონაცემებს**

## Current signal ownership

`signal/independent_long_signal_service.py` is the active v5 decision engine. It computes opposing context and entry quality from Spot history, without Futures signal dependencies. `metrics_system/` is also a service family. See [Spot rules](../../docs/trading/spot_rules.md).
