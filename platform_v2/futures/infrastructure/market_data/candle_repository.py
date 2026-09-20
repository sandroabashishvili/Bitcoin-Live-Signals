"""Read futures candle data from storage and expose normalized models."""

from __future__ import annotations

from typing import Protocol

from platform_v2.shared.backend.market.candle import Candle
from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.shared.backend.time import utc_now_ms
from platform_v2.futures.storage import candle_file_path, load_json_list


class CandleRepository(Protocol):
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
        closed_only: bool = True,
    ) -> list[Candle]: ...

    def get_closed_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> list[Candle]: ...


class JsonCandleRepository:
    def __init__(self) -> None:
        pass

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
        closed_only: bool = True,
    ) -> list[Candle]:
        source_path = candle_file_path(symbol, timeframe)
        raw_rows = read_market_series_safely(
            venue="binance",
            asset_class="crypto",
            market_type="futures",
            dataset="candles",
            symbol=symbol,
            timeframe=timeframe,
        ) or load_json_list(source_path)

        cutoff_ms = utc_now_ms()
        candles: list[Candle] = []
        for row in raw_rows:
            candle = self._parse_candle_row(symbol=symbol, timeframe=timeframe, row=row)
            if candle is None:
                continue
            if closed_only and candle.close_time_ms > cutoff_ms:
                continue
            candles.append(candle)

        if limit is not None and limit > 0:
            return candles[-limit:]
        return candles

    def get_closed_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> list[Candle]:
        return self.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            closed_only=True,
        )

    @staticmethod
    def _parse_candle_row(symbol: str, timeframe: str, row: object) -> Candle | None:
        if not isinstance(row, dict):
            return None
        try:
            return Candle(
                symbol=symbol,
                timeframe=timeframe,
                open_time_ms=int(row.get("timestamp", 0) or 0),
                close_time_ms=int(row.get("close_time", 0) or 0),
                open_price=float(row.get("open", 0.0) or 0.0),
                high_price=float(row.get("high", 0.0) or 0.0),
                low_price=float(row.get("low", 0.0) or 0.0),
                close_price=float(row.get("close", 0.0) or 0.0),
                volume=float(row.get("volume", 0.0) or 0.0),
            )
        except (TypeError, ValueError):
            return None
