from __future__ import annotations

from pathlib import Path

from platform_v2.futures.config import ExecutionProfile
from platform_v2.futures.config import settings
from platform_v2.futures.infrastructure.market_data import JsonCandleRepository
from platform_v2.futures.services.analytics import FuturesIndicatorBuilderService
from platform_v2.futures.services.market import BinanceFuturesCandleFetchService
from platform_v2.futures.storage import candle_file_path

from .models import CycleInputs, CycleKeyInfo


class MainCycleInputService:
    """Prepare fetched futures inputs and stable cycle keys."""

    def __init__(
        self,
        candle_fetch_service: BinanceFuturesCandleFetchService | None = None,
        candle_repository: JsonCandleRepository | None = None,
        indicator_builder_service: FuturesIndicatorBuilderService | None = None,
    ) -> None:
        self._candle_fetch_service = candle_fetch_service or BinanceFuturesCandleFetchService()
        self._candle_repository = candle_repository or JsonCandleRepository()
        self._indicator_builder_service = indicator_builder_service or FuturesIndicatorBuilderService(
            candle_repository=self._candle_repository,
        )

    def prepare_cycle_inputs(
        self,
        *,
        profile: ExecutionProfile,
        fetch_limit: int = 500,
    ) -> CycleInputs:
        fetched_candle_paths = tuple(
            self._candle_fetch_service.fetch_many(
                symbol=profile.symbol,
                timeframes=settings.DEFAULT_FETCH_TIMEFRAMES,
                limit=fetch_limit,
            )
        )
        self._indicator_builder_service.build_many(
            symbol=profile.symbol,
            timeframes=("5m", profile.timeframe, "4h"),
        )
        cycle_info = self._build_cycle_key(
            fetched_candle_paths,
            symbol=profile.symbol,
            timeframe=profile.timeframe,
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
        expected_path = candle_file_path(symbol, timeframe)
        target_path = next((path for path in fetched_candle_paths if path == expected_path), None)
        if target_path is None:
            return CycleKeyInfo(
                key=f"{symbol}:{timeframe}:missing",
                state="missing_primary_candle_file",
                note=f"{expected_path.name} was not fetched",
            )
        candles = self._candle_repository.get_closed_candles(symbol=symbol, timeframe=timeframe, limit=1)
        if not candles:
            return CycleKeyInfo(
                key=f"{symbol}:{timeframe}:empty",
                state="empty_primary_candle_payload",
                note="market-data database has no primary candle rows",
            )
        close_time = candles[-1].close_time_ms
        return CycleKeyInfo(
            key=f"{symbol}:{timeframe}:{close_time}",
            state="ready",
            note=str(close_time),
        )
