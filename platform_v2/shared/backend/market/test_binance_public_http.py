from __future__ import annotations

from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import Mock
import importlib
import json
from types import SimpleNamespace

import pytest
import platform_v2.shared.backend.market.binance_public_http as http_module

from platform_v2.shared.backend.market.binance_public_http import BinancePublicHttpClient


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.headers = Message()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._payload


def test_public_client_reads_json() -> None:
    client = BinancePublicHttpClient(opener=lambda *_args, **_kwargs: _Response(b'{"ok": true}'))

    assert client.get_json("https://example.test") == {"ok": True}


def test_public_client_honors_retry_after_for_429() -> None:
    calls = 0
    waits: list[float] = []
    headers = Message()
    headers["Retry-After"] = "3"

    def opener(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError(
                "https://example.test",
                429,
                "rate limited",
                headers,
                BytesIO(b""),
            )
        return _Response(b"[]")

    client = BinancePublicHttpClient(opener=opener, sleeper=waits.append)

    assert client.get_json("https://example.test") == []
    assert calls == 2
    assert waits == [3.0]


def test_timeout_retries_are_bounded_and_use_the_same_url():
    opener = Mock(side_effect=[TimeoutError('slow'), TimeoutError('slow'), _Response(b'[]')])
    waits = []
    client = BinancePublicHttpClient(opener=opener, sleeper=waits.append)
    assert client.get_json('https://example.test/aggTrades?fromId=123') == []
    assert waits == [1.0, 2.0]
    assert [c.args[0].full_url for c in opener.call_args_list] == ['https://example.test/aggTrades?fromId=123'] * 3
    assert [c.kwargs['timeout'] for c in opener.call_args_list] == [15.0] * 3


def test_permanent_timeout_stops_after_three_attempts():
    opener = Mock(side_effect=TimeoutError('offline'))
    waits = []
    with pytest.raises(TimeoutError, match='offline'):
        BinancePublicHttpClient(opener=opener, sleeper=waits.append).get_json('https://example.test')
    assert opener.call_count == 3 and waits == [1.0, 2.0]


@pytest.mark.parametrize('status,retried', [(400, False), (403, False), (503, True)])
def test_retry_only_transient_http_errors(status, retried):
    error = HTTPError('https://example.test', status, 'failure', Message(), BytesIO())
    opener = Mock(side_effect=[error, _Response(b'[]')])
    client = BinancePublicHttpClient(opener=opener, sleeper=lambda _: None)
    if retried:
        assert client.get_json('https://example.test') == []
        assert opener.call_count == 2
    else:
        with pytest.raises(HTTPError):
            client.get_json('https://example.test')
        assert opener.call_count == 1


@pytest.mark.parametrize('status', [418, 429])
def test_long_retry_after_is_not_shortened_or_retried_inside_budget(monkeypatch, status):
    monkeypatch.setattr(http_module, 'monotonic', lambda: 0.0)
    headers = Message(); headers['Retry-After'] = '180'
    error = HTTPError('https://example.test', status, 'wait', headers, BytesIO())
    opener = Mock(side_effect=error); sleeper = Mock()
    assert BinancePublicHttpClient._retry_delay(headers, 0) == 180
    with pytest.raises(TimeoutError, match='safe retry'):
        BinancePublicHttpClient(opener=opener, sleeper=sleeper).get_json('https://example.test', deadline=120)
    opener.assert_called_once(); sleeper.assert_not_called()


def test_remaining_deadline_limits_timeout_and_prevents_another_attempt(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(http_module, 'monotonic', lambda: now[0])
    def slow(*args, **kwargs):
        assert kwargs['timeout'] == 2.0
        now[0] = 2.0
        raise TimeoutError('slow')
    opener = Mock(side_effect=slow); sleeper = Mock()
    with pytest.raises(TimeoutError):
        BinancePublicHttpClient(opener=opener, sleeper=sleeper).get_json('https://example.test', deadline=2)
    opener.assert_called_once(); sleeper.assert_not_called()


def test_expired_budget_does_not_start_request(monkeypatch):
    monkeypatch.setattr(http_module, 'monotonic', lambda: 5.0)
    opener = Mock()
    with pytest.raises(TimeoutError, match='deadline'):
        BinancePublicHttpClient(opener=opener).get_json('https://example.test', deadline=5)
    opener.assert_not_called()


def test_success_after_deadline_is_rejected(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(http_module, 'monotonic', lambda: now[0])
    def late(*args, **kwargs):
        now[0] = 3.0
        return _Response(b'[]')
    opener = Mock(side_effect=late)
    with pytest.raises(TimeoutError, match='arrived after'):
        BinancePublicHttpClient(opener=opener).get_json('https://example.test', deadline=2)
    opener.assert_called_once()


@pytest.mark.parametrize('module_name,class_name', [
    ('platform_v2.spot.services.market.binance_orderbook_service', 'BinanceOrderbookService'),
    ('platform_v2.futures.services.market.binance_futures_orderflow_service', 'BinanceFuturesOrderflowService'),
])
@pytest.mark.parametrize('failure', ['recover', 'exhausted', 'late', 'budget'])
def test_orderflow_page_retry_preserves_cursor_budget_and_atomic_publication(monkeypatch, module_name, class_name, failure):
    module = importlib.import_module(module_name)
    now = [0.0]; waits = []; urls = []
    monkeypatch.setattr(http_module, 'monotonic', lambda: now[0])
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda: now[0]))
    def sleep(delay):
        waits.append(delay); now[0] += delay
    monkeypatch.setattr(module, 'BinancePublicHttpClient',
        lambda **kwargs: BinancePublicHttpClient(sleeper=sleep, **kwargs))
    def trade(ident, stamp):
        return {'a': ident, 'T': stamp, 'q': '1', 'm': False}
    calls = [0]
    def open_page(request, *, timeout):
        urls.append(request.full_url); calls[0] += 1
        assert timeout <= min(15, 120 - now[0])
        if calls[0] == 1:
            if failure == 'budget':
                now[0] = 119.5  # The next page must not get a fresh 120s budget.
            return _Response(json.dumps([trade(1, 100), trade(2, 100)]).encode())
        if failure == 'budget':
            assert timeout == 0.5
            now[0] = 120
            raise TimeoutError('shared collection budget exhausted')
        if failure == 'late':
            now[0] = 121
        elif failure == 'exhausted' or calls[0] == 2:
            raise TimeoutError('temporary outage')
        return _Response(json.dumps([trade(3, 200)]).encode())
    monkeypatch.setattr(module, 'urlopen', open_page)
    write = Mock(); monkeypatch.setattr(module, 'replace_market_series', write)
    monkeypatch.setattr(module, 'read_market_series_safely', lambda **kwargs: [])
    instance = getattr(module, class_name)()
    if failure != 'recover':
        with pytest.raises(TimeoutError):
            instance.fetch_and_store(symbol='BTCUSDT', timeframe='15m', close_time_ms=899999, limit=2)
        write.assert_not_called()
        assert calls[0] == (4 if failure == 'exhausted' else 2)
    else:
        instance.fetch_and_store(symbol='BTCUSDT', timeframe='15m', close_time_ms=899999, limit=2)
        assert calls[0] == 3 and waits == [1.0]
        write.assert_called_once()
        row = write.call_args.kwargs['rows'][0]
        assert row['period_count'] == 3 and row['buyers'] == 3.0
        assert row['page_count'] == 2  # Retries are not extra pages.
        assert row['completeness'] == 'COMPLETE_CLOSED_WINDOW_V1'
    assert len(set(urls[1:])) == 1 and 'fromId=3' in urls[1]
