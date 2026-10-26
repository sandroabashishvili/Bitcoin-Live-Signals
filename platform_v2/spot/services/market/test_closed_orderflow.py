import json
from unittest.mock import Mock
import pytest
from platform_v2.spot.services.market.binance_orderbook_service import BinanceOrderbookService
from platform_v2.spot.infrastructure.market_data.orderbook_snapshot_repository import JsonOrderbookSnapshotRepository
import platform_v2.spot.infrastructure.market_data.orderbook_snapshot_repository as repository_module


def trade(ident,stamp,quantity='1',maker=False):
    return {'a':ident,'T':stamp,'q':quantity,'m':maker}


def service(pages):
    instance=BinanceOrderbookService();instance._request_aggtrades=Mock(side_effect=pages)
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
    snapshot=BinanceOrderbookService._build_snapshot(symbol='BTCUSDT',timeframe='15m',trades=rows,
        window_start_ms=0,window_end_ms=899999,page_count=pages)
    assert snapshot.buyers==snapshot.sellers==snapshot.period_count==0
    assert snapshot.first_trade_ms is None and snapshot.last_trade_ms is None
    assert snapshot.completeness=='COMPLETE_CLOSED_WINDOW_V1'


def test_snapshot_records_trade_time_and_correct_boundary_label():
    snapshot=BinanceOrderbookService._build_snapshot(symbol='BTCUSDT',timeframe='15m',
        trades=[trade(1,100,'3'),trade(2,899998,'1',True)],window_start_ms=0,window_end_ms=899999,page_count=2)
    assert snapshot.timestamp_text=='1970-01-01 00:15:00'
    assert snapshot.dominance_ratio==snapshot.imbalance==.5
    assert snapshot.first_trade_ms==100 and snapshot.last_trade_ms==899998


def test_history_is_preserved_and_equal_volumes_do_not_collapse_windows():
    old={'timestamp_text':'1970-01-01 00:15:00','buyers':1,'sellers':2}
    new=dict(old,timestamp_text='1970-01-01 00:30:00')
    assert BinanceOrderbookService._merge_snapshot_row([old],new)==[old,new]
    assert BinanceOrderbookService._merge_snapshot_row([old],old)==[old]
    with pytest.raises(ValueError,match='overwrite historical'):
        BinanceOrderbookService._merge_snapshot_row([old],dict(old,buyers=3))


def test_incomplete_collection_never_calls_persistence(monkeypatch):
    import platform_v2.spot.services.market.binance_orderbook_service as module
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
    row=asdict(BinanceOrderbookService._build_snapshot(symbol='BTCUSDT',timeframe='15m',trades=[trade(1,100)],
        window_start_ms=0,window_end_ms=899999,page_count=1))
    monkeypatch.setattr(repository_module,'read_market_series_safely',lambda **kw:[row])
    snapshot=JsonOrderbookSnapshotRepository().get_latest_snapshot('BTCUSDT','15m')
    assert snapshot.window_end_ms==899999 and snapshot.period_count==1


def test_request_cursor_does_not_send_conflicting_time_parameters(monkeypatch):
    import platform_v2.spot.services.market.binance_orderbook_service as module
    from urllib.parse import urlparse,parse_qs
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self):return b'[]'
    urls=[]
    monkeypatch.setattr(module,'urlopen',lambda request,**kw:urls.append(request.full_url) or Response())
    BinanceOrderbookService()._request_aggtrades(symbol='BTCUSDT',from_id=123,limit=1000)
    assert parse_qs(urlparse(urls[0]).query)=={'symbol':['BTCUSDT'],'fromId':['123'],'limit':['1000']}


def test_market_context_rejects_wrong_candle_even_if_complete():
    from types import SimpleNamespace
    from platform_v2.spot.services.market.market_context_service import MarketContextService
    candles=Mock();candles.get_closed_candles.return_value=[SimpleNamespace(close_time_ms=1799999)]
    indicators=Mock();indicators.get_latest_snapshot.return_value=SimpleNamespace()
    books=Mock();books.get_latest_snapshot.return_value=SimpleNamespace(completeness='COMPLETE_CLOSED_WINDOW_V1',window_end_ms=899999)
    context=MarketContextService(candle_repository=candles,indicator_snapshot_repository=indicators,orderbook_snapshot_repository=books)
    with pytest.raises(RuntimeError,match='another candle'):context.build_context('BTCUSDT','15m')
