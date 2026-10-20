"""Monitor the normal working-tree runtime; no launcher or source copies."""
import json
from pathlib import Path
from platform_v2.shared.backend.research_evidence.monitor import run


def covers(path):
    try:
        data = json.loads(path.read_text())
        names = {'smartsignalhub_trading.sqlite3', 'smartsignalhub_market_data.sqlite3', 'smartsignalhub_content.sqlite3'}
        if data.get('format') == 'verified-trading-epoch-archive-v1':
            required = {'database/'+name for name in names}
            return bool(data.get('completed_ms')) and required <= set(data.get('files', {})) and all((path.parent/name).is_file() for name in required)
        if 'databases' in data:
            return bool(data.get('completed_ms')) and {row['database'] for row in data['databases'] if row.get('restore_verified')} >= names and all((path.parent/name).is_file() for name in names)
        required = {'platform_v2/runtime/database/'+name for name in names}
        return required <= {row['path'] for row in data.get('files', [])} and all((path.parent/name).is_file() for name in required)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main():
    root = Path(__file__).resolve().parents[3]
    backup_root = Path('/home/sandro/backups/smartsignalhub')
    candidates = [p for p in backup_root.glob('*/manifest.json') if covers(p)]
    # A missing manifest is reported honestly; never depend on retired archives.
    fallback = backup_root/'manifest.json'
    backup = max(candidates, key=lambda p:p.stat().st_mtime) if candidates else fallback
    return run(root/'platform_v2/runtime/database/smartsignalhub_trading.sqlite3',
        Path(__file__).with_name('expectations.json'), backup,
        root/'platform_v2/runtime/research_health')


if __name__ == '__main__':
    raise SystemExit(main())
