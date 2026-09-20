"""Fetch an execution-time Binance quote for Spot or USD-M Futures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, ContextManager, Protocol
from urllib.parse import urlencode
from urllib.request import urlopen

from platform_v2.shared.backend.time import utc_now_ms


class _ReadableResponse(Protocol):
    def read(self) -> bytes: ...


QuoteOpener = Callable[..., ContextManager[_ReadableResponse]]


@dataclass(frozen=True)
class MarketQuote:
    """One quote observed immediately before a simulated entry decision."""

    symbol: str
    market_type: str
    price: float
    observed_at_ms: int
    source: str = "binance_ticker_price"


class BinanceQuoteService:
    """Read the latest ticker price without mixing it with candle-close data."""

    _URLS = {
        "spot": "https://api.binance.com/api/v3/ticker/price",
        "futures": "https://fapi.binance.com/fapi/v1/ticker/price",
    }

    def __init__(self, *, opener: QuoteOpener = urlopen, timeout_seconds: float = 10.0) -> None:
        self._opener = opener
        self._timeout_seconds = float(timeout_seconds)

    def fetch(self, *, symbol: str, market_type: str) -> MarketQuote:
        """Return a positive quote or raise so an entry cannot use a stale fallback."""

        normalized_market = str(market_type).strip().lower()
        base_url = self._URLS.get(normalized_market)
        if base_url is None:
            raise ValueError(f"Unsupported Binance market_type: {market_type!r}")

        query = urlencode({"symbol": str(symbol).strip().upper()})
        with self._opener(f"{base_url}?{query}", timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Binance ticker response must be an object")
        try:
            price = float(payload.get("price") or 0.0)
        except (TypeError, ValueError) as exc:
            raise ValueError("Binance ticker response has no valid price") from exc
        if price <= 0:
            raise ValueError("Binance ticker response has no positive price")

        return MarketQuote(
            symbol=str(payload.get("symbol") or symbol).upper(),
            market_type=normalized_market,
            price=price,
            observed_at_ms=utc_now_ms(),
        )
