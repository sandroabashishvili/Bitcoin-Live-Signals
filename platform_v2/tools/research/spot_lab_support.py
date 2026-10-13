"""Private persistence/clock/input adapters around pinned production Spot services."""
import copy
import dataclasses
import functools
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import datetime,UTC
from types import SimpleNamespace


def plain(value):
    if dataclasses.is_dataclass(value):value=dataclasses.asdict(value)
    return json.loads(json.dumps(value,allow_nan=False))


def millis(text):
    parsed=datetime.fromisoformat(text.replace('Z','+00:00'))
    if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp()*1000)


def historical_fill_time(orders,symbol,timeframe,price,quote_time,default):
    matches=[r for r in orders if r.get('fill') and r['request']['symbol']==symbol
        and r['request']['timeframe']==timeframe and r['fill']['fill_price']==price
        and quote_time<=r['fill']['filled_at_ms']<quote_time+900000]
    if len(matches)>1:raise ValueError('Ambiguous historical paper fill')
    return matches[0]['fill']['filled_at_ms'] if matches else default


class SpotStore:
    def __init__(self,output):self.output=output;self.docs={};self.events=[]
    def documents(self,family):return [(date,rows) for (f,date),rows in sorted(self.docs.items()) if f==family]
    def all(self,family):return [r for date,rows in self.documents(family) for r in rows]
    def write(self,family,date,value,key=None):
        row=plain(value);rows=self.docs.setdefault((family,date),[])
        if key:
            index=next((i for i,r in enumerate(rows) if r.get(key)==row.get(key)),None)
            if index is None:rows.append(row)
            else:rows[index]=row
        else:rows.append(row)
        self.events.append({'family':family,'date':date,'row':copy.deepcopy(row)})
        return self.output/'replay.sqlite3'


