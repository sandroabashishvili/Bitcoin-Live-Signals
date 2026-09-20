"""Fetch closed candle data from Binance Futures and persist it."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from platform_v2.futures.storage import candle_file_path
from platform_v2.shared.backend.market import BinancePublicHttpClient
from platform_v2.shared.backend.persistence import read_market_series_safely, replace_market_series
from platform_v2.shared.backend.time import utc_now_ms
from platform_v2.shared.runtime_warnings import warn_runtime_fallback


class BinanceFuturesCandleFetchService:
    BASE_URL = "https://fapi.binance.com/fapi/v1/klines"

    def __init__(self, *, http_client: BinancePublicHttpClient | None = None) -> None:
        self._http_client = http_client or BinancePublicHttpClient()

    def fetch_and_store(self, *, symbol: str, timeframe: str, limit: int = 500) -> Path | None:
        raw_klines = self._request_klines(symbol=symbol, timeframe=timeframe, limit=limit)
        rows = self._normalize_klines(symbol=symbol, timeframe=timeframe, raw_klines=raw_klines)
        if not rows:
            return None

        target_path = candle_file_path(symbol, timeframe)
        existing = read_market_series_safely(
            venue="binance", asset_class="crypto", market_type="futures",
            dataset="candles", symbol=symbol, timeframe=timeframe,
        )
        merged = self._merge_rows(existing, rows)
        replace_market_series(
            venue="binance",
            asset_class="crypto",
            market_type="futures",
            dataset="candles",
            symbol=symbol,
            timeframe=timeframe,
            rows=merged,
            source_path=target_path,
        )
        return target_path

    def fetch_many(
        self,
        *,
        symbol: str,
        timeframes: tuple[str, ...] | list[str],
        limit: int = 500,
    ) -> list[Path]:
        written: list[Path] = []
        for timeframe in timeframes:
            path = self.fetch_and_store(symbol=symbol, timeframe=timeframe, limit=limit)
            if path is not None:
                written.append(path)
        return written

    def _request_klines(self, *, symbol: str, timeframe: str, limit: int) -> list[list[object]]:
        query = urlencode({"symbol": symbol, "interval": timeframe, "limit": limit})
        try:
            payload = self._http_client.get_json(f"{self.BASE_URL}?{query}")
        except (OSError, ValueError) as exc:
            warn_runtime_fallback(
                scope="binance_futures_candle_fetch_service",
                operation="request_klines",
                error=exc,
                fallback="return_empty_rows",
                extra={"symbol": symbol, "timeframe": timeframe, "limit": limit},
            )
            return []
        if not isinstance(payload, list):
            return []
        return [row for row in payload if isinstance(row, list)]

    def _normalize_klines(
        self,
        *,
        symbol: str,
        timeframe: str,
        raw_klines: list[list[object]],
    ) -> list[dict[str, object]]:
        cutoff_ms = utc_now_ms()
        rows: list[dict[str, object]] = []
        for kline in raw_klines:
            if len(kline) < 7:
                continue
            open_time_ms = self._coerce_int(kline[0])
            close_time_ms = self._coerce_int(kline[6])
            if open_time_ms <= 0 or close_time_ms <= 0 or close_time_ms > cutoff_ms:
                continue
            open_price = self._coerce_float(kline[1])
            high_price = self._coerce_float(kline[2])
            low_price = self._coerce_float(kline[3])
            close_price = self._coerce_float(kline[4])
            volume = self._coerce_float(kline[5])
            if None in (open_price, high_price, low_price, close_price, volume):
                continue
            rows.append(
                {
                    "timestamp": open_time_ms,
                    "time_readable": self._ms_to_text(open_time_ms),
                    "close_time": close_time_ms,
                    "close_time_readable": self._ms_to_text(close_time_ms),
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "market": "futures",
                }
            )
        return rows

    @classmethod
    def _merge_rows(
        cls,
        existing_rows: list[dict[str, object]],
        new_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        merged: dict[int, dict[str, object]] = {}
        for row in existing_rows + new_rows:
            ts = cls._coerce_int(row.get("timestamp"))
            if ts <= 0:
                continue
            merged[ts] = row
        return [merged[key] for key in sorted(merged)]

    @staticmethod
    def _coerce_int(value: object) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0

    @staticmethod
    def _coerce_float(value: object) -> float | None:
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _ms_to_text(timestamp_ms: int) -> str:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ")
