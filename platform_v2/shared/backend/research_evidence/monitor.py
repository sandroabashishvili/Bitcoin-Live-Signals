"""Independent local monitor; reads DB, writes bounded daily operational logs only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from .health import inspect


def run(database, expectations, backup_manifest, output):
    output.mkdir(parents=True,exist_ok=True)
    try:
        expected=json.loads(expectations.read_text())
        result=inspect(database,backup_manifest=backup_manifest,expectations=expected)
    except Exception as exc:
        result={'checked_ms':int(time.time()*1000),'ready_for_signoff':False,
                'issues':['MONITOR_FAILURE'],'error_type':type(exc).__name__}
    previous=output/'latest.json'
    if previous.exists():
        try:
            old=json.loads(previous.read_text())
            for key in ('database_bytes','wal_bytes'):
                if key in result and key in old:result[key+'_delta']=result[key]-old[key]
        except (ValueError,OSError):
            result['issues'].append('PREVIOUS_MONITOR_REPORT_UNREADABLE')
    data=json.dumps(result,sort_keys=True)
    temporary=output/'latest.tmp'
    temporary.write_text(data+'\n');temporary.replace(previous)
    day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    with (output/(day+'.jsonl')).open('a') as stream:stream.write(data+'\n')
    # This directory is dedicated to monitor output; retain 90 daily log files.
    for stale in sorted(output.glob('????-??-??.jsonl'))[:-90]:stale.unlink()
    return int(bool(result['issues']))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('database','expectations','backup-manifest','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    return run(a.database,a.expectations,a.backup_manifest,a.output)


if __name__=='__main__':raise SystemExit(main())
