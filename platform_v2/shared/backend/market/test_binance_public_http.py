from __future__ import annotations

from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

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
