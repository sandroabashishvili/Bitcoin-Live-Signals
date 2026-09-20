# Runtime Database System

Updated: 2026-09-12. Active SQLite-primary storage, not a mirror pilot.

```bash
python3 -m platform_v2.tools.runtime_database_system
python3 -m platform_v2.tools.runtime_database_system --check-parity
python3 -m platform_v2.tools.runtime_database_system --export-root /tmp/runtime-json-export
```

The three databases separate trading, market observations and news content. Status reports their counts and sizes. Parity compares optional compatibility/public JSON that exists; absence of trading JSON is normal. Readers do not require a JSON mirror to use SQLite.

`--import-json` imports/replaces trading, market, state and news records. It is a deliberate migration/recovery command, not a routine health check and not a safe substitute for content-only recovery after a trading reset. Existing matching family/date records can be replaced.

Public news generation deliberately creates render-ready JSON snapshots. A full reset can leave these outside the clean content database; September 12 recovered missing days only with a backed-up, transaction-protected content script. See [runbook](../../docs/operations/runbook.md) and [database architecture](../../docs/system/database_architecture.md).
