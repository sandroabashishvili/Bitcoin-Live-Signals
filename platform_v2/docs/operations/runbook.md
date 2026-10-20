# Operating Guide and Current Status

Updated: 2026-10-19. This is the single maintained entry point for current status,
everyday commands and next work. Technical specifications remain in their module
and topic documents. Dated reports describe historical checkpoints, not current deployment.

## 2026-10-19: operational deployment relocated inside platform_v2

The active deployment now lives at
`/home/sandro/SmartSignalHub/platform_v2/deployment/`, with configuration in
`deploy/`, one selected code snapshot in `releases/`, and its native library in
`sqlite/`. The user service, installed health-monitor cron entry and Windows
`SmartSignalHub-WSL` sign-in task now target this location. The former research
deployment is retained only for rollback; it is not the active launch location.

This is a path relocation, not a strategy promotion or trading reset. The code
hash remains `1f4295af7a8832beb669616243ad343e7e5491c34fd2e40a718be71ea0b40e3f`;
the October 18 activation epoch, strategy configuration and live databases are
preserved. Working-tree changes still require explicit promotion into the selected
snapshot; restarting alone does not promote code. Local before/after migration
evidence is under `platform_v2/deployment/migration/`.

## 2026-10-18: new all-system trading collection epoch

This dated checkpoint supersedes older references below to the unchanged September
28 activation epoch. The approved strategy release and SQLite runtime are unchanged.
Spot, Futures and Hedge paper accounts were reset to fresh 3,000 USDT accounts;
market_data and content were preserved in place. Expected first candle close is
2026-10-18 15:29:59.999 UTC; the successful process start was 15:43:17 UTC.
Actual first observations/receipts are recorded, not backdated synthetic decisions.

Verified archive and cutover report:
`/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/REPORT.md`.
Current retention/restore instructions:
`/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/RETENTION.md`.
After user-approved cleanup, only the verified self-contained `database/` backup
set remains; `raw_trading/` and older trial/legacy-report archives were removed.
Activation and monitor expectations now reference the new epoch. Initial bootstrap
failure was corrected by explicitly initializing projection schema before startup;
its FAILED/INTERRUPTED evidence was retained, so recent-failure health can warn
temporarily. Both first subsequent cycles committed successfully. This is not a
claim of full operational signoff, uninterrupted future collection, or profitability.

## Earlier deployment checkpoint

The local simulation service and research evidence collection are active. R2.1
activation began 2026-09-28 06:00:10 UTC (08:00:10 Europe/Berlin); the first expected
collection candle closed at 05:59:59.999 UTC. Earlier history is not relabelled as
first-live evidence. The service uses a pinned Python source bundle and verified
private SQLite 3.51.3. Updating checkout files or GitHub does not update that bundle.
A service restart alone also does not select a new release.

Immutable observations, input capture, cycle receipts, atomic simulation publication,
backfill provenance and independent health monitoring are enabled. Three-database
backup/restore verification and isolated validation passed; the implementation
checkpoint recorded 74 passing tests. These are dated results, not a test run on
every future revision. Strategy profitability is not established.

**Long-run operational acceptance passed on 2026-10-05.** The first repeat reboot
reproduced a WSL 2.5.9/WSLg runtime-directory overlay that hid the user systemd bus.
WSL was upgraded through Microsoft's supported updater to 3.0.1 (kernel
6.18.40.1-1), followed by another full Windows reboot. That boot exposed one
`/run/user/1000` mount, a working bus, one enabled/active runtime service and one
parent with the expected Spot, Futures and Telegram children. Fresh Spot,
Futures and Hedge cycles committed against the same pinned release and databases;
the independent health report had no issues. No custom root mount workaround was
installed. The monitor's `ready_for_signoff` field deliberately remains false by
design; operational acceptance is recorded here and in the dated local evidence.

Local evidence (not shipped with GitHub):
- `/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/retired_metadata/research_snapshots_2026-10-18/readiness_R21_20260928/REPORT.md` — activation checkpoint.
- `/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/retired_metadata/research_snapshots_2026-10-18/readiness_R21_20260928/user-bus-repair.md` — later boot finding.
- `/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/retired_metadata/research_snapshots_2026-10-18/readiness_R21_20260928/boot-acceptance-20261005.md` — WSL update and final reboot acceptance.
- `/home/sandro/SmartSignalHub/platform_v2/deployment/deploy/` — current operational deployment files (relocated October 19).
Preserve the release and SQLite library referenced by activation configuration.

### Hedge maintenance release — 2026-10-08

Pinned Python release updated to
`73ff648436ab29e208719b998dad0b428cf227909c21c2af741b87829954c743`.
The successor bundle changes only five Hedge files: overview page builder,
renderer, backend overview content, equity-risk helper and replay service.
Other pinned Python source, Spot/Futures parameters, SQLite library, database
paths and the original September 28 activation epoch are unchanged. New run
records identify the new release; previous evidence remains identified by its
original release and is not relabelled.

