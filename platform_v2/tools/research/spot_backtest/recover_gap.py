"""Recover ONLY the known 21 missing Spot minutes in a NEW frozen workspace.

python -m platform_v2.tools.research.spot_backtest.recover_gap ORIGINAL NEW
No live database or original frozen input/result is modified.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys

from . import common as lab
from . import dataset

DAY='2026-08-24'
START=int(datetime(2026,8,24,19,46,tzinfo=timezone.utc).timestamp()*1000)
EXPECTED=set(range(START,START+21*60000,60000))


def equivalent(a,b):
    return all(abs(float(a[k])-float(b[k]))<=max(1e-7,abs(float(b[k]))*1e-10)
        for k in ('open','high','low','close','volume'))


def validate_recovery(existing, public, higher):
    """All daily overlap must agree; only exact missing minutes may be added."""
    rows={row['timestamp']:row for row,_ in public}
    day=START//86400000*86400000
    expected_day=set(range(day,day+86400000,60000))
    if len(public)!=1440 or set(rows)!=expected_day:raise ValueError('Public daily file is not complete/unique')
    local={stamp:row for stamp,row in existing.items() if day<=stamp<day+86400000}
    if expected_day-set(local)!=EXPECTED:raise ValueError('Local missing minutes differ from the declared 21-minute gap')
    for stamp,row in local.items():
        if not equivalent(row,rows[stamp]):raise ValueError('Public/local 1m OHLCV conflict at '+str(stamp))
    merged=local|{stamp:rows[stamp] for stamp in EXPECTED}
    checks=[]
    for bucket in sorted({stamp//900000*900000 for stamp in EXPECTED}):
        group=[merged[stamp] for stamp in range(bucket,bucket+900000,60000)]
        aggregate={'open':group[0]['open'],'close':group[-1]['close'],
            'high':max(r['high'] for r in group),'low':min(r['low'] for r in group),
            'volume':sum(r['volume'] for r in group)}
        if bucket not in higher or not equivalent(aggregate,higher[bucket]):
            raise ValueError('Recovered minutes disagree with existing 15m candle at '+str(bucket))
        checks.append({'open_ms':bucket,'OHLCV_match':True})
    return [rows[stamp] for stamp in sorted(EXPECTED)], {'overlap_1m_candles_checked':len(local),
        'overlap_conflicts':0,'higher_timeframe_crosschecks':checks}


def recover(original,target):
    original=lab.outside_live(original);target=lab.outside_live(target)
    if target==original or target.is_relative_to(original) or original.is_relative_to(target):
        raise ValueError('Recovery workspace must be separate from original')
    parent=json.loads((original/'protocol.json').read_text())
    if lab.digest(original/'market.sqlite3')!=parent['market_sha256']:raise ValueError('Original market hash mismatch')
    target.mkdir(parents=True,exist_ok=False)
    try:
        public,meta=dataset.public_file(target/'public',DAY,tf='1m')
        with sqlite3.connect((original/'market.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
            minutes={stamp:json.loads(payload) for stamp,payload in db.execute("SELECT stamp,payload FROM candles WHERE tf='1m'")}
            higher={stamp:json.loads(payload) for stamp,payload in db.execute("SELECT stamp,payload FROM candles WHERE tf='15m'")}
            added,checks=validate_recovery(minutes,public,higher)
            with sqlite3.connect(target/'market.sqlite3') as fresh:
                db.backup(fresh)
                for row in added:dataset.insert_candle(fresh,'1m',row,meta['url'])
                fresh.execute('INSERT INTO imports VALUES(?,?)',(meta['url'],json.dumps(meta|checks|{'added_minutes':len(added)})))
                fresh.commit()
                if fresh.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Recovered SQLite integrity failed')
                coverage=dataset.coverage(fresh)
                if coverage['1m']['gaps']!=0:raise ValueError('Internal 1m gaps remain')
                if fresh.execute('SELECT count(*) FROM conflicts').fetchone()[0]!=parent['overlap_conflicts']:
                    raise ValueError('Recovery introduced conflicts')
        shutil.copytree(original/'source',target/'source')
        shutil.copytree(original/'public',target/'public',dirs_exist_ok=True)
        shutil.copyfile(original/'flow_crosscheck.json',target/'flow_crosscheck.json')
        protocol=dict(parent)
        protocol.update(created_utc=datetime.now(timezone.utc).isoformat(),coverage=coverage,
            market_sha256=lab.digest(target/'market.sqlite3'),parent_workspace=str(original),
            parent_protocol_sha256=lab.digest(original/'protocol.json'),parent_market_sha256=parent['market_sha256'],
            recovery={'added_minutes':len(added),'first_open_ms':min(EXPECTED),'last_open_ms':max(EXPECTED),
                'official_archive':meta,'checks':checks,'method':'Insert missing minutes ONLY; all original OHLCV and flow rows retained.'})
        protocol['public_imports']=[dict(item,file=str(target/'public'/Path(item['file']).name)) if item.get('file') else item
            for item in parent['public_imports']]
        lab.write(target/'protocol.json',protocol)
        (target/'market.sqlite3').chmod(0o444)
        if lab.digest(original/'market.sqlite3')!=parent['market_sha256']:raise ValueError('Original dataset unexpectedly changed')
        lab.write(target/'recovery.json',protocol['recovery']|{'original_unchanged':True,'new_internal_1m_gaps':0})
        (target/'REPORT.md').write_text('# Verified missing-minute recovery\n\n'
            f'Source: {meta["url"]}\n\n'
            'Recovered 21 BTCUSDT Spot 1m candles: 2026-08-24 19:46–20:06 UTC.\n'
            f'Official SHA-256 verified; {checks["overlap_1m_candles_checked"]} overlapping 1m candles agree; '
            'two enclosing 15m OHLCV aggregates agree. No interpolation.\n\n'
            'Original frozen workspace, live runtime and all prior experiment results are untouched. '
            'This new workspace contains recovered inputs only; previous segmented-account performance is NOT continuous-account performance. '
            'New continuous-account replays must produce their own new run results.\n')
        lab.write(target/'recovery_manifest.json',{'source_sha256':lab.digest(Path(__file__)),
            'files':{p.name:lab.digest(p) for p in target.iterdir() if p.is_file()}})
        print(json.dumps(protocol['recovery']|{'workspace':str(target)},indent=2))
    except Exception as exc:
        lab.write(target/'RECOVERY_FAILED.json',{'error':str(exc),'original_workspace_unchanged':True,
            'instruction':'Do not use this incomplete new workspace; original segmented evidence remains intact.'})
        raise


if __name__=='__main__':
    recover(Path(sys.argv[1]),Path(sys.argv[2]))
