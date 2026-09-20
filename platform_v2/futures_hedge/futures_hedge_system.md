# Futures Hedge System

Updated: 2026-09-12. Active paper replay, not an unfinished scaffold. Policy unchanged in the September 12 maintenance pass.

Hedge consumes confirmed Futures `OPENED` events as entry triggers. It uses their direction, entry time and price, while owning its own budget, size, leverage, fees, LONG/SHORT baskets and basket-reset rules. It does not independently score market signals. This dependency is intentional.

Futures TP/SL and force-close events do not close Hedge baskets. Hedge accumulates entries and applies its own capital/reset policy. Do not equate Hedge equity, estimated close equity and available margin.

`config/` owns Hedge defaults; `services/replay/` builds its report; `services/ops/` handles runtime/notifications; `dashboard/overview_hedge/` renders the overview. Hedge families are stored under system `hedge` in trading SQLite. The Futures main cycle runs the replay; a separate Hedge process is not required.

See [Hedge policy](../docs/trading/futures_hedge.md), [database inventory](../docs/system/runtime_data_inventory.md) and [runtime flow](../docs/system/runtime_flow.md).