Hedge report selection and equity statistics now belong to backend services.
Peak drawdown and loss below starting capital are separate metrics, visible on
the overview with explanations. On copied runtime data, old/new replay account
payloads matched exactly apart from the intended risk fields. Pre-activation
validation passed 65 relevant tests and 19 tests through the candidate pinned
importer. Three-database online backup and restore verification passed at
`~/backups/smartsignalhub/hedge-update-20261008/`.

Release manifest, previous activation/monitor configuration and deployment
verification are under `/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/retired_metadata/research_snapshots_2026-10-18/hedge_update_20261008/`.
Live acceptance verified one parent and the three expected children on the final
release, unchanged Spot/Futures config identities, retained research counts,
zero gap detections and no health issues. The generated Hedge page matches the
versioned replay summary and includes both explanation drawers. The initial
metric release completed a Futures/Hedge cycle; the final content-only correction
rebuilt the page from that summary and passed the normal startup duplicate-cycle
guard. See `live-acceptance.json` and `REPORT.md` in the evidence directory.
The original immutable release is retained for rollback. This maintenance does
not constitute a new strategy or predictive-research promotion.

### Spot trade-flow collector maintenance — 2026-10-14

The selected pinned release is
`41a68287bc792dd9a77189f039fd5829545a90a48896f40e5a1ecebf65599778`.
It changes exactly five Spot input-path files from the previous release
`ca9071e09ab28ac9a82c5a82bc4b80d0b345f13b7b8ec9758c22aefe6af3666b`.
ORDERBOOK now receives the complete executed-trade flow for the exact closed
15-minute candle, paginated by aggregate-trade ID, with explicit coverage metadata.
Incomplete, legacy-unverified and mismatched-window context fails closed.
Scoring formulas, configuration identities, Futures/Hedge code, position rules,
SQLite library and original activation epoch are unchanged. Historical input
rows are preserved; this is not a research candidate promotion.

Validation: 286 Spot/research tests and 30 tests through the pinned importer passed.
A public-market preflight collected 4,768 aggregate trades in five pages without
writing live databases. Scoped online backups of the three runtime databases were
restore-verified under `~/backups/smartsignalhub/orderflow-fix-20261014/`.
Deployment files and acceptance evidence are under
`/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/retired_metadata/research_snapshots_2026-10-18/orderflow_fix_20261014/`; `live-acceptance.json` confirms the
first committed cycle used 5,828 trades across six responses, matching captured
raw quantities and retaining all 2,878 previous orderflow rows. The post-activation
health check passed with only the unchanged historical gap-review flags; no open
or failed attempts and no incomplete decision evidence were found. The service restarted at
06:04:26 UTC and correctly skipped the already committed previous candle.
The previous immutable release and deployment configuration are retained for
rollback. Historical `GAP_HISTORY_REVIEW` flags (27 detections per system before
this maintenance) are not cleared or represented as newly caused by this release.

### Futures trade-flow collector maintenance — 2026-10-15

Selected pinned release:
`1f4295af7a8832beb669616243ad343e7e5491c34fd2e40a718be71ea0b40e3f`.
Exactly five Futures input-path files changed from the preceding Spot-corrected
release. Futures now fetches the exact closed decision candle using aggregate-ID
pagination and rejects incomplete, legacy/unverified or wrong-candle flow. API
errors propagate rather than becoming empty-volume snapshots. Supported collection
windows are 1m/5m/15m/30m; production uses 15m. Component scoring, configuration
identities, entry and position rules, Spot/Hedge code and the original activation
epoch are unchanged. Historical evidence is not relabelled or erased.

379 regression tests and 36 exact-pinned-importer tests passed. Public-market
preflight captured 17,370 trades across 18 responses for one closed 15m candle
without live database writes. Three-runtime-database online copies and restore
verification passed under `~/backups/smartsignalhub/futures-orderflow-fix-20261015/`.
The service restarted at 05:55:45 UTC and skipped the already committed old candle.
Deployment/rollback files and verification scripts are under
`/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/retired_metadata/research_snapshots_2026-10-18/futures_orderflow_fix_20261015/`. Completed first-cycle and
health acceptance require `live-acceptance.json`, `after-health.json` and
`completion_manifest.json`; selection/restart alone does not establish acceptance.
First-cycle input and commit acceptance passed: 30,620 trades across 31 responses
for the closed 05:45–05:59:59.999 UTC candle, with raw response counts/quantities
matching the consumed snapshot and all 2,977 old Futures orderflow rows preserved.
The previous immutable release is retained. Existing historical gap-review flags
are not cleared by a data-collector repair. This is not a strategy promotion.

## Everyday operation on the configured WSL host

Run these commands in Ubuntu:

