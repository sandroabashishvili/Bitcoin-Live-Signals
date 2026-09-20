# Backup And Reset

Status: `active - SQLite-aware backup and reset`  
Created: `2026-05-19`  
Updated: `2026-09-12`  
Author: Codex  
Purpose: Runtime reset and backup workflow.

## Runtime Reset

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.runtime_reset_system
```

Stop the running system before reset; this tool does not stop processes.
Reset archives current runtime output and rebuilds 11 clean Spot/Futures/Hedge dashboard pages.
It also archives the SQLite database files and creates a clean database state.
Spot-only reset removes only Spot documents from SQLite.

Default reset archive destination:

```text
/home/sandro/runtime_archives/
```

This folder intentionally lives next to the project folder, not inside `platform_v2`.

Tool runtime logs belong under:

```text
platform_v2/runtime/logs/tools/
```

## Backup

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.backup_system
```

Default local backup destination:

```text
/home/sandro/SmartSignalHub_backups/
```

Windows path:

```text
\\wsl.localhost\Ubuntu\home\sandro\SmartSignalHub_backups
```

This folder intentionally lives next to the project folder, not inside:

```text
/home/sandro/SmartSignalHub/
```

The backup command creates the backup root automatically if it does not exist.

The live SQLite file, WAL and SHM files are excluded from ordinary raw file
copying. The backup tool creates a transactionally consistent SQLite snapshot
with SQLite's backup API and places it at the canonical database path inside
the backup. This remains safe while the runtime is writing.

Every new local backup is verified before the command reports success. The
verification checks manifest hashes, required content, ZIP membership and CRC,
and `PRAGMA quick_check` for every copied SQLite database. To recheck the latest
local backups later, run:

```bash
python3 -m platform_v2.tools.backup_system --diagnose
```

Backup scope note: all three active SQLite databases are copied consistently.
Generated dashboards and project artifacts remain in the normal project backup;
the GitHub Pages publish mirror stays excluded because it is rebuildable.

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.backup_system
```

## External Drive Mount Example

```bash
sudo mkdir -p /mnt/f
sudo mount -t drvfs F: /mnt/f
findmnt /mnt/f
```

Mounting the drive is not the backup itself. It only makes the Windows drive visible inside WSL. The backup command writes the actual backup.

## Current Notes

- local full backups are written as `full_YYYY-MM-DD_HH-MM-SS/`
- a matching `.zip` is created next to the folder
- external sync still uses `/mnt/d/SmartSignalHub_V2` and `/mnt/f/SmartSignalHub_V2`
- old project-local `backups/` remains excluded from backup input

Ordinary stop/start preserves positions and history. Full reset clears market history too. Public news HTML/JSON remain outside runtime roots; retained news may need content-only restoration after reset. Do not delete WAL/SHM files independently. See [runbook](runbook.md).
