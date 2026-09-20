# Runtime Store

Status: `active`  
Created: `2026-08-01`  
Purpose: One labelled storage API for Spot, Futures, and Hedge.

## Code Ownership

This is the only runtime storage code package:

```text
platform_v2/shared/backend/runtime_store/
```

System adapters are explicit modules, not scattered subsystem folders:

```text
spot.py       RuntimeStore(system="spot")
futures.py    RuntimeStore(system="futures")
hedge.py      RuntimeStore(system="hedge")
```

The generic `RuntimeStore` owns SQLite-primary reads/writes, logical compatibility
paths, upserts, replacement and validation. Trading JSON is an explicit
export/import artifact, not a required live mirror.
Family metadata lives under `families/` and remains labelled by system.

## Data Ownership

Generated data is separate from code:

```text
platform_v2/runtime/spot/
platform_v2/runtime/futures/
platform_v2/runtime/hedge/
platform_v2/runtime/database/
platform_v2/runtime/artifacts/
platform_v2/runtime/logs/
```

Do not recreate `spot/runtime_ledger`, `futures/runtime_ledger`,
`futures_hedge/runtime_ledger`, or subsystem-local runtime roots.

Reviewed 2026-09-12. `futures_positions` is derived from lifecycle events.
See [database architecture](../../../docs/system/database_architecture.md).
