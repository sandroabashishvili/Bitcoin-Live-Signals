"""File: binance_candle_fetch_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Fetch closed candle data from Binance and persist it into V2 candle storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from platform_v2.shared.backend.market import BinancePublicHttpClient
from platform_v2.spot.config import settings
from platform_v2.spot.storage.paths import candle_file_path
from platform_v2.shared.backend.persistence import read_market_series_safely, replace_market_series
from platform_v2.shared.backend.time import utc_now_ms


class BinanceCandleFetchService:
    """Fetch Binance klines and store only closed candles in V2 storage."""

    BASE_URL = "https://api.binance.com/api/v3/klines"

    def __init__(self, *, http_client: BinancePublicHttpClient | None = None) -> None:
        self._http_client = http_client or BinancePublicHttpClient()

    def fetch_and_store(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int = settings.DEFAULT_FETCH_LIMIT,
    ) -> Path | None:
        """Fetch Binance klines, keep closed candles only, and persist them."""

        raw_klines = self._request_klines(symbol=symbol, timeframe=timeframe, limit=limit)
        normalized_rows = self._normalize_klines(symbol=symbol, timeframe=timeframe, raw_klines=raw_klines)
        if not normalized_rows:
            return None

        target_path = candle_file_path(symbol, timeframe)
        existing_rows = read_market_series_safely(
            venue="binance", asset_class="crypto", market_type="spot",
            dataset="candles", symbol=symbol, timeframe=timeframe,
        )
        merged_rows = self._merge_rows(existing_rows, normalized_rows)

        replace_market_series(
            venue="binance",
            asset_class="crypto",
            market_type="spot",
            dataset="candles",
            symbol=symbol,
            timeframe=timeframe,
            rows=merged_rows,
            source_path=target_path,
        )
        return target_path

    def fetch_many(
        self,
        *,
        symbol: str,
        timeframes: tuple[str, ...] | list[str],
        limit: int = settings.DEFAULT_FETCH_LIMIT,
    ) -> list[Path]:
        """Fetch and store multiple Binance candle files for one symbol."""

        written_paths: list[Path] = []
        for timeframe in timeframes:
            target_path = self.fetch_and_store(symbol=symbol, timeframe=timeframe, limit=limit)
            if target_path is not None:
                written_paths.append(target_path)
        return written_paths

    def _request_klines(self, *, symbol: str, timeframe: str, limit: int) -> list[list[object]]:
        """Request raw klines from Binance."""

        query = urlencode({"symbol": symbol, "interval": timeframe, "limit": limit})
        url = f"{self.BASE_URL}?{query}"
        payload = self._http_client.get_json(url)
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
        """Normalize Binance raw klines into our candle storage shape."""

        cutoff_ms = utc_now_ms()
        rows: list[dict[str, object]] = []

        for kline in raw_klines:
            if len(kline) < 7:
                continue

            open_time_ms = self._int_from_kline(kline, 0)
            close_time_ms = self._int_from_kline(kline, 6)
            if open_time_ms is None or close_time_ms is None:
                continue
            if close_time_ms > cutoff_ms:
                continue

            open_price = self._float_from_kline(kline, 1)
            high_price = self._float_from_kline(kline, 2)
            low_price = self._float_from_kline(kline, 3)
            close_price = self._float_from_kline(kline, 4)
            volume = self._float_from_kline(kline, 5)
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
                }
            )

        return rows

    @staticmethod
    def _int_from_kline(kline: list[object], index: int) -> int | None:
        value = BinanceCandleFetchService._coerce_int(kline[index])
        return value if value > 0 else None

    @staticmethod
    def _float_from_kline(kline: list[object], index: int) -> float | None:
        value = kline[index]
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
    def _merge_rows(
        existing_rows: list[dict[str, object]],
        new_rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Merge candle rows by open timestamp, keeping the latest version."""

        merged: dict[int, dict[str, object]] = {}
        for row in existing_rows + new_rows:
            timestamp = BinanceCandleFetchService._coerce_int(row.get("timestamp"))
            if timestamp <= 0:
                continue
            merged[timestamp] = row

        return [merged[key] for key in sorted(merged)]

    @staticmethod
    def _ms_to_text(timestamp_ms: int) -> str:
        """Convert milliseconds into the stored UTC text format."""

        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%SZ"
        )
