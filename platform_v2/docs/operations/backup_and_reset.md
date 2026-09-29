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
