"""Build a compact, provenance-preserving offline dataset; never repair live tables."""
import csv
import hashlib
import io
import json
import math
import sqlite3
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

MINUTE=60000
INTERVALS={'1m':MINUTE,'5m':5*MINUTE,'15m':15*MINUTE,'30m':30*MINUTE,'1h':60*MINUTE,'2h':120*MINUTE,'4h':240*MINUTE}


def stamp_ms(value):
    value=int(value)
    return value//1000 if value>=10**14 else value


def validate_candle(row,tf):
    interval=INTERVALS[tf];start=row['timestamp']
    if isinstance(start,bool) or not isinstance(start,int) or start%interval:
        raise ValueError('Unaligned candle')
    if row['close_time']!=start+interval-1:raise ValueError('Wrong candle close')
    values=[float(row[k]) for k in ('open','high','low','close','volume')]
    if any(not math.isfinite(v) for v in values) or min(values[:4])<=0 or values[-1]<0:
        raise ValueError('Invalid OHLCV')
    o,h,l,c,_=values
    if not l<=min(o,c)<=max(o,c)<=h:raise ValueError('Impossible OHLC')
    return row


def parse_klines(data,tf='15m'):
    rows=[]
    for index,cells in enumerate(csv.reader(io.StringIO(data.decode('utf-8-sig')))):
        if not cells:continue
        if index==0 and cells[0].lower() in ('open_time','open time'):continue
        if len(cells)<12:raise ValueError('Truncated kline CSV')
        start,end=stamp_ms(cells[0]),stamp_ms(cells[6])
        row=dict(timestamp=start,close_time=end,open=float(cells[1]),high=float(cells[2]),
            low=float(cells[3]),close=float(cells[4]),volume=float(cells[5]))
        validate_candle(row,tf)
        buy=float(cells[9]);total=row['volume']
        if not math.isfinite(buy) or not 0<=buy<=total+1e-8:raise ValueError('Invalid taker-buy volume')
        count=int(cells[8])
        if count<0:raise ValueError('Invalid exchange trade count')
        rows.append((row,{'window_start_ms':start,'window_end_ms':end,'buyers':buy,
            'sellers':max(0,total-buy),'raw_trade_count':count,
            'source':'binance_public_spot_kline_taker_volume_v1'}))
    return rows


def public_file(folder,period,tf='15m'):
    """Download requested small Spot klines plus official checksum; no credentials."""
    if tf not in ('1m','15m'):raise ValueError('Unsupported public archive interval')
    kind='monthly' if len(period)==7 else 'daily'
    name=f'BTCUSDT-{tf}-{period}.zip'
    url=f'https://data.binance.vision/data/spot/{kind}/klines/BTCUSDT/{tf}/{name}'
    folder.mkdir(parents=True,exist_ok=True)
    with urlopen(url+'.CHECKSUM',timeout=25) as response:checksum=response.read(1024).decode()
    expected=checksum.split()[0]
    if len(expected)!=64:raise ValueError('Invalid official checksum')
    checksum_path=folder/(name+'.CHECKSUM')
    if not checksum_path.exists():
        with checksum_path.open('x') as stream:stream.write(checksum)
    target=folder/name
    if not target.exists():
        with urlopen(url,timeout=30) as response:
            data=response.read(8*1024*1024+1)
        if len(data)>8*1024*1024:raise ValueError('Historical kline size budget exceeded')
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Public checksum mismatch')
        with target.open('xb') as output:output.write(data)
    else:data=target.read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Cached public checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries=archive.infolist()
        if len(entries)!=1 or entries[0].file_size>32*1024*1024:raise ValueError('Unexpected public archive')
        rows=parse_klines(archive.read(entries[0]),tf)
    return rows,{'url':url,'sha256':expected,'rows':len(rows),'file':str(target)}


def create_schema(db):
    db.executescript('''CREATE TABLE candles(tf TEXT,stamp INTEGER,close_ms INTEGER,payload TEXT,source TEXT,PRIMARY KEY(tf,stamp));
CREATE TABLE flow(close_ms INTEGER PRIMARY KEY,payload TEXT,source TEXT);
CREATE TABLE conflicts(tf TEXT,stamp INTEGER,retained_source TEXT,rejected_source TEXT);
CREATE TABLE imports(source TEXT PRIMARY KEY,payload TEXT);''')


