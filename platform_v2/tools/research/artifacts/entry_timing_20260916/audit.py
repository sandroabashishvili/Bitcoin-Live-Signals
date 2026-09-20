"""Read-only decision comparison, not a portfolio/PnL backtest."""
from pathlib import Path
import sqlite3,json
from collections import Counter
from dataclasses import asdict
from platform_v2.futures.services.simulation.entry_quality_service import FuturesEntryQualityService
root=Path(__file__).resolve().parents[5]
c=sqlite3.connect((root/'platform_v2/runtime/database/smartsignalhub_trading.sqlite3').as_uri()+'?mode=ro',uri=True)
with c:
    signals=[json.loads(r[0]) for r in c.execute("SELECT payload_json FROM runtime_rows WHERE system='futures' AND family='futures_signals' ORDER BY timestamp_ms")]
c.close()
service=FuturesEntryQualityService()
history=[]; rows=[]
for row in signals:
    if '2026-09-14 22:59:59Z'<=row.get('candle_close_time','')<='2026-09-15 17:29:59Z':
        new=service.evaluate(signal_side=row['side'],timestamp_ms=row['timestamp_ms'],prior_signals=history,
                             market_plan_permission=row.get('market_plan_permission'))
        checks=dict(row['permission_checks']);checks['entry_quality']=new.allowed
        rows.append({'time':row['candle_close_time'],'old':row.get('entry_quality'), 'candidate':asdict(new),
                     'would_pass_recorded_checks':all(checks.values()),
                     'failed_checks':[k for k,v in checks.items() if not v]})
    history.append(row)
summary={'scope':'Recorded decision checks only; positions/cooldowns/exits are NOT replayed; no profitability claim',
         'rows':len(rows),'candidate_reasons':dict(Counter(r['candidate']['reason'] for r in rows)),
         'pass_recorded_checks':sum(r['would_pass_recorded_checks'] for r in rows),'decisions':rows}
Path(__file__).with_name('comparison.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='decisions'},indent=2))
