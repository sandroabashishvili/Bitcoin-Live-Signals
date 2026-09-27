"""Read-only evidence health inspection. No schema migration, repair or checkpoint."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import time


def inspect(path: Path, *, stale_after_ms=1200000, backup_manifest: Path | None=None):
    now=int(time.time()*1000)
    result={'database':str(path),'checked_ms':now,'ready_for_signoff':False,'issues':[]}
    if not path.exists():
        result['issues'].append('EVIDENCE_DATABASE_MISSING')
        return result
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
    try:
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'research_runs' not in names:
            result['issues'].append('EVIDENCE_NOT_ACTIVATED')
            return result
        result['quick_check']=[r[0] for r in db.execute('PRAGMA quick_check')]
        if result['quick_check']!=['ok']:
            result['issues'].append('INTEGRITY_FAILURE')
        result['systems']={}
        for system in ('spot','futures'):
            latest=db.execute('SELECT MAX(at_ms) FROM cycle_attempt_events WHERE system=?',(system,)).fetchone()[0]
            incomplete=db.execute('''SELECT count(*) FROM cycle_attempt_events s WHERE s.system=? AND s.kind='STARTED'
                AND NOT EXISTS (SELECT 1 FROM cycle_attempt_events t WHERE t.attempt_id=s.attempt_id
                AND t.kind IN ('COMMITTED','FAILED','INTERRUPTED','ABANDONED'))''',(system,)).fetchone()[0]
            gaps=db.execute("SELECT count(*) FROM cycle_gap_events WHERE system=? AND kind='DETECTED'",(system,)).fetchone()[0]
            decisions=db.execute('SELECT payload_json FROM decision_observations WHERE system=?',(system,)).fetchall()
            bad=sum(not json.loads(r[0]).get('evidence_complete',False) for r in decisions)
            errors=sum(bool(json.loads(r[0]).get('recorder_errors')) for r in db.execute(
                "SELECT payload_json FROM cycle_attempt_events WHERE system=? AND kind IN ('COMMITTED','FAILED','INTERRUPTED')",(system,)))
            config_refs={json.loads(r[0]).get('config_sha256') for r in db.execute('SELECT payload_json FROM research_runs WHERE system=?',(system,))}
            latest_run=db.execute("SELECT payload_json FROM research_runs WHERE system=? AND kind='STARTED' ORDER BY id DESC LIMIT 1",(system,)).fetchone()
            run=json.loads(latest_run[0]) if latest_run else {}
            if not run.get('release_verified'):
                result['issues'].append(system+':UNPINNED_RELEASE')
            if not run.get('atomic_simulation'):
                result['issues'].append(system+':ATOMIC_SIMULATION_DISABLED')
            if not run.get('activation_close_ms'):
                result['issues'].append(system+':GAP_EPOCH_UNDEFINED')

            result['systems'][system]={'last_event_ms':latest,'incomplete_attempts':incomplete,
                'gap_detections':gaps,'incomplete_decision_evidence':bad,'attempts_with_recorder_errors':errors,
                'run_config_identities':len(config_refs)}
            if latest is None or now-latest>stale_after_ms:
                result['issues'].append(system+':STALE_OR_ABSENT')
            if bad or errors:
                result['issues'].append(system+':EVIDENCE_INCOMPLETE')
            if incomplete:
                result['issues'].append(system+':OPEN_ATTEMPTS_REVIEW')
            if gaps:
                result['issues'].append(system+':GAP_HISTORY_REVIEW')
            if len(config_refs)>1:
                result['issues'].append(system+':CONFIG_CHANGE_REVIEW')
        result['free_bytes']=shutil.disk_usage(path.parent).free
        if result['free_bytes']<5*1024**3:
            result['issues'].append('DISK_SPACE_LOW')
        if backup_manifest is not None:
            result['backup_manifest_age_ms']=now-int(backup_manifest.stat().st_mtime*1000) if backup_manifest.exists() else None
            age=result['backup_manifest_age_ms']
            if age is None or age>48*3600000:
                result['issues'].append('BACKUP_MANIFEST_MISSING_OR_STALE')
            result['backup_check_scope']='manifest age only; not a restore/integrity test'
    finally:
        db.close()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--backup-manifest',type=Path)
    args=parser.parse_args()
    result=inspect(args.database,backup_manifest=args.backup_manifest)
    print(json.dumps(result,indent=2))
    return int(bool(result['issues']))


if __name__=='__main__':
    raise SystemExit(main())
