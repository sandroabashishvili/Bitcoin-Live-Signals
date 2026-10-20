"""Run pinned monitor against the newest manifest covering all three runtime DBs.

Selection checks coverage and files exist; monitor freshness is not restore proof.
"""
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
NAMES={'smartsignalhub_trading.sqlite3','smartsignalhub_market_data.sqlite3','smartsignalhub_content.sqlite3'}

def covers(path):
    try:
        data=json.loads(path.read_text())
        if data.get('format')=='verified-trading-epoch-archive-v1':
            required={'database/'+n for n in NAMES}
            return (bool(data.get('completed_ms')) and required<=set(data.get('files',{}))
                    and all((path.parent/n).is_file() for n in required))
        if 'databases' in data:
            return (data.get('completed_ms') and
                    {d['database'] for d in data['databases'] if d.get('restore_verified')}>=NAMES and
                    all((path.parent/n).is_file() for n in NAMES))
        names={item['path'] for item in data.get('files',[])}
        required={'platform_v2/runtime/database/'+n for n in NAMES}
        return required<=names and all((path.parent/n).is_file() for n in required)
    except (OSError,ValueError,KeyError,TypeError):
        return False


def main():
    args=json.loads((HERE/'monitor-command.json').read_text())
    candidates=[p for p in Path('/home/sandro/backups/smartsignalhub').glob('*/manifest.json') if covers(p)]
    configured=Path(args[args.index('--backup-manifest')+1])
    if covers(configured):candidates.append(configured)
    if candidates:
        args[args.index('--backup-manifest')+1]=str(max(candidates,key=lambda p:p.stat().st_mtime))
    # Missing/stale fallback manifest is reported by the pinned monitor.
    return subprocess.run(args,check=False).returncode


if __name__=='__main__':sys.exit(main())
