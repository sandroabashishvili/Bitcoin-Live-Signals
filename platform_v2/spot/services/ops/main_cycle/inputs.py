from __future__ import annotations

from pathlib import Path

from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.spot.config import settings
from platform_v2.spot.services.market.binance_candle_fetch_service import BinanceCandleFetchService

from .models import CycleInputs, CycleKeyInfo


class MainCycleInputService:
    """Prepare fetched runtime inputs and stable cycle keys."""

    def __init__(
        self,
        candle_fetch_service: BinanceCandleFetchService | None = None,
    ) -> None:
        self._candle_fetch_service = candle_fetch_service or BinanceCandleFetchService()

    def prepare_cycle_inputs(
        self,
        *,
        symbol: str,
        timeframe: str,
        fetch_limit: int = settings.DEFAULT_FETCH_LIMIT,
    ) -> CycleInputs:
        fetched_candle_paths = tuple(
            self._candle_fetch_service.fetch_many(
                symbol=symbol,
                timeframes=settings.DEFAULT_FETCH_TIMEFRAMES,
                limit=fetch_limit,
            )
        )
        cycle_info = self._build_cycle_key(
            fetched_candle_paths,
            symbol=symbol,
            timeframe=timeframe,
        )
        return CycleInputs(
            fetched_candle_paths=fetched_candle_paths,
            cycle_info=cycle_info,
        )

    def _build_cycle_key(
        self,
        fetched_candle_paths: tuple[Path, ...],
        *,
        symbol: str,
        timeframe: str,
    ) -> CycleKeyInfo:
        target_path = next(
            (path for path in fetched_candle_paths if path.name == f"{timeframe}.json"),
            None,
        )
        if target_path is None:
            return CycleKeyInfo(
                key=f"{symbol}:{timeframe}:missing",
                state="missing_primary_candle_file",
                note=f"{timeframe}.json was not fetched",
            )
        payload = read_market_series_safely(
            venue="binance",
            asset_class="crypto",
            market_type="spot",
            dataset="candles",
            symbol=symbol,
            timeframe=timeframe,
        )
        if not payload:
            return CycleKeyInfo(
                key=f"{symbol}:{timeframe}:empty",
                state="empty_primary_candle_payload",
                note="market-data database has no primary candle rows",
            )

        latest_row = payload[-1]
        close_time = latest_row.get("close_time")
        if close_time is None:
            return CycleKeyInfo(
                key=f"{symbol}:{timeframe}:missing_close_time",
                state="missing_primary_close_time",
                note="latest primary candle row has no close_time",
            )
        return CycleKeyInfo(
            key=f"{symbol}:{timeframe}:{close_time}",
            state="ready",
            note=str(close_time),
        )
