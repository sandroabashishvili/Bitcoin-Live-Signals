"""Build MarketContext for Futures runtime data using V2 indicator logic."""

from __future__ import annotations

from typing import Any

from platform_v2.futures.config import settings
from platform_v2.shared.backend.market.candle import Candle
from platform_v2.futures.domain.models.indicator_snapshot import IndicatorSnapshot
from platform_v2.futures.domain.models.market_context import MarketContext
from platform_v2.futures.infrastructure.market_data import JsonCandleRepository, JsonOrderbookSnapshotRepository
from platform_v2.futures.services.analytics.indicator_pipeline import IndicatorSnapshotBuilder

from .futures_mtf_context_service import MultiTimeframeContextService


class FuturesMarketContextService:
    """Assemble a V2-compatible market context from Futures runtime data."""

    def __init__(self) -> None:
        self._snapshot_builder = IndicatorSnapshotBuilder()
        self._mtf_service = MultiTimeframeContextService()
        self._candle_repository = JsonCandleRepository()
        self._orderbook_repository = JsonOrderbookSnapshotRepository()

    def build_context(
        self,
        *,
        symbol: str,
        timeframe: str,
        candle_limit: int = settings.DEFAULT_CANDLE_LIMIT,
    ) -> MarketContext | None:
        timeframe_snapshots: dict[str, IndicatorSnapshot | None] = {}
        primary_candles: list[Candle] = []

        for tf in settings.DEFAULT_CANDLE_TIMEFRAMES:
            candles = self._candle_repository.get_closed_candles(
                symbol=symbol,
                timeframe=tf,
                limit=max(candle_limit, 240),
            )
            if tf == timeframe:
                primary_candles = candles[-candle_limit:] if candle_limit > 0 else candles
            if len(candles) < 35:
                timeframe_snapshots[tf] = None
                continue
            snapshot = self._build_latest_snapshot(symbol=symbol, timeframe=tf, candles=candles)
            timeframe_snapshots[tf] = snapshot

        latest_snapshot = timeframe_snapshots.get(timeframe)
        if latest_snapshot is None or not primary_candles:
            return None

        latest_orderbook = self._orderbook_repository.get_latest_snapshot(symbol=symbol, timeframe=timeframe)
        mtf_signals, mtf_direction = self._mtf_service.build_signals(
            timeframe_snapshots=timeframe_snapshots,
            primary_timeframe=timeframe,
        )

        return MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            latest_snapshot=latest_snapshot,
            latest_orderbook=latest_orderbook,
            recent_candles=tuple(primary_candles),
            mtf_signals=mtf_signals,
            mtf_direction=mtf_direction,
        )

    def _build_latest_snapshot(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[Candle],
    ) -> IndicatorSnapshot | None:
        rows = self._snapshot_builder.build_rows(symbol=symbol, timeframe=timeframe, candles=candles)
        if not rows:
            return None
        return self._snapshot_from_row(symbol=symbol, timeframe=timeframe, row=rows[-1])

    @staticmethod
    def _snapshot_from_row(
        *,
        symbol: str,
        timeframe: str,
        row: dict[str, Any],
    ) -> IndicatorSnapshot:
        promoted = {
            "symbol",
            "timeframe",
            "datetime",
            "price",
            "volume",
            "rsi",
            "macd",
            "macd_signal",
            "macd_trend",
            "ema50",
            "ema200",
            "ema50_slope",
            "vwap",
            "vwap_signal",
            "adx",
            "atr",
            "atr_spike",
            "tenkan",
            "kijun",
            "ichimoku_signal",
            "plus_di",
            "minus_di",
            "adx_slope",
            "atr_growth_20",
            "atr_spike_threshold",
            "swing_low",
            "swing_high",
            "resistance_level",
            "liquidity_zone",
            "liquidity_tolerance",
            "bounce_confirmed",
            "avg_volume_10",
        }
        extras = {
            key: value
            for key, value in row.items()
            if key not in promoted and value is not None
        }
        return IndicatorSnapshot(
            symbol=str(row.get("symbol") or symbol),
            timeframe=str(row.get("timeframe") or timeframe),
            timestamp_text=str(row.get("datetime") or ""),
            price=float(row.get("price", 0.0) or 0.0),
            volume=FuturesMarketContextService._as_float(row.get("volume")),
            rsi=FuturesMarketContextService._as_float(row.get("rsi")),
            macd=FuturesMarketContextService._as_float(row.get("macd")),
            macd_signal=FuturesMarketContextService._as_float(row.get("macd_signal")),
            macd_trend=FuturesMarketContextService._as_str(row.get("macd_trend")),
            ema50=FuturesMarketContextService._as_float(row.get("ema50")),
            ema200=FuturesMarketContextService._as_float(row.get("ema200")),
            ema50_slope=FuturesMarketContextService._as_float(row.get("ema50_slope")),
            vwap=FuturesMarketContextService._as_float(row.get("vwap")),
            vwap_signal=FuturesMarketContextService._as_str(row.get("vwap_signal")),
            adx=FuturesMarketContextService._as_float(row.get("adx")),
            atr=FuturesMarketContextService._as_float(row.get("atr")),
            atr_spike=FuturesMarketContextService._as_bool(row.get("atr_spike")),
            tenkan=FuturesMarketContextService._as_float(row.get("tenkan")),
            kijun=FuturesMarketContextService._as_float(row.get("kijun")),
            ichimoku_signal=FuturesMarketContextService._as_str(row.get("ichimoku_signal")),
            plus_di=FuturesMarketContextService._as_float(row.get("plus_di")),
            minus_di=FuturesMarketContextService._as_float(row.get("minus_di")),
            adx_slope=FuturesMarketContextService._as_float(row.get("adx_slope")),
            atr_growth_20=FuturesMarketContextService._as_float(row.get("atr_growth_20")),
            atr_spike_threshold=FuturesMarketContextService._as_float(row.get("atr_spike_threshold")),
            swing_low=FuturesMarketContextService._as_float(row.get("swing_low")),
            swing_high=FuturesMarketContextService._as_float(row.get("swing_high")),
            resistance_level=FuturesMarketContextService._as_float(row.get("resistance_level")),
            liquidity_zone=FuturesMarketContextService._as_float(row.get("liquidity_zone")),
            liquidity_tolerance=FuturesMarketContextService._as_float(row.get("liquidity_tolerance")),
            bounce_confirmed=FuturesMarketContextService._as_bool(row.get("bounce_confirmed")),
            avg_volume_10=FuturesMarketContextService._as_float(row.get("avg_volume_10")),
            extras=extras,
        )

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
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
    def _as_str(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _as_bool(value: Any) -> bool | None:
        if value is None:
            return None
        return bool(value)