```bash
systemctl --user status smartsignalhub-runtime.service --no-pager
journalctl --user -u smartsignalhub-runtime.service -n 100 --no-pager
journalctl --user -u smartsignalhub-runtime.service -f
cat ~/SmartSignalHub/platform_v2/runtime/research_health/latest.json
```

Ctrl+C closes the log viewer only. The service owns one parent with Spot, Futures
and Telegram children; Futures also updates Hedge replay. Windows task
`SmartSignalHub-WSL` starts WSL at the configured user's sign-in, not before login.
Repeated service start requests do not create extra instances.

```bash
systemctl --user stop smartsignalhub-runtime.service
systemctl --user start smartsignalhub-runtime.service
systemctl --user restart smartsignalhub-runtime.service
```

Stop/start preserves databases. An intentional stop remains stopped for that
session; enabled startup can start it on the next boot/sign-in. Do not run
`python3 -m platform_v2.tools.runtime_start_system` beside the service.
A fresh source clone does not include this host's service, release or private
configuration; see [fresh setup](source_repository.md).

## Monitoring, data and backups

Local cron checks health at minutes 05, 20, 35 and 50. It reports stale/incomplete
cycles, evidence failures, identity drift, database/disk/WAL issues and backup age.
It does not create backups; manifest age is not a restore test. Read `issues` and
`ready_for_signoff` separately. No Codex automation is involved.

The three canonical SQLite databases are under `platform_v2/runtime/database/`.
Market candles cover 1m, 5m, 15m and 4h; UTC timestamps ending in Z are not local
time. Candle open and close times differ. Running candles are not closed-candle
history. Orderflow stores its values in `payload_json`; empty OHLC columns in
those rows are expected. Filter `dataset = candles` to inspect price bars.
Backfilled market candles do not recreate missed live decisions.

Use SQLite online backup for an inspection copy, rather than copying a changing
main DB alone. On Windows, open a verified self-contained copy on a local Windows
path. Such a copy does not refresh itself. Do not delete live WAL/SHM companions.

```bash
~/workspace_tools/backup/run.sh
~/workspace_tools/backup/run.sh --mode full
```

Daily covers projects, workspace tools and docs; full adds private recovery and
selected Windows/Codex state, not a complete disk image. Local output is under
`~/backups/{smartsignalhub,home,private,windows}`. Daily warns and skips unavailable
external targets; full reports them as failures. Verify results and manifests.
See [backup and reset details](backup_and_reset.md). A reset is destructive to the
current research epoch and is not part of ordinary maintenance.

## Local website and GitHub

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory "$HOME/SmartSignalHub"
```

Open `/platform_v2/public_site/`, `/platform_v2/spot/dashboard/` or
`/platform_v2/futures/dashboard/` on that local server.

Source is on `main`; generated public pages are on `gh-pages`, staged in the
ignored `publish/Bitcoin-Live-Signals` checkout. Runtime DBs, credentials, logs and
backups do not belong on GitHub. Source synchronization and website publishing
are separate operations.

Configured host schedules (Europe/Berlin): code upload daily 06:00; public website
publication 06:19, 12:19, 18:19, 23:19. Fifteen-minute publication is deferred.
Code synchronization skips remote changes/conflicts and continues other projects;
it never automatically pulls or overwrites remote work.

```bash
~/workspace_tools/github_sync/run.sh
~/workspace_tools/site_publish/run.sh --dry-run
# Explicit publication of reviewed generated pages:
~/workspace_tools/site_publish/run.sh
```

See [publishing details](../product/seo_and_publishing.md). These workspace tools
are local dependencies, not included in a fresh public source clone.

## Next work and research boundaries

1. Continue simulation evidence accumulation with a fixed, identified strategy.
2. Add candle charts in an isolated workspace, starting with closed candles and
   decision-time Spot/Futures signal markers; add entry/exit and TP/SL later.
3. Continue reproducible predictive research with sufficient usable history and
   frozen comparisons; keep the untouched test cohort closed until its approved stage.

Exploration has shown weak/unstable total-score relationships. This neither proves
profitability nor establishes a profitable replacement. Candidate baselines and
ablations belong in isolated research. Fix proven implementation defects, but do
not tune live weights, thresholds, permissions or TP/SL opportunistically. Keep
signal quality separate from execution costs and position management. Elapsed
months alone do not establish sample sufficiency.

Historical candidates (orderbook reweighting, RSI/MACD/ADX/rejection changes and
full trailing TP/SL) are not deployment recommendations. Exit inspection remains
inside the 15-minute cycle, not an independent one-minute monitor. Google Search
Console coverage and field performance still require account evidence; HTTP checks
alone do not establish indexing.

## Documentation maintenance

Update this guide when deployment, commands or next work changes. Keep low-level
contracts in their technical documents and link here for operational status.
Do not rewrite dated research evidence as if it described a later deployment.
[Documentation map](../platform_v2_docs.md) lists the technical references.
