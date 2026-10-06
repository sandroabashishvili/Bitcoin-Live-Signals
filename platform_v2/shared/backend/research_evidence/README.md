# Research evidence and atomic simulation — R2

Feature defaults remain **OFF** for unconfigured launches. On the configured host,
R2.1 collection and atomic simulation were activated on 2026-09-28 using a pinned
release and private SQLite 3.51.3. Service and independent cron monitoring are
installed. Final long-run acceptance remains pending the WSL boot-management issue.
See the [operating guide](../../../docs/operations/runbook.md) for current status,
commands and remaining work. This document describes the implementation contract.
No predictive test outcomes were opened during activation.

## Evidence schema (additive versions1–2)

All evidence and execution receipts reside in the existing trading DB. Importing
modules does not migrate it; explicit recorder startup creates missing tables.
Existing projections and the three-database ownership remain intact.

| Table / view | Meaning |
| --- | --- |
| research_runs | Startup, loaded code/config identity, pinned source reference, dependencies, host/boot/PID/start ticks, active flags |
| cycle_attempt_events | STARTED before network, effective CONFIG, COMMITTED/FAILED/INTERRUPTED/ABANDONED |
| decision_observations | Exact serialized row before compatibility upsert, actual candle, availability, origin, input references |
| research_first_live_decisions | Earliest immutable LIVE observation per system/candle; excludes reconstruction |
| market_acquisition_events | Every observed HTTP try, response/error, parameters, times, count, truncation uncertainty, JSON content ref |
| cycle_gap_events | Missing decision detection bounded by an explicitly enabled epoch; reason UNKNOWN unless separately evidenced |
| research_input_revisions / research_blobs | Exact returned inputs in hashed compressed chunks; missing refs fail validation |
| execution_cycle_receipts | Unique system/cycle receipt committed atomically with simulation effects |
| research_evidence_schema | Independent migration versions |

Evidence tables reject UPDATE/DELETE. Identical event retry is idempotent;
conflicting event-key reuse and second terminals are rejected. No old mutable
row is imported as a first evaluation. STARTED expected due is15m boundary+60s,
with a further120s lateness budget. Decision lateness uses actual availability
and actual candle close, not the expected slot. These labels do not filter entries.

COMMITTED means the cycle function returned (including skipped cycles), not that
a trade opened. Receipt presence is the authoritative atomic-simulation publication
fact. Failure after publication can yield a FAILED attempt **with a receipt**;
reporting failure must never cause re-execution. ABANDONED is only appended after
positive local process-exit proof, not by age. SIGTERM becomes a graceful
SystemExit in evidence-enabled loops; interruption during a cycle is recorded.

## Atomic simulation, independently opt-in

With `SSH_RESEARCH_ATOMIC_SIMULATION=1` and an active recorder, the guarded cycle
works against a consistent in-memory snapshot of runtime documents/rows/state.
Existing storage helpers read their own staged writes. Durable research evidence
uses separate real connections and survives discarded simulation staging.

After the Spot signal pipeline or Futures simulation finishes, the cycle marker,
position/order/capital/state writes and a unique receipt are published in **one**
FULL synchronous SQLite transaction. Before publication the system's read snapshot
is validated against concurrent changes. A conflict aborts rather than overwrites.
HTTP work holds no writer transaction. Pages/notifications/reports run after
publication. Failure before publication leaves no partial simulation effects;
failure after publication cannot replay that cycle because the receipt persists.

This applies to current local **simulation** only. Futures non-simulation profiles
and Spot non-paper/non-dry-run execution are rejected while staging is active.
It is not exactly-once exchange-order submission. Recorder STARTED failure in
atomic mode aborts the cycle; it never silently falls back to unsafe legacy writes.
Disabled mode retains legacy behavior, including its known crash window.

## Pinned source release

`release.py` is a stdlib-only builder/launcher, executed directly before project
imports. It captures all project Python sources, checks syntax/source stability,
stores a content hash and read-only bundle, and installs a source loader that uses
that bundle for every platform_v2 import, including lazy imports. New disk modules
absent from the bundle cannot be imported. Existing resource/runtime paths stay
unchanged. The parent runtime launcher propagates the same pinned bundle to its
Spot/Futures/Telegram children. Run provenance retains the bundle in evidence.

This pins Python project source. The Python interpreter, installed dependencies,
configuration values and non-Python resources still require deployment/environment
control; their identities are recorded, not sandboxed or frozen by this loader.
Ordinary unpinned startup explicitly records `release_verified=false`.

Build only (does not start runtime):

```bash
cd ~/SmartSignalHub
venv/bin/python platform_v2/shared/backend/research_evidence/release.py \
  --build "$PWD" --output ~/research_snapshots/research_releases
```

