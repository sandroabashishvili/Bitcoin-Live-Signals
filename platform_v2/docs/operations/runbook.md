# Runbook

Updated: 2026-09-12.

## Normal start and stop

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.runtime_start_system
```

Starts Spot, Futures and Telegram; Futures also runs Hedge replay. `--spot-only` and `--futures-only` limit trading loops but still start Telegram. Ctrl+C requests child shutdown. The September 12 loop entrypoints suppress the expected KeyboardInterrupt traceback; this is a display fix, not a strategy or scheduling change. Running Python processes need a normal restart to load changed modules.

Normal stop/start keeps SQLite positions/history. Do not reset to load code changes. The main loops process closed 15m decisions after a 60-second scheduling offset and processing time. Closed 1m exits are checked within those cycles, not every minute independently.

## Intentional clean experiment

Stop the running launcher before any reset. Verify a backup first. A full reset deliberately clears current trading and market history; do not run it during a normal maintenance restart.

```bash
python3 -m platform_v2.tools.backup_system --help
python3 -m platform_v2.tools.runtime_reset_system --dry-run
```

When a full new experiment is explicitly intended:

```bash
python3 -m platform_v2.tools.runtime_reset_system
python3 -m platform_v2.tools.runtime_start_system
```

Full reset moves existing database/Spot/Futures/Hedge runtime roots to `/home/sandro/runtime_archives/reset_<UTC timestamp>/` and rebuilds 11 empty dashboards. It does not stop active processes itself. Databases and optional mutable state are recreated on demand. `.sqlite3-wal` and `.sqlite3-shm` are SQLite companions, not additional databases; retain them with archived databases.

Public HTML/news JSON are outside those runtime roots. Consequently, a clean content DB can lack retained public snapshots. September 12 restored only missing news days with the reviewed script in `/home/sandro/research_snapshots/system_review_20260912/restore_missing_news.py`, after a SQLite backup. It leaves existing content batches and all trading/market state untouched. Do not use a broad `--import-json` command to repair only news; that also imports trading and market state.

## Checks

```bash
python3 -m platform_v2.tools.diagnostics --profile operational
python3 -m platform_v2.tools.diagnostics --profile full
python3 -m platform_v2.tools.runtime_database_system --check-parity
```

Reports go under `platform_v2/runtime/artifacts/`. Full diagnostics includes complexity/refactoring candidates; a finding's severity alone is not proof of a trading failure. Operational checks are also not proof of profitable logic. Read the findings and validate new signals/orders/exits together.

Backups use `platform_v2.tools.backup_system`; inspect `--help` for current profiles and targets. SQLite backups use the backup API rather than copying a changing main DB alone. Review verification output and manifests before relying on a backup.

## Local pages and publishing

```bash
python3 -m http.server 8080 --bind 127.0.0.1
```

Run from `~/SmartSignalHub`; dashboards are under `/platform_v2/spot/dashboard/`, `/platform_v2/futures/dashboard/` and `/platform_v2/futures_hedge/dashboard/`.

```bash
python3 -m platform_v2.tools.sitemap_system
python3 -m platform_v2.tools.github_publish_system --dry-run
```

Publishing without `--dry-run` can commit and push to public `gh-pages`. Read [SEO and publishing](../product/seo_and_publishing.md) and the [current review](../current/system_review_20260912.md) first. No reset is needed for metadata fixes.
