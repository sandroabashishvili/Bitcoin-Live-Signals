"""Sequential raw-market simulation using pinned native Spot decision/execution code."""
import bisect,json,sqlite3
from collections import Counter
from datetime import datetime,timezone
from types import SimpleNamespace
if __package__:
    from .dataset import INTERVALS,segments
    from ..spot_lab_support import SpotReplay,SpotStore,plain
else:
    from inputs import INTERVALS,segments
    from native_adapters import SpotReplay,SpotStore,plain


def contiguous_tail(stamps,end,interval,count):
    index=bisect.bisect_right(stamps,end)
    if index<count:return None
    tail=stamps[index-count:index]
    if tail[-1]!=end or tail[-1]-tail[0]!=(count-1)*interval:return None
    return index


def eligibility(stamp,flow_closes,warm,minute_closes,minute_opens):
    if stamp not in flow_closes:return 'missing_verified_flow'
    if any((stamp if tf!='4h' else (stamp+1)//INTERVALS['4h']*INTERVALS['4h']-1) not in warm[tf] for tf in ('5m','15m','4h')):
        return 'indicator_warmup_or_gap'
    quote_time=stamp+60001
    if quote_time not in minute_opens or contiguous_tail(minute_closes,quote_time-1,60000,16) is None:
        return 'missing_entry_or_exit_minutes'
    return None


def validate_account_segments(groups,request):
    if request and (len(groups)!=1 or len(groups[0])!=request['expected_cycles']):
        raise ValueError('Continuous experiment must have exactly one fully covered account segment and declared cycle count')


class NativeAccount(SpotReplay):
    def __init__(self,output):
        from platform_v2.spot.services.account.position_state_service import PositionStateService
        from platform_v2.spot.services.account.portfolio_state_service import PortfolioStateService
        from platform_v2.spot.services.account.position_batch_update_service import PositionBatchUpdateService
        from platform_v2.spot.services.signal.signal_runtime_service import SignalRuntimeService
        from platform_v2.spot.services.permission.signal_permission_runtime_service import SignalPermissionRuntimeService
        from platform_v2.spot.config import settings
        self.output=output;self.store=SpotStore(output);self.clock=self.fill_clock=0;self.settings=settings
        self.position_state=PositionStateService()
        self.portfolio_state=PortfolioStateService(position_state_service=self.position_state)
        self.batch=PositionBatchUpdateService(position_state_service=self.position_state)
        self.context=None
        self.signals=SignalRuntimeService(market_context_service=SimpleNamespace(build_context=lambda **kw:self.context))
        self.pipeline=SignalPermissionRuntimeService(signal_runtime_service=self.signals,
            portfolio_state_service=self.portfolio_state,position_state_service=self.position_state)
        self._patch()


def run(root,output,variant='baseline'):
    from platform_v2.spot.infrastructure.market_data.candle_repository import JsonCandleRepository
    from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import JsonIndicatorSnapshotRepository
    from platform_v2.spot.services.analytics.indicator_snapshot_builder import IndicatorSnapshotBuilder
    from platform_v2.spot.services.signal.mtf_context_service import MultiTimeframeContextService
    from platform_v2.spot.domain.models.market_context import MarketContext
    from platform_v2.spot.domain.models.orderbook_snapshot import OrderbookSnapshot
    from platform_v2.shared.backend.market import MarketQuote
    if __package__:
        from .candidates import CandidateSignalService,SUPPORTED_CANDIDATES
    else:
        from candidates import CandidateSignalService,SUPPORTED_CANDIDATES
    if variant not in ('baseline','unchanged','control_v2',*SUPPORTED_CANDIDATES):
        raise ValueError('Unknown backtest variant: '+variant)
    candidate_mode=variant in SUPPORTED_CANDIDATES

    with sqlite3.connect((root/'market.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        candles={};closes={};indicators={};warm={}
        for tf in ('1m','5m','15m','4h'):
            raw=[json.loads(r[0]) for r in db.execute('SELECT payload FROM candles WHERE tf=? ORDER BY stamp',(tf,))]
            parsed=[JsonCandleRepository._parse_candle_row('BTCUSDT',tf,r) for r in raw]
            if any(c is None for c in parsed):raise ValueError('Native candle parser rejected input')
            candles[tf]=parsed;closes[tf]=[c.close_time_ms for c in parsed]
            if tf=='1m':continue
            indicators[tf]={};warm[tf]=set()
            # Reset native indicator recurrence at every raw candle gap; never use future rows.
            start=0
            for index in range(len(parsed)+1):
                if index<len(parsed) and (index==0 or closes[tf][index]==closes[tf][index-1]+INTERVALS[tf]):continue
                group=parsed[start:index];start=index
                if len(group)<200:continue
                rows=IndicatorSnapshotBuilder().build_rows(symbol='BTCUSDT',timeframe=tf,candles=group)
                for row in rows:
                    stamp=int(datetime.fromisoformat(row['datetime']).replace(tzinfo=timezone.utc).timestamp()*1000)+999
                    snap=JsonIndicatorSnapshotRepository._parse_snapshot_row(symbol='BTCUSDT',timeframe=tf,row=row)
                    if snap is None:raise ValueError('Native indicator parser rejected recomputed input')
                    indicators[tf][stamp]=snap
                warm[tf].update(c.close_time_ms for c in group[199:])
            print('Recomputed',tf,len(indicators[tf]),'indicator rows',flush=True)
        flows={stamp:json.loads(text) for stamp,text in db.execute('SELECT close_ms,payload FROM flow')}

    eligible=[];skipped=Counter();one_minute={c.open_time_ms:c for c in candles['1m']}
    for stamp in closes['15m']:
        reason=eligibility(stamp,flows,warm,closes['1m'],one_minute)
        if reason:skipped[reason]+=1;continue
        eligible.append(stamp)
    declared=json.loads((output/'candidate_protocol.json').read_text())
    paired=declared.get('paired_account');decision_stamps=None;recorded=None
    if paired:
        if candidate_mode:raise ValueError('Matched-account audit cannot test new strategy candidates')
        if __package__:
            from .paired_support import select_cohort,RecordedDecisions
        else:
            from paired_support import select_cohort,RecordedDecisions
        records=json.loads((output/'recorded_signals.json').read_text())
        eligible,decision_stamps=select_cohort(eligible,records,paired['start_ms'],paired['end_ms'])
        if len(decision_stamps)!=paired['expected_common_cycles']:raise ValueError('Matched cycle count changed')
        if paired['mode']=='recorded':recorded=RecordedDecisions(records)
        elif paired['mode']!='recomputed':raise ValueError('Unknown matched-account mode')
    groups=segments(eligible,900000)
    request=declared.get('continuous_experiment')
    validate_account_segments(groups,request)
    summaries=[];all_cycles=[]
    for number,group in enumerate(groups,1):
        account=NativeAccount(output);mtf=MultiTimeframeContextService()
        if paired and account.settings.DEFAULT_STARTING_BALANCE!=paired['initial_balance_USDT']:
            raise ValueError('Native starting capital differs from declared matched account')
        if recorded is not None:account.signals._signal_decision_service=recorded
        candidate=CandidateSignalService(variant) if candidate_mode else None
        if candidate is not None:account.signals._signal_decision_service=candidate
        for stamp in group:
            quote_time=stamp+60001;account.clock=account.fill_clock=quote_time
            account.date=datetime.fromtimestamp(quote_time/1000,timezone.utc).date().isoformat()
            snaps={tf:indicators[tf][stamp if tf!='4h' else (stamp+1)//INTERVALS['4h']*INTERVALS['4h']-1] for tf in ('5m','15m','4h')}
            flow=flows[stamp];total=flow['buyers']+flow['sellers']
            dominance=(flow['buyers']-flow['sellers'])/total if total else 0.
            # This is reconstructed from official candle taker volumes, NOT fabricated aggTrade rows.
            book=OrderbookSnapshot(symbol='BTCUSDT',timeframe='15m',
                timestamp_text=datetime.fromtimestamp((stamp+1)/1000,timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                buyers=round(flow['buyers'],8),sellers=round(flow['sellers'],8),dominance_ratio=round(dominance,6),imbalance=round(dominance,6),
                momentum_classification='bullish' if dominance>.3 else 'bearish' if dominance<-.3 else 'neutral',
                period_count=flow['raw_trade_count'],source=flow['source'],window_start_ms=stamp-899999,window_end_ms=stamp,
                completeness='RESEARCH_VERIFIED_CANDLE_FLOW_V1')
            index=bisect.bisect_right(closes['15m'],stamp)
            signals,direction=mtf.build_signals(timeframe_snapshots=snaps,primary_timeframe='15m')
            account.context=MarketContext(symbol='BTCUSDT',timeframe='15m',latest_snapshot=snaps['15m'],latest_orderbook=book,
                recent_candles=tuple(candles['15m'][max(0,index-200):index]),mtf_signals=signals,mtf_direction=direction)
            if candidate is not None:candidate.snapshots=snaps
            def read_candles(symbol,timeframe,limit=None):
                end=bisect.bisect_right(closes[timeframe],quote_time-1 if timeframe=='1m' else stamp)
                return candles[timeframe][max(0,end-limit):end] if limit else candles[timeframe][:end]
            account.batch._candle_repository=SimpleNamespace(get_closed_candles=read_candles)
            price=one_minute[quote_time].open_price
            quote=MarketQuote('BTCUSDT','spot',price,quote_time,'research_raw_next_1m_open')
            account.pipeline._resolve_execution_quote=lambda **kw:(quote,None)
            account.batch.run(date_iso=account.date)
            if decision_stamps is not None and stamp not in decision_stamps:
                # Both arms skip the unavailable decision, but exit management continues.
                all_cycles.append({'segment':number,'timestamp_ms':stamp,'quote_ms':quote_time,
                    'signal':None,'permission':None,'account':account.accounting(),'missing_recorded_decision':True})
                continue
            result=account.pipeline.run_for_symbol(symbol='BTCUSDT',timeframe='15m',date_iso=account.date)
            all_cycles.append({'segment':number,'timestamp_ms':stamp,'quote_ms':quote_time,'signal':plain(result.signal),
                'permission':plain(result.permission) if result.permission else None,'account':account.accounting()})
            if candidate is not None:all_cycles[-1]['candidate']=candidate.last_diagnostics
            if len(all_cycles)%500==0:print('Raw backtest cycles',len(all_cycles),flush=True)
        positions=account.latest();closed=[p for p in positions if p['status']=='CLOSED']
        summaries.append({'segment':number,'start_ms':group[0]-899999,'last_signal_close_ms':group[-1],
            'cycles':len(group),'initial_balance_USDT':account.settings.DEFAULT_STARTING_BALANCE,
            'final_account':account.accounting(),'positions':positions,
            'new_positions':len(positions),'closed_positions':len(closed),'open_positions':len(positions)-len(closed),
            'closed_net_USDT':round(sum(p['net_pnl'] for p in closed),4),
            'exit_reasons':dict(Counter(p['exit_reason'] for p in closed)),
            'boundary':'Open positions remain open/marked at segment end; never silently carried across missing data or forced closed.'})
        print('Finished segment',number,'cycles',len(group),'positions',len(positions),flush=True)
    result={'format':'raw-spot-backtest-v1','cycles':len(all_cycles),'segments':summaries,'skipped':dict(skipped),
        'actions':dict(Counter(r['signal']['side'] for r in all_cycles if r['signal'] is not None)),
        'new_positions':sum(s['new_positions'] for s in summaries),'closed_positions':sum(s['closed_positions'] for s in summaries),
        'closed_net_USDT':round(sum(s['closed_net_USDT'] for s in summaries),4),
        'limitations':['Separate fresh accounts per covered segment; combined net is NOT a continuous-account return.',
            'Native indicator formulas recomputed causally on contiguous history, with at least 200 bars; not captured old indicator snapshots.',
            'Historical kline buy/sell volumes, not historical order-book depth; raw trade count differs from aggregate trade count.',
            'Fixed 60s decision delay, exact next-minute open fill, native fees, zero additional slippage, OHLC exits; not actual exchange fills.',
            'No five-scenario/4-of-6 candidate yet; this establishes the current-code raw-input baseline.']}
    if not all_cycles:raise ValueError('No fully covered historical cycles')
    if len(groups)==1:
        result['limitations'][0]='One continuous account for the entire covered cohort; no internal balance/position reset. Closed net excludes remaining open positions; inspect final marked equity too.'
    if candidate_mode:
        result['variant']=variant
        result['limitations'][-1]='Exploratory equal-vote candidate; no holdout. Native weighted confidence retained for adaptive setup/other native consumers, not for voting. Scenario trigger overlaps STRUCTURE vote.'
    if paired:
        result['paired_account']=paired
        result['limitations'][-1]='Matched fresh-account diagnostic, NOT operational ledger reproduction. Both arms use reconstructed context and fixed modeled fills; recorded decisions are exogenous historical outputs, possibly known later than modeled execution. Their entry quality is recomputed from fresh history. Missing recorded decisions skip entry in BOTH arms, never fabricate NO_SIGNAL; exits continue. Differences are not solely causal ORDERBOOK effects.'
    (output/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    with (output/'cycles.jsonl').open('w') as stream:
        for row in all_cycles:stream.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('segments','limitations')},indent=2))
    return result
