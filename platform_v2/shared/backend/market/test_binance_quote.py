from __future__ import annotations

from contextlib import contextmanager

import pytest

from .binance_quote import BinanceQuoteService


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


def _opener(payload: bytes, captured: list[str]):
    @contextmanager
    def open_url(url: str, *, timeout: float):
        captured.append(f"{url}|{timeout}")
        yield _Response(payload)

    return open_url


@pytest.mark.parametrize(
    ("market_type", "expected_path"),
    (("spot", "/api/v3/ticker/price"), ("futures", "/fapi/v1/ticker/price")),
)
def test_fetch_uses_market_specific_endpoint(market_type: str, expected_path: str) -> None:
    captured: list[str] = []
    service = BinanceQuoteService(
        opener=_opener(b'{"symbol":"BTCUSDT","price":"64250.12"}', captured),
    )

    quote = service.fetch(symbol="btcusdt", market_type=market_type)

    assert quote.price == 64250.12
    assert quote.market_type == market_type
    assert quote.observed_at_ms > 0
    assert expected_path in captured[0]
    assert "symbol=BTCUSDT" in captured[0]


def test_fetch_rejects_non_positive_price() -> None:
    service = BinanceQuoteService(opener=_opener(b'{"price":"0"}', []))

    with pytest.raises(ValueError, match="positive price"):
        service.fetch(symbol="BTCUSDT", market_type="spot")
