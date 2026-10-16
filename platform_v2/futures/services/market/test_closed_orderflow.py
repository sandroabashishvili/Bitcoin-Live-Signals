import json
from unittest.mock import Mock
import pytest
from platform_v2.futures.services.market.binance_futures_orderflow_service import BinanceFuturesOrderflowService
from platform_v2.futures.infrastructure.market_data.orderbook_snapshot_repository import JsonOrderbookSnapshotRepository
import platform_v2.futures.infrastructure.market_data.orderbook_snapshot_repository as repository_module


def trade(ident,stamp,quantity='1',maker=False):
    return {'a':ident,'T':stamp,'q':quantity,'m':maker}


def service(pages):
    instance=BinanceFuturesOrderflowService();instance._request_aggtrades=Mock(side_effect=pages)
    return instance


def test_pagination_uses_ids_and_retains_multiple_trades_same_millisecond():
    instance=service([[trade(1,100),trade(2,100)],[trade(3,100),trade(4,900000)]])
    rows,pages=instance._collect_window('BTCUSDT',0,899999,2,10,10)
    assert [r['a'] for r in rows]==[1,2,3] and pages==2
    assert instance._request_aggtrades.call_args_list[1].kwargs['from_id']==3
    assert instance._request_aggtrades.call_args_list[1].kwargs['start_time'] is None


def test_full_final_millisecond_requires_tail_page():
    instance=service([[trade(1,899999),trade(2,899999)],[trade(3,899999)]])
    rows,pages=instance._collect_window('BTCUSDT',0,899999,2,10,10)
    assert len(rows)==3 and pages==2


def test_duplicate_page_boundary_is_deduplicated():
    first=trade(1,100);second=trade(2,200)
    instance=service([[first,second],[second,trade(3,300)],[]])
    rows,pages=instance._collect_window('BTCUSDT',0,899999,2,10,10)
    assert [r['a'] for r in rows]==[1,2,3] and pages==3


@pytest.mark.parametrize('pages',[
    [[trade(1,100),trade(2,200)],[trade(1,100),trade(2,200)]],
    [[trade(2,100),trade(1,200)]],
    [[trade(1,200),trade(2,100)]],
    [[trade(1,100,'nan')]],
    [[trade(1,-1)]],
    [[{'code':-1}]],
])
def test_bad_or_nonprogressing_pages_fail_closed(pages):
    with pytest.raises((ValueError,RuntimeError,KeyError)):
        service(pages)._collect_window('BTCUSDT',0,899999,2,10,10)


def test_cap_exhaustion_does_not_silently_return_partial_data():
    with pytest.raises(RuntimeError,match='budget exhausted'):
        service([[trade(1,100),trade(2,200)]])._collect_window('BTCUSDT',0,899999,2,1,10)


def test_empty_complete_range_is_explicit_zero_volume_not_old_snapshot():
    rows,pages=service([[]])._collect_window('BTCUSDT',0,899999,2,10,10)
    snapshot=BinanceFuturesOrderflowService._build_snapshot(symbol='BTCUSDT',timeframe='15m',trades=rows,
        window_start_ms=0,window_end_ms=899999,page_count=pages)
    assert snapshot.buyers==snapshot.sellers==snapshot.period_count==0
    assert snapshot.first_trade_ms is None and snapshot.last_trade_ms is None
    assert snapshot.completeness=='COMPLETE_CLOSED_WINDOW_V1'


def test_snapshot_records_trade_time_and_correct_boundary_label():
    snapshot=BinanceFuturesOrderflowService._build_snapshot(symbol='BTCUSDT',timeframe='15m',
        trades=[trade(1,100,'3'),trade(2,899998,'1',True)],window_start_ms=0,window_end_ms=899999,page_count=2)
    assert snapshot.timestamp_text=='1970-01-01 00:15:00'
    assert snapshot.dominance_ratio==snapshot.imbalance==.5
    assert snapshot.first_trade_ms==100 and snapshot.last_trade_ms==899998


def test_history_is_preserved_and_equal_volumes_do_not_collapse_windows():
    old={'timestamp_text':'1970-01-01 00:15:00','buyers':1,'sellers':2}
    new=dict(old,timestamp_text='1970-01-01 00:30:00')
    assert BinanceFuturesOrderflowService._merge_snapshot_row([old],new)==[old,new]
    assert BinanceFuturesOrderflowService._merge_snapshot_row([old],old)==[old]
    with pytest.raises(ValueError,match='overwrite historical'):
        BinanceFuturesOrderflowService._merge_snapshot_row([old],dict(old,buyers=3))


def test_incomplete_collection_never_calls_persistence(monkeypatch):
    import platform_v2.futures.services.market.binance_futures_orderflow_service as module
    write=Mock();monkeypatch.setattr(module,'replace_market_series',write)
    instance=service([[trade(1,100),trade(2,200)]])
    with pytest.raises(RuntimeError,match='budget exhausted'):
        instance.fetch_and_store(symbol='BTCUSDT',timeframe='15m',close_time_ms=899999,limit=2,max_pages=1)
    write.assert_not_called()


