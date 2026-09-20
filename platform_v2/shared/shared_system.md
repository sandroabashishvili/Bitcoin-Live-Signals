# Shared System

Updated: 2026-09-12. Shared infrastructure; strategy ownership remains inside each subsystem.

`backend/` provides neutral contracts, time/numeric helpers, persistence and runtime-store facades. SQLite is partitioned into trading, market-data and content databases. `frontend/` owns common CSS, navigation, metadata helpers, explanation components and charts. Shared terminal helpers format human-readable output.

Dependency direction is Spot/Futures/Hedge/tools → shared. Shared backend must not import strategy-specific services. Similar Spot/Futures scoring code may be intentional independent ownership; do not merge it merely to silence a duplication warning.

No shared helper should silently alter strategy thresholds, permissions or account policy. Frontend handles presentation; backend owns financial calculations and prepared payloads.

See [architecture](../docs/system/architecture.md), [database architecture](../docs/system/database_architecture.md), [runtime store](backend/runtime_store/runtime_store.md) and [frontend boundary](../docs/system/frontend_backend_boundary.md).