def insert_candle(db,tf,row,source):
    validate_candle(row,tf)
    canonical={k:row[k] for k in ('timestamp','close_time','open','high','low','close','volume')}
    text=json.dumps(canonical,sort_keys=True)
    previous=db.execute('SELECT payload,source FROM candles WHERE tf=? AND stamp=?',(tf,row['timestamp'])).fetchone()
    if previous:
        old=json.loads(previous[0])
        if any(old[k]!=canonical[k] for k in canonical):
            db.execute('INSERT INTO conflicts VALUES(?,?,?,?)',(tf,row['timestamp'],previous[1],source))
        return
    db.execute('INSERT INTO candles VALUES(?,?,?,?,?)',(tf,row['timestamp'],row['close_time'],text,source))


def import_market(db,path,cutoff):
    """Priority is explicit: first source wins. Conflicting overlaps remain visible."""
    source=str(path.resolve());count=0
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as src:
        src.execute('BEGIN')
        tables={r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'market_observations' not in tables:return
        for tf,text in src.execute("SELECT timeframe,payload_json FROM market_observations WHERE venue='binance' AND market_type='spot' AND dataset='candles' AND symbol='BTCUSDT' AND event_time_ms<? ORDER BY timeframe,event_time_ms",(cutoff,)):
            if tf not in INTERVALS:continue
            row=json.loads(text)
            if row['close_time']>=cutoff:continue
            insert_candle(db,tf,row,source);count+=1
    db.execute('INSERT INTO imports VALUES(?,?)',(source,json.dumps({'rows_read':count,'cutoff_ms':cutoff})))


def add_public_flow(db,rows,source):
    matched=missing=conflicting=0
    for row,flow in rows:
        existing=db.execute("SELECT payload FROM candles WHERE tf='15m' AND stamp=?",(row['timestamp'],)).fetchone()
        if existing is None:missing+=1;continue
        original=json.loads(existing[0])
        if any(abs(float(original[k])-float(row[k]))>max(1e-7,abs(float(row[k]))*1e-10) for k in ('open','high','low','close','volume')):
            conflicting+=1;continue
        db.execute('INSERT INTO flow VALUES(?,?,?)',(flow['window_end_ms'],json.dumps(flow),source));matched+=1
    return {'matched_local_candles':matched,'missing_local_candles':missing,'conflicting_local_candles':conflicting}


def segments(stamps,interval):
    result=[]
    for stamp in stamps:
        if not result or stamp!=result[-1][-1]+interval:result.append([])
        result[-1].append(stamp)
    return result


def coverage(db):
    result={}
    for tf in INTERVALS:
        stamps=[r[0] for r in db.execute('SELECT stamp FROM candles WHERE tf=? ORDER BY stamp',(tf,))]
        if not stamps:continue
        groups=segments(stamps,INTERVALS[tf])
        result[tf]={'candles':len(stamps),'first_ms':stamps[0],'last_ms':stamps[-1],
            'gaps':len(groups)-1,'missing_intervals':sum((b[0]-a[-1])//INTERVALS[tf]-1 for a,b in zip(groups,groups[1:])),
            'continuous_segments':[{'start_ms':g[0],'end_ms':g[-1]+INTERVALS[tf],'candles':len(g)} for g in groups]}
    return result


def crosscheck_flow(db,market_path):
    checked=0;maximum=0.;bad=[]
    with sqlite3.connect(market_path.resolve().as_uri()+'?mode=ro',uri=True) as market:
        market.execute('BEGIN')
        for text, in market.execute("SELECT payload_json FROM market_observations WHERE venue='binance' AND market_type='spot' AND dataset='orderflow' AND symbol='BTCUSDT' AND timeframe='15m'"):
            row=json.loads(text)
            if row.get('completeness')!='COMPLETE_CLOSED_WINDOW_V1':continue
            found=db.execute('SELECT payload FROM flow WHERE close_ms=?',(row['window_end_ms'],)).fetchone()
            if found is None:continue
            flow=json.loads(found[0])
            difference=max(abs(row[k]-flow[k]) for k in ('buyers','sellers'))
            maximum=max(maximum,difference);checked+=1
            if difference>1e-7:bad.append({'close_ms':row['window_end_ms'],'difference':difference})
    if bad:raise ValueError('Historical candle volumes disagree with complete aggTrade snapshots')
    return {'checked_candles':checked,'volume_mismatches':bad,'max_absolute_BTC_difference':maximum,
        'threshold_BTC':1e-7,'counts_compared':False,'comparison':'Official candle taker volumes versus paginated aggregate trades; counts have different semantics.'}
