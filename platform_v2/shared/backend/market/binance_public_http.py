"""Small resilient HTTP reader for Binance public market-data endpoints."""

from __future__ import annotations

import json
from email.message import Message
from time import sleep
from typing import Any, Callable, ContextManager, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class _Response(Protocol):
    headers: Message

    def read(self) -> bytes: ...


Opener = Callable[..., ContextManager[_Response]]


class BinancePublicHttpClient:
    """Read public JSON with bounded retry and mandatory 429/418 backoff."""

    def __init__(
        self,
        *,
        opener: Opener = urlopen,
        timeout_seconds: float = 15.0,
        max_attempts: int = 3,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._opener = opener
        self._timeout_seconds = float(timeout_seconds)
        self._max_attempts = max(1, int(max_attempts))
        self._sleeper = sleeper

    def get_json(self, url: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                request = Request(url, headers={"User-Agent": "SmartSignalHub/1.0"})
                with self._opener(request, timeout=self._timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code in {418, 429} or 500 <= exc.code < 600
                if not retryable or attempt + 1 >= self._max_attempts:
                    raise
                self._sleeper(self._retry_delay(exc.headers, attempt))
            except (URLError, OSError, ValueError) as exc:
                last_error = exc
                if attempt + 1 >= self._max_attempts:
                    raise
                self._sleeper(min(4.0, float(2**attempt)))
        if last_error is not None:
            raise last_error
        raise RuntimeError("Binance public request failed without an error")

    @staticmethod
    def _retry_delay(headers: Message | None, attempt: int) -> float:
        retry_after = headers.get("Retry-After") if headers is not None else None
        try:
            requested = float(retry_after) if retry_after is not None else 0.0
        except (TypeError, ValueError):
            requested = 0.0
        return min(60.0, max(requested, float(2**attempt)))
