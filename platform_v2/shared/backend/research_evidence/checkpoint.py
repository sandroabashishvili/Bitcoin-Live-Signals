"""Explicit verified online backup of the three DBs; never restore over live files."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time

NAMES=('smartsignalhub_trading.sqlite3','smartsignalhub_market_data.sqlite3','smartsignalhub_content.sqlite3')


def verify(path):
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        integrity=[r[0] for r in db.execute('PRAGMA integrity_check')]
        foreign=list(db.execute('PRAGMA foreign_key_check'))
        if integrity!=['ok'] or foreign:raise ValueError('backup integrity verification failed')
        names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts={name:db.execute('SELECT count(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in names}
    return counts


def create(source,destination):
    destination.mkdir(parents=True,exist_ok=False)
    results=[]
    for name in NAMES:
        src=source/name;copy=destination/name
        # No create-on-missing source and no raw copying of active WAL databases.
        with sqlite3.connect(src.resolve().as_uri()+'?mode=ro',uri=True,timeout=30) as live:
            with sqlite3.connect(copy) as backup:live.backup(backup,pages=256,sleep=0.05)
        counts=verify(copy)
        restored=destination/('restore-'+name)
        shutil.copyfile(copy,restored)
        if verify(restored)!=counts:raise ValueError('restored table counts differ')
        digest=hashlib.sha256(copy.read_bytes()).hexdigest()
        if hashlib.sha256(restored.read_bytes()).hexdigest()!=digest:raise ValueError('restore digest mismatch')
        restored.unlink()
        results.append({'database':name,'sha256':digest,'integrity':'ok','restore_verified':True,'table_counts':counts})
    report={'completed_ms':int(time.time()*1000),'sqlite_version':sqlite3.sqlite_version,
            'scope':'individually consistent online snapshots, not one cross-DB transaction', 'databases':results}
    (destination/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args();print(json.dumps(create(a.source,a.destination),indent=2))


if __name__=='__main__':main()
