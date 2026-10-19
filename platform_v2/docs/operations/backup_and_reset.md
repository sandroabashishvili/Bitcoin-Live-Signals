# Backup and Reset Semantics

Updated: 2026-09-28. Everyday backup commands, destinations and current deployment
are maintained in the [operating guide](runbook.md). Implementation belongs to
`~/workspace_tools/backup`; there is no project-local backup launcher.

## Consistent backups

Use the tool's SQLite backup API snapshots, not a raw copy of a changing database
file. The three databases are individually consistent snapshots, not necessarily
one shared instant. Preserve verification manifests and inspect errors, missing
external targets and restore evidence. Manifest age alone does not verify restore.
GitHub source history does not contain runtime databases or private configuration.
Full backup includes sensitive recovery state and is not a whole-disk image.

## Deliberate reset only

Reset is not needed for restart, code updates or documentation changes. It ends
the continuity of the current collection epoch. Never reset during accumulation
without an explicit new-experiment decision and a reviewed activation/epoch plan.
Stop the owning service first and verify a backup; the reset tool does not stop
processes itself. To inspect the proposed scope without resetting:

```bash
cd ~/SmartSignalHub
venv/bin/python -m platform_v2.tools.runtime_reset_system --dry-run
```

A full reset archives runtime roots/databases under `~/runtime_archives/` and
rebuilds empty dashboards. It clears trading and market history in the active
storage. Spot-only reset has a narrower scope. Consult the tool help for flags.
Do not delete WAL/SHM companions independently. Public HTML/news JSON can remain
outside reset roots; they are not proof that a new content database has those rows.
Historical content-only recovery scripts are not general restoration commands.

## Prospective trading-only epoch preparation

To prepare an ALL-system Spot/Futures/Hedge new-cohort plan without touching
production, use a new destination:

```bash
venv/bin/python -m platform_v2.tools.runtime_reset_system.epoch_plan /home/sandro/research_snapshots/trading_epoch_preflight_NEW
```

This read-only preflight records database boundaries, current release/monitor
identities, recent orderflow window completeness, market coverage counts and
remaining cutover gates. It copies deployment configuration into the report,
not database contents: this is NOT a backup or authorization to reset. The
destination must not exist or overlap live runtime/deployment. Coverage counts
do not prove gap-free history. The current service is not stopped or restarted.

`runtime_reset_system/trading_archive.py` provides an isolated, tested archive
primitive for a reviewed cutover: with the owning service explicitly stopped,
the supervisor lock held and same-user manual writers absent, first create and
verify self-contained SQLite backups of all three DBs, then rotate only the
trading DB and its sidecars. Market/content remain in place. Legacy filesystem
engine state causes refusal pending separate archival. Append-only evidence is
archived whole, not deleted in place. Pre-activation failure attempts rollback
without overwriting newly appeared files; retained journal/backups support recovery.

The primitive intentionally has NO executable CLI and does not rotate the
activation epoch, rebuild dashboards or restart production. A coordinated
activation/monitoring configuration transition and post-start acceptance are
still required before actually beginning a fresh epoch. Do not substitute the
existing full reset or bare start command for that procedure. Research candidate
strategy changes are not implicitly approved by starting a new collection epoch.

### Reviewed all-system cutover

`python -m platform_v2.tools.runtime_reset_system.epoch_cutover PLAN_DIR NEW_ARCHIVE`
validates a sealed preflight and deployment drift without stopping/resetting.
Adding `--apply` is an explicitly authorized ALL-system paper-account reset:
wait for current atomic attempts to finish, stop the owning user service, acquire
the supervisor lock, verify archived databases, rotate trading only, coordinate
activation/monitoring epoch configuration and restart the owning service once.
The latest closed 15m candle at the end of archival becomes the expected epoch;
actual first observed decisions must still be checked after startup. This does
not synthesize signals missed during downtime or alter the approved strategy.

If the writer guard rejects the operation before rotation, the original DB/config
are intact: restore the original owning service while diagnosing the guard.
If failure occurs after rotation/config update, leave the service stopped and
review `transition.json`, `deployment_before/`, `raw_trading/` and the verified
`database/` copies together. Never restart on mixed old/new configuration.
No automatic rollback may overwrite a newly created DB. Post-start health,
configuration identity, first-cycle receipts and fresh-account acceptance are
required before declaring the cutover complete.

After successful cutover, user-approved retention may remove `raw_trading/`
ONLY after the self-contained `database/` backups have passed an actual SQLite
restore/integrity/foreign-key/table-count check. Retain deployment configuration
and verification evidence beside that single backup set. In such a compacted
archive, restore from `database/`, not the intentionally removed raw files; never
overwrite the new epoch's active DB without first preserving it separately.
