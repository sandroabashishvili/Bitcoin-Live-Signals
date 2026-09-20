# Futures System

Updated: 2026-09-12. Active independent LONG/SHORT simulation. Version `futures-short-zone-required-long-profit-lock-1m-v5`.

- `config/`: execution profile and Futures-owned rules.
- `domain/`: market, signal, account and execution contracts.
- `services/signal/`: direction scoring and structure calculations.
- `services/simulation/`: permissions, quotes, position lifecycle and state orchestration.
- `services/analytics/`, `services/metrics_system/`: trade audits, diagnostics and dashboard content.
- `app/run_loop.py`: scheduled cycle, notifications and Hedge replay integration.
- `dashboard/`: five generated static pages.

Default simulation is x5 isolated, 100 USDT margin, 3,000 USDT initial capital. No individual Gate is mandatory. SHORT market-plan-zone permission remains required; its old continuation override is off. LONG profit lock is active. TP/SL uses closed 1m evidence within the 15-minute cycle.

Orders/events and mutable simulation state live in trading SQLite. `futures_positions` is projected from latest position events, not persisted a second time. Hedge intentionally consumes OPENED events but does not change Futures entry/exit decisions.

See [Futures rules](../docs/trading/futures_rules.md), [simulation modules](services/simulation/futures_simulation_modules.md) and [runbook](../docs/operations/runbook.md).


## SHORT entry timing correction — 2026-09-16

Live `FuturesEntryQualityService` now treats mature SHORT age as descriptive, not proof of price exhaustion. SHORT history includes actionable signals across NO_SIGNAL pauses; those pauses no longer reset age. A gap longer than the configured candle period truncates the historical segment and blocks the first resumed actionable SHORT until a subsequent observed candle. Flip confirmation remains independently enforced.

For SHORT at legacy late/exhausted ages, permission requires a same-candle market plan, IN_ZONE permission, CLEAN short location and finite EMA9/VWAP/support-distance diagnostics. Missing/stale/non-clean context denies entry. The existing outside-zone restriction, account risk, slot, cooldown and proximity guards remain. No score/Gate override may bypass the new location/history denial reasons. LONG/Spot/Hedge policy is unchanged. This is a policy correction, not a proven profitability improvement.

Reason codes: entry_history_gap, short_entry_location_unconfirmed, mature_short_in_clean_zone. Mature SHORT labels now use MATURE_DIRECTION; legacy analytics may still classify by the original domain helper. The older portfolio research replay remains a historical-policy implementation and must not be presented as replay of this new live policy without integration of the same service and timestamped market-plan context.

Validation: 43 targeted futures/research tests passed. Read-only audit in `platform_v2/tools/research/artifacts/entry_timing_20260916/` compares 56 decisions from 2026-09-14 22:59:59Z through 2026-09-15 17:29:59Z. 21 pass the recorded non-timing checks plus the new policy. This is NOT a portfolio replay: newly opened positions would change subsequent capital, cooldowns, exposure and exits. Runtime/database records were not rewritten. Restart the existing runtime to load the changes; no reset required.