def test_repository_rejects_legacy_snapshot(monkeypatch):
    monkeypatch.setattr(repository_module,'read_market_series_safely',lambda **kw:[{'buyers':1,'sellers':2}])
    assert JsonOrderbookSnapshotRepository().get_latest_snapshot('BTCUSDT','15m') is None


def test_repository_accepts_explicit_complete_window(monkeypatch):
    from dataclasses import asdict
    row=asdict(BinanceFuturesOrderflowService._build_snapshot(symbol='BTCUSDT',timeframe='15m',trades=[trade(1,100)],
        window_start_ms=0,window_end_ms=899999,page_count=1))
    monkeypatch.setattr(repository_module,'read_market_series_safely',lambda **kw:[row])
    snapshot=JsonOrderbookSnapshotRepository().get_latest_snapshot('BTCUSDT','15m')
    assert snapshot.window_end_ms==899999 and snapshot.period_count==1


def test_request_cursor_does_not_send_conflicting_time_parameters(monkeypatch):
    import platform_v2.futures.services.market.binance_futures_orderflow_service as module
    from urllib.parse import urlparse,parse_qs
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self):return b'[]'
    urls=[]
    monkeypatch.setattr(module,'urlopen',lambda url,**kw:urls.append(url) or Response())
    BinanceFuturesOrderflowService()._request_aggtrades(symbol='BTCUSDT',from_id=123,limit=1000)
    assert parse_qs(urlparse(urls[0]).query)=={'symbol':['BTCUSDT'],'fromId':['123'],'limit':['1000']}


@pytest.mark.parametrize("book", [None, {"completeness": "COMPLETE_CLOSED_WINDOW_V1", "window_end_ms": 899999}, {"completeness": "LEGACY_UNKNOWN", "window_end_ms": 1799999}])
def test_market_context_rejects_invalid_flow(book):
    from types import SimpleNamespace
    from platform_v2.futures.services.signal.futures_market_context_service import FuturesMarketContextService
    context=FuturesMarketContextService()
    context._candle_repository=Mock()
    context._candle_repository.get_closed_candles.return_value=[SimpleNamespace(close_time_ms=1799999)]*40
    context._build_latest_snapshot=Mock(return_value=SimpleNamespace())
    context._orderbook_repository=Mock()
    context._orderbook_repository.get_latest_snapshot.return_value=None if book is None else SimpleNamespace(**book)
    with pytest.raises(RuntimeError,match="another candle"):
        context.build_context(symbol='BTCUSDT',timeframe='15m')


def test_futures_rejects_unsupported_hour_window():
    with pytest.raises(ValueError,match="Unsupported"):
        BinanceFuturesOrderflowService().fetch_and_store(symbol='BTCUSDT',timeframe='1h')


def test_api_failure_does_not_publish_empty_snapshot(monkeypatch):
    import platform_v2.futures.services.market.binance_futures_orderflow_service as module
    from urllib.error import URLError
    instance=BinanceFuturesOrderflowService()
    instance._request_aggtrades=Mock(side_effect=URLError("offline"))
    write=Mock()
    monkeypatch.setattr(module,'replace_market_series',write)
    with pytest.raises(URLError):
        instance.fetch_and_store(symbol='BTCUSDT',timeframe='15m',close_time_ms=899999)
    write.assert_not_called()


def test_ready_cycle_passes_decision_close_and_stops_on_collection_failure():
    from types import SimpleNamespace
    from platform_v2.futures.services.ops.main_cycle.execution import MainCycleExecutionService
    runner=object.__new__(MainCycleExecutionService)
    runner._orderflow_service=Mock()
    runner._orderflow_service.fetch_and_store.side_effect=RuntimeError('collection failed')
    runner._simulation_service=Mock()
    commit=Mock()
    with pytest.raises(RuntimeError,match='collection failed'):
        runner.run_ready_cycle(profile=SimpleNamespace(symbol='BTCUSDT',timeframe='15m'),
            date_iso='2026-10-15',fetched_candle_paths=(),
            cycle_info=SimpleNamespace(key='BTCUSDT:15m:899999'),commit_callback=commit)
    runner._orderflow_service.fetch_and_store.assert_called_once_with(
        symbol='BTCUSDT',timeframe='15m',limit=1000,close_time_ms=899999)
    runner._simulation_service.run.assert_not_called()
    commit.assert_not_called()


def test_matching_complete_context_is_accepted():
    from types import SimpleNamespace
    from platform_v2.futures.services.signal.futures_market_context_service import FuturesMarketContextService
    context=FuturesMarketContextService()
    context._candle_repository=Mock()
    context._candle_repository.get_closed_candles.return_value=[SimpleNamespace(close_time_ms=1799999)]*40
    context._build_latest_snapshot=Mock(return_value=SimpleNamespace())
    book=SimpleNamespace(completeness='COMPLETE_CLOSED_WINDOW_V1',window_end_ms=1799999)
    context._orderbook_repository=Mock()
    context._orderbook_repository.get_latest_snapshot.return_value=book
    context._mtf_service=Mock()
    context._mtf_service.build_signals.return_value=({},'NO_SIGNAL')
    assert context.build_context(symbol='BTCUSDT',timeframe='15m').latest_orderbook is book
