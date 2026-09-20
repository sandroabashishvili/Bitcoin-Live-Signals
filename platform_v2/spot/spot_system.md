# Spot System

Updated: 2026-09-12. Active independent BUY-only simulation. Version `spot-independent-direction-quality-v5`.

- `config/`: operational defaults and locally owned copied scoring rules.
- `domain/`: Spot entities and typed signal/market contracts.
- `services/market/`: Spot observations and indicators.
- `services/signal/`: independent LONG/SHORT context scores; BUY-only output and Spot history-based entry quality.
- `services/permission/`, `services/trading/`, `services/account/`: entry permission, adaptive execution and position lifecycle.
- `services/metrics_system/`, `services/analytics/`: prepared metrics, explanations and reports.
- `storage/`: repository/path adapters backed by central SQLite.
- `app/run_loop.py`: initial cycle plus quarter-hour scheduling.
- `dashboard/`: five generated pages; frontend displays prepared backend data.

Spot does not read Futures signals or execution events. No individual Gate is mandatory. Weak-open-position and peer force-close flags are off. LONG profit lock is active; full trailing TP/SL is not. Closed 1m exit evidence is processed by the 15-minute cycle.

See [Spot rules](../docs/trading/spot_rules.md), [runtime flow](../docs/system/runtime_flow.md), and [runbook](../docs/operations/runbook.md).
