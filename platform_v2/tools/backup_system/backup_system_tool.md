# Backup System Tool

Status: `active`
Updated: `2026-08-24`

## Purpose

`platform_v2.tools.backup_system` creates local ZIP backups and optional external drive copies.

There are six supported profiles:

- `all-critical` runs both important backup sets in one command.
- `smartsignalhub` backs up the SmartSignalHub workspace.
- `home-critical` backs up selected personal/work folders from `/home/sandro` without caches, virtual environments, credentials, or large tool state.
- `linux-migration-final` creates the final private migration set on both configured external drives.
- `migration-private` preserves selected WSL home data, Codex state, Git/SSH credentials, runtime archives, and SmartSignalHub `.env`.
- `windows-critical` preserves Windows Codex state and selected user files needed after migration.

## Final Linux Migration Backup

This profile is intentionally private and unencrypted. It contains credentials,
authentication state and private keys because it is meant for Sandro's final
machine migration only. Keep both destination drives under physical control.

Before running it, close the Codex desktop app and make sure `D:` and `F:` are
mounted. Then run:

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.backup_system --profile linux-migration-final --sync-usb -q
```

It creates three timestamped sets on both drives:

- `SmartSignalHub_V2`
- `Sandro_WSL_Migration_Private`
- `Windows_User_Critical`

Every copied folder, manifest, ZIP CRC, required path, hash and included SQLite
database is verified automatically. Exit code `0` means all six external copies
(three on `D:`, three on `F:`) passed verification. The profile excludes virtual
environments, `node_modules`, caches, Quality System artifacts and Ollama models.

## Recommended Command

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.backup_system
```

Default behavior:

- Creates a SmartSignalHub backup.
- Creates a home-critical backup.
- Syncs both backup sets to configured USB/flash targets when available.
- Uses descriptive names such as `full_SmartSignalHub_V2_2026-07-29_23-47-43`.
- Continues with the second profile when one external target is unavailable.

## Local Only

```bash
python3 -m platform_v2.tools.backup_system --local-only
```

This creates both local backup sets without attempting USB or flash sync.

Each new local backup is verified automatically: manifest hashes, ZIP CRC and
contents, required files, and every SQLite database's integrity are checked.

## Diagnose Latest Backups

```bash
python3 -m platform_v2.tools.backup_system --diagnose
```

This checks the required source paths and fully verifies the latest local
SmartSignalHub and home-critical backups without creating a new copy.

## SmartSignalHub Only

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.backup_system --profile smartsignalhub
```

Default target names:

- Local: `/home/sandro/SmartSignalHub_backups`
- USB: `/mnt/d/SmartSignalHub_V2`
- Flash: `/mnt/f/SmartSignalHub_V2`

## Home Critical Only

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.backup_system --profile home-critical
```

Default target names:

- Local: `/home/sandro/Sandro_home_backups`
- USB: `/mnt/d/Sandro_Home_Critical`
- Flash: `/mnt/f/Sandro_Home_Critical`

Included by default:

- `portfolio_projects/**`
- `SV SANDRO/**`
- `docs/**`
- `docs_archive_platform_v2/**`
- `research_snapshots/**`
- `Screenshot/**`
- `CODEX_MASTER_CONTEXT.md`
- `terminal_commands_reference.md`
- `# SmartSignalHub AI Assistant — Vis.txt`
- `ტექნიკური მონაცემები.txt`

Excluded by default:

- caches: `.cache`, `.npm`
- editor/tool state: `.vscode-server`, `.codex`, `.claude`, `.gemini`, `.ollama`
- credentials/secrets: `.ssh`, `.git-credentials`
- generated dependencies: `.venv`, `venv`, `node_modules`, `__pycache__`
- temporary browser state: `lighthouse-profile` and generated Quality System scan artifacts
- unencrypted environment secrets: `.env`
- existing backups and runtime archives

## Reliability

- Dangling symbolic links and source files that disappear during a running backup are skipped with a warning instead of aborting the whole profile.
- Manifests and ZIP archives are built only from files that were copied successfully.
- A successful command means the new folder and its ZIP passed hash, CRC,
  required-content and SQLite integrity checks.
- Verification also rejects accidental `.env`, credentials, Git metadata,
  virtual environments, dependency folders, caches, and browser profiles.

## Notes

Normal backup ZIPs are not encrypted and exclude `.env` files, private keys,
auth tokens, and credentials. The explicit `linux-migration-final` profile is
the exception: it deliberately includes that private state and therefore must
not be shared or left on an untrusted drive.