class SpotReplay:
    def __init__(self,output,db,prices,blob,tail,protocol,model,baseline,limit):
        from platform_v2.spot.services.account.position_state_service import PositionStateService
        from platform_v2.spot.services.account.portfolio_state_service import PortfolioStateService
        from platform_v2.spot.services.account.position_batch_update_service import PositionBatchUpdateService
        from platform_v2.spot.services.permission.signal_permission_runtime_service import SignalPermissionRuntimeService
        from platform_v2.spot.services.signal.signal_runtime_service import SignalRuntimeService
        from platform_v2.spot.services.market.market_context_service import MarketContextService
        from platform_v2.spot.config import settings
        self.output,self.db,self.prices,self.blob,self.tail=output,db,prices,blob,tail
        self.protocol,self.model,self.baseline,self.limit=protocol,model,baseline,limit
        self.store=SpotStore(output);self.clock=0;self.initial=None;self.initial_net=None
        self.fill_clock=0
        self.recorded_orders=[json.loads(r[0]) for r in db.execute("SELECT payload_json FROM runtime_rows WHERE system='spot' AND family='orders' ORDER BY date_iso,ordinal")]
        self.cycles=[];self.mismatches=[];self.prestate_mismatches=[];self.quote_missing=[]
        self.settings=settings
        self.candle_chunks=functools.lru_cache(maxsize=512)(self._candle_chunk)
        self.position_state=PositionStateService()
        self.portfolio_state=PortfolioStateService(position_state_service=self.position_state)
        self.batch=PositionBatchUpdateService(position_state_service=self.position_state)
        self.context_service=MarketContextService()
        self.signals=SignalRuntimeService(market_context_service=self.context_service)
        self.pipeline=SignalPermissionRuntimeService(signal_runtime_service=self.signals,
            portfolio_state_service=self.portfolio_state,position_state_service=self.position_state)
        self._patch()

    def _candle_chunk(self,symbol,timeframe,ref):
        from platform_v2.spot.infrastructure.market_data.candle_repository import JsonCandleRepository
        values=tuple(JsonCandleRepository._parse_candle_row(symbol,timeframe,r) for r in self.blob(ref))
        if any(c is None for c in values):raise ValueError('Invalid captured candle')
        return values

    def _patch(self):
        from platform_v2.spot.services.account import position_state_service,position_runtime_service,position_batch_update_service
        from platform_v2.spot.services.signal import signal_runtime_service
        from platform_v2.spot.services.permission import signal_permission_runtime_service,denied_entry_runtime_service
        from platform_v2.spot.services.trading import order_execution_service
        position_state_service.load_family_documents=self.store.documents
        position_runtime_service.load_family_rows_all=self.store.all
        signal_runtime_service.load_family_rows_all=self.store.all
        writers={'write_position_record':('positions','position_id'),'write_signal_record':('signals','timestamp_ms'),
                 'write_denied_entry_record':('denied_entries',None),'write_order_record':('orders',None),
                 'write_force_close_record':('force_closes',None)}
        for module in (position_runtime_service,position_batch_update_service,signal_runtime_service,signal_permission_runtime_service,denied_entry_runtime_service):
            for function,(family,key) in writers.items():
                if hasattr(module,function):
                    def write(*,date_iso,family=family,key=key,**kw):
                        return self.store.write(family,date_iso,next(iter(kw.values())),key)
                    setattr(module,function,write)
        signal_permission_runtime_service.utc_now_ms=lambda:self.clock
        order_execution_service.utc_now_ms=lambda:self.fill_clock
        replay=self
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):
                value=cls.fromtimestamp(replay.clock/1000,UTC)
                return value.astimezone(tz) if tz else value.replace(tzinfo=None)
        for module in (position_state_service,position_runtime_service,position_batch_update_service,signal_permission_runtime_service):
            module.datetime=Clock

    def reads(self,evidence,first=False):
        docs={};market={}
        for ref in evidence['input_refs']:
            m=self.blob(ref);identity=m['identity']
            if len(identity)==6:market[tuple(identity)]=m
            elif len(identity)==2 and identity[0]=='sqlite_document_queries.py:read_document':
                args=json.loads(identity[1])
                if args.get('system')!='spot':continue
                key=(args['family'],args['date_iso'])
                if first and key in docs:continue
                value=[]
                for ref in m['chunks']:value.extend(self.blob(ref))
                if len(value)!=1:raise ValueError('Expected one captured document')
                if isinstance(value[0],list):docs[key]=value[0]
        return docs,market

    def latest(self):return [plain(p) for p in self.position_state.load_latest_positions(as_of_date_iso=self.date)]

    def accounting(self):
        from platform_v2.spot.services.account.fee_service import FeeService
        positions=self.position_state.load_latest_positions(as_of_date_iso=self.date)
        opens=[p for p in positions if p.is_open];closed=[p for p in positions if p.is_closed]
        net=sum(FeeService.net_pnl_value(p) for p in closed)
        fees=FeeService.open_entry_fees_total(opens)
        unrealized=sum(float(p.unrealized_pnl or 0) for p in opens)
        state=self.portfolio_state.build_state(as_of_date_iso=self.date)
        return {'closed_net_pnl':round(net,2),'equity':round(self.settings.DEFAULT_STARTING_BALANCE+net-fees+unrealized,2),
                'unrealized_pnl':round(unrealized,2),'available_balance':state.available_balance,
                'reserved':state.current_open_exposure,'open_positions':len(opens),'closed_positions':len(closed),
                'total_positions':len(positions),'open_entry_fees':fees}

    def step(self,oid,first,last):
        from platform_v2.spot.infrastructure.market_data.candle_repository import JsonCandleRepository
        from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import JsonIndicatorSnapshotRepository
        from platform_v2.spot.infrastructure.market_data.orderbook_snapshot_repository import JsonOrderbookSnapshotRepository
        from platform_v2.shared.backend.market import MarketQuote
        record=last['record'];stamp=record['timestamp_ms'];symbol,tf=record['symbol'],record['timeframe']
        self.clock=millis(record['decision_time']) if record.get('decision_time') else first['available_ms']
        self.date=datetime.fromtimestamp(self.clock/1000,UTC).date().isoformat()
        before_docs,_=self.reads(first,first=True)
        _,market=self.reads(last)
        if self.initial is None:
            self.store.docs={key:copy.deepcopy(rows) for key,rows in before_docs.items() if key[0] in ('positions','signals')}
            for key in list(self.store.docs):
                if key[0]=='signals':self.store.docs[key]=[r for r in self.store.docs[key] if int(r.get('timestamp_ms') or 0)<stamp]
            self.initial=copy.deepcopy(self.latest());self.initial_net=self.accounting()['closed_net_pnl']
        elif self.baseline and self.model=='observed':
            expected={}
            for key,rows in sorted(before_docs.items()):
                if key[0]=='positions':
                    for r in rows:
                        p=self.position_state._parse_position_row(r)
                        if p:expected[p.position_id]=plain(p)
            if self.latest()!=list(expected.values()):
                self.prestate_mismatches.append({'observation_id':oid,'actual':self.latest(),'expected':list(expected.values())})
        candles={}
        for timeframe in ('1m','5m','15m','4h'):
            m=market[('binance','crypto','spot','candles',symbol,timeframe)]
            refs=m['chunks'] if timeframe=='1m' else m['chunks'][-2:]
            values=[c for ref in refs for c in self.candle_chunks(symbol,timeframe,ref)]
            if timeframe!='1m':values=values[-256:]
            candles[timeframe]=[c for c in values if c.close_time_ms<=self.clock+999]
        candle_repo=SimpleNamespace(get_closed_candles=lambda symbol,timeframe,limit=None: candles[timeframe][-limit:] if limit else candles[timeframe])
        self.batch._candle_repository=candle_repo;self.context_service._candle_repository=candle_repo
        snapshots={}
        for timeframe in ('5m','15m','4h'):
            r=self.tail(market[('binance','crypto','spot','indicators',symbol,timeframe)],1)[-1]
            rtime=r.get('timestamp_ms') or r.get('close_time_ms')
            if rtime is None:rtime=millis(r['datetime'])
            if rtime>self.clock+999:raise ValueError('Future indicator')
            snapshots[timeframe]=JsonIndicatorSnapshotRepository._parse_snapshot_row(symbol=symbol,timeframe=timeframe,row=r)
        self.context_service._indicator_snapshot_repository=SimpleNamespace(get_latest_snapshot=lambda symbol,timeframe:snapshots[timeframe])
        book_rows=self.tail(market[('binance','crypto','spot','orderflow',symbol,tf)],1)
        book=JsonOrderbookSnapshotRepository()
        import platform_v2.spot.infrastructure.market_data.orderbook_snapshot_repository as book_module
        book_module.read_market_series_safely=lambda **kw:book_rows
        self.context_service._orderbook_snapshot_repository=book
        price,time,source=record.get('execution_quote_price'),record.get('execution_quote_time_ms'),record.get('execution_quote_source')
        if self.model=='next-minute':
            available=max(last['available_ms'],self.clock+999,time or 0)
            time=(available//60000+1)*60000
            rows=self.prices.execute("SELECT payload_json FROM market_observations WHERE venue='binance' AND market_type='spot' AND dataset='candles' AND symbol=? AND timeframe='1m' AND event_time_ms=? AND event_time_ms+60000<=?",(symbol,time,self.protocol['end_ms'])).fetchall()
            if len(rows)!=1:price=None;self.quote_missing.append(oid)
            else:
                r=json.loads(rows[0][0]);price=float(r['open']);source='research_next_1m_open'
                if r['timestamp']!=time or r['close_time']!=time+59999:raise ValueError('Invalid model candle')
            self.clock=time;self.date=datetime.fromtimestamp(time/1000,UTC).date().isoformat()
        quote=None if price is None else MarketQuote(symbol,'spot',price,time,source)
        if quote and (not math.isfinite(price) or price<=0):raise ValueError('Invalid quote')
        self.pipeline._resolve_execution_quote=lambda **kw:(quote,None if quote else 'historical_quote_missing')
        self.fill_clock=self.clock
        if self.model=='observed' and quote:
            self.fill_clock=historical_fill_time(self.recorded_orders,symbol,tf,price,time,self.clock)
        before=self.accounting();start=len(self.store.events)
        self.batch.run(date_iso=self.date)
        result=self.pipeline.run_for_symbol(symbol=symbol,timeframe=tf,date_iso=self.date)
        actual=plain(result.signal)
        keys=('side','evaluated_direction','component_scores','component_weights','direction_scores','gates','mtf_signals','mtf_direction','score','threshold','setup_confidence','entry_quality','theoretical_setup')
        if self.model=='observed':keys+=('decision_time','execution_quote_price','execution_quote_time_ms','execution_quote_source')
        different=[k for k in keys if actual.get(k)!=record.get(k)] if self.baseline else []
        if different:self.mismatches.append({'observation_id':oid,'fields':different,'actual':{k:actual.get(k) for k in different},'expected':{k:record.get(k) for k in different}})
        if self.baseline and self.model=='observed' and result.denied_entry:
            expected=[json.loads(r[0]) for r in self.db.execute("SELECT payload_json FROM runtime_rows WHERE system='spot' AND family='denied_entries' AND json_extract(payload_json,'$.signal.timestamp_ms')=?",(stamp,))]
            matches=[r for r in expected if r['signal'].get('execution_quote_time_ms')==time]
            if len(matches)!=1 or plain(result.permission)!=matches[0].get('permission'):
                self.mismatches.append({'observation_id':oid,'fields':['permission'],'actual':plain(result.permission),'expected':[r.get('permission') for r in matches]})
        self.cycles.append({'observation_id':oid,'timestamp_ms':stamp,'clock_ms':self.clock,'signal':actual,
           'permission':plain(result.permission) if result.permission else None,'account_before':before,'account_after':self.accounting(),
           'events':copy.deepcopy(self.store.events[start:]),'positions':self.latest()})

    def finish(self):
        if not self.cycles:raise ValueError('No complete Spot cycles')
        historical=not self.mismatches and not self.prestate_mismatches
        terminal_match=None
        if self.baseline and self.model=='observed' and not self.limit:
            expected={}
            for date,text in self.db.execute("SELECT date_iso,payload_json FROM runtime_rows WHERE system='spot' AND family='positions' ORDER BY date_iso,ordinal"):
                p=self.position_state._parse_position_row(json.loads(text))
                if p:expected[p.position_id]=plain(p)
            terminal_match=self.latest()==list(expected.values());historical &= terminal_match
        if not self.baseline:
            root=self.output.parent/'baseline-next-minute'
            base=json.loads((root/'portfolio.json').read_text())
            if self.initial!=base['initial_positions'] or [r['observation_id'] for r in self.cycles]!=[r['observation_id'] for r in base['cycles']]:raise ValueError('Candidate account/cohort differs')
            for a,b in zip(self.cycles,base['cycles']):
                if any(v!=b['signal']['component_scores'][k] for k,v in a['signal']['component_scores'].items() if k!='mtf'):
                    raise ValueError('Undeclared Spot component changed')
        final=self.accounting()
        result={'passed':historical if self.baseline else True,'model':self.model,'limit':self.limit,
          'historical_parity_ok':historical if self.model=='observed' else None,'signal_parity_ok':not self.mismatches if self.baseline else None,
          'terminal_positions_match':terminal_match,'mismatches':self.mismatches,'prestate_mismatches':self.prestate_mismatches,
          'initial_positions':self.initial,'initial_closed_net':self.initial_net,'final_positions':self.latest(),
          'period_net_pnl':round(final['closed_net_pnl']-self.initial_net,2),'final_account':final,
          'actions':dict(Counter(r['signal']['side'] for r in self.cycles)),
          'evaluated_directions':dict(Counter(r['signal']['evaluated_direction'] for r in self.cycles)),
          'cycles':self.cycles,'missing_modeled_quotes':self.quote_missing,
          'limitations':['Spot paper execution and fee/SL/TP/profit-lock rules retained',
             'No tick/exchange fill claim; next-minute execution is a model',
             'Point-in-time captured indicators retained, not changing indicator formulas',
             'Complete first-attempt capture chains used; later retry decisions not substituted',
             'Inherited positions retained; period PnL is ledger-recognized closed net',
             'No automatic production promotion; reused period is exploratory']}
        with sqlite3.connect(self.output/'replay.sqlite3') as d:
            d.execute('CREATE TABLE rows(family TEXT,date TEXT,ordinal INTEGER,payload_json TEXT)')
            for (family,date),rows in self.store.docs.items():
                d.executemany('INSERT INTO rows VALUES(?,?,?,?)',[(family,date,i,json.dumps(r,sort_keys=True)) for i,r in enumerate(rows)])
            d.execute('CREATE TABLE states(name TEXT PRIMARY KEY,payload_json TEXT)')
            d.executemany('INSERT INTO states VALUES(?,?)',[('initial',json.dumps(self.initial)),('final',json.dumps(self.latest()))])
            if d.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Private SQLite corruption')
        (self.output/'portfolio.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
        return result