A controlled cutover must use the resulting bundle's `run.py`, `source.json.gz`
and exact SHA, with `--module platform_v2.tools.runtime_start_system`. Do not run
it beside existing loops. The `.service.example` remains guarded and disabled;
replace its legacy ExecStart with that pinned command before approved deployment.

## Input and market recovery

Market reads, runtime documents/history, runtime state, generic JSON fallbacks and
resolved Futures engine state are captured as exact returned values. Signal payloads
include persisted scores/weights/gates/thresholds without historical reconstruction.
Spot's raw decision precedes its readable timestamp/permission enrichment. Its
exact integer `timestamp_ms` supplies the initial candle identity; both writes
are retained, and the first-live view selects the raw evaluation. Research that
needs later permission fields must explicitly select that subsequent observation.
`evidence_complete` means captured refs exist and no observed recorder error;
it is not a mathematical proof that every future custom input is instrumented.

HTTP capture retains parsed JSON, not raw bytes/headers. A limit-sized response
is POSSIBLY_TRUNCATED; fewer rows do not prove window completeness. Futures
orderflow error is recorded before its existing empty-array fallback. Quote
responses are also retained. Old market rows keep unknown historic first-seen
provenance; observing them now does not make them originally live observations.

`SSH_RESEARCH_BACKFILL=1` requires an active observer and enables explicit paginated
closed-candle recovery. Both internal holes and missing tails are repaired using
validated contiguous pages of at most500rows. Empty storage can recover back to
the configured activation epoch. No arbitrary historical start is invented.
Partial/malformed pages remain incomplete; only verified ranges are merged.
All recovery acquisitions are BACKFILLED. Signals, orderflow and past trades are
never synthesized. Market recovery changes available history and must be included
in controlled regression acceptance before activation.

`SSH_RESEARCH_ACTIVATION_CLOSE_MS` sets the first expected15m close in the collection
epoch. Elapsed missing slots are appended with UNKNOWN reason. Existing detections
are historical facts, not deleted when a late decision appears. Rotate the epoch
when collection was intentionally disabled; do not silently attribute every gap
to computer downtime.

## Health and validation

Read-only command (no migration, repair, checkpoint or decisions):

```bash
cd ~/SmartSignalHub
venv/bin/python -m platform_v2.shared.backend.research_evidence.health \
  --database platform_v2/runtime/database/smartsignalhub_trading.sqlite3
```

Checks include integrity, staleness, open attempts, recorded failures, gap history,
run/config changes, disk space, pinned release/atomic/epoch configuration. Optional
`--backup-manifest PATH` checks manifest age only, not restore completeness. Nonzero
exit indicates findings. `ready_for_signoff` deliberately remains false pending
operational acceptance. No Codex automation has been created. Installation is host-specific; current deployment status is in the operating guide.

Run isolated tests:

```bash
venv/bin/python -m pytest -q platform_v2/shared/backend/research_evidence
```

They include subprocess hard exits before/after atomic publication, real SQLite
writers, optimistic conflicts, both cycle integrations, source-pin tamper/drift,
missing input chunks, multi-writer event recording, market recovery and neutrality.
The legacy negative crash test still illustrates why disabled mode is not certified.
Existing strategy/entry/exit regressions run separately; no historical test outcome
analysis. Synthetic60-day performance probes and3-DB online backup/restore checks
are documented in the local R2 completion report.

The copied-runtime comparison has passed for one ready Spot/Futures candle with
fixed market/clock, no external IO, identical business rows and complete evidence.
This is not coverage of every market state or a live operational soak.

The configured cutover verified a private SQLite runtime, installed monitoring,
and observed pinned atomic cycles and controlled restarts. This host completed
boot acceptance on 2026-10-05 after updating WSL and verifying a clean user bus,
one supervised runtime tree and fresh cycles; see the operating guide and dated
local evidence. No physical power-loss test was performed.
On other installations, flags require a separately reviewed cutover. Disabling
flags does not remove historical evidence.

## R2.1 operational helpers (explicit, not installed automatically)

`python -m platform_v2.shared.backend.research_evidence.checkpoint --source DIR
--destination NEW_DIR` makes online backups of all three canonical DBs and verifies
isolated restores; a successful manifest is written only after all succeed.

`python -m platform_v2.shared.backend.research_evidence.monitor --database DB
--expectations REVIEWED_JSON --backup-manifest MANIFEST --output LOG_DIR` is a local
cron-compatible monitor. It writes latest.json and daily JSONL, retaining 90 days;
it does not repair databases or change expected identities. It detects stale
actual decisions, stale open attempts, recent failures, release/config/epoch drift,
SQLite identity mismatch, disk/WAL size and backup-manifest age. Monitor failures
return nonzero and are visible in its report. The backup age check is not a restore
test. Deployment and Windows/WSL boot acceptance remain separate from these tools.
