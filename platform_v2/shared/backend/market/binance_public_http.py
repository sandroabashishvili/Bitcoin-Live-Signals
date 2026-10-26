"""Small resilient HTTP reader for Binance public market-data endpoints."""

from __future__ import annotations

import json
import math
from email.message import Message
from time import monotonic, sleep
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

    def get_json(self, url: str, *, deadline: float | None = None) -> Any:
        """Retry one GET, optionally within a shared monotonic collection budget.

        Socket timeouts bound blocking operations, not an entire response. Reject
        late responses too, so an expired collection is never published.
        """
        from platform_v2.shared.backend.research_evidence.runtime import observe_acquisition
        if deadline is not None and not math.isfinite(deadline):
            raise ValueError("Invalid market-data deadline")
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            timeout = self._timeout_seconds
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError("Market-data collection deadline exceeded") from last_error
                timeout = min(timeout, remaining)
            try:
                request = Request(url, headers={"User-Agent": "SmartSignalHub/1.0"})
                def fetch():
                    with self._opener(request, timeout=timeout) as response:
                        return json.loads(response.read().decode("utf-8"))
                payload = observe_acquisition(url, fetch)
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code in {418, 429} or 500 <= exc.code < 600
                if not retryable or attempt + 1 >= self._max_attempts:
                    raise
                delay = self._retry_delay(exc.headers, attempt)
            except (URLError, OSError, ValueError) as exc:
                last_error = exc
                if attempt + 1 >= self._max_attempts:
                    raise
                delay = min(4.0, float(2**attempt))
            else:
                if deadline is not None and monotonic() >= deadline:
                    raise TimeoutError("Market-data response arrived after collection deadline")
                return payload
            if deadline is not None and delay >= deadline - monotonic():
                raise TimeoutError("Insufficient collection time for safe retry") from last_error
            self._sleeper(delay)
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
        # Never shorten Binance's mandatory Retry-After (including long IP bans).
        return max(requested, float(2**attempt))
