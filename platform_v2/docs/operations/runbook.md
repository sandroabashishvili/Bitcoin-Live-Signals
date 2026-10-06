# Operating Guide and Current Status

Updated: 2026-10-05. This is the single maintained entry point for current status,
everyday commands and next work. Technical specifications remain in their module
and topic documents. Dated reports describe historical checkpoints, not current deployment.

## Current checkpoint

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
- `~/research_snapshots/readiness_R21_20260928/REPORT.md` — activation checkpoint.
- `~/research_snapshots/readiness_R21_20260928/user-bus-repair.md` — later boot finding.
- `~/research_snapshots/readiness_R21_20260928/boot-acceptance-20261005.md` — WSL update and final reboot acceptance.
- `~/research_snapshots/readiness_R21_20260927/deploy/` — approved deployment files.
Preserve the release and SQLite library referenced by activation configuration.

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
