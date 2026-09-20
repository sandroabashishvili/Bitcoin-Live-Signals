"""File: snapshot_builder.py
Folder: platform_v2/futures/services/analytics/indicator_pipeline
Created date: 2026-04-19
Last updated date: 2026-05-14
Author: Codex
Purpose: Build normalized Futures indicator snapshot rows from closed candles.
"""

from __future__ import annotations

from typing import TypedDict

from platform_v2.futures.config import settings
from platform_v2.shared.backend.market.candle import Candle
from platform_v2.shared.backend.market.indicator_series import (
    adx_series,
    adx_slope,
    atr_growth_20,
    atr_series,
    atr_spike,
    atr_spike_threshold,
    ema_series,
    ema_slope,
    macd_histogram,
    macd_series,
    macd_trend,
    rsi_series,
)
from .structure_math import (
    SnapshotFormat,
    StructureMath,
)


class IndicatorSeries(TypedDict):
    closes: list[float]
    highs: list[float]
    lows: list[float]
    volumes: list[float]
    ema9_series: list[float | None]
    ema50_series: list[float | None]
    ema200_series: list[float | None]
    rsi_series: list[float | None]
    atr_series: list[float | None]
    macd_line: list[float | None]
    macd_signal: list[float | None]
    adx_series: list[float | None]
    plus_di_series: list[float | None]
    minus_di_series: list[float | None]


class IndicatorFeatures(TypedDict):
    ema9: float | None
    ema50: float | None
    ema200: float | None
    rsi: float | None
    atr: float | None
    macd: float | None
    macd_sig: float | None
    adx: float | None
    plus_di: float | None
    minus_di: float | None
    tenkan: float | None
    kijun: float | None
    vwap: float | None
    prev_atr: float | None
    prev_adx: float | None
    atr_spike_threshold: float | None
    swing_low: float | None
    swing_high: float | None
    avg_volume_10: float | None
    resistance_level: float | None
    liquidity_zone: float | None
    liquidity_tolerance: float
    bounce_confirmed: bool
    ema50_slope: float | None
    macd_histogram: list[float] | None
    macd_trend: str | None
    vwap_signal: str | None
    atr_spike: bool | None
    ichimoku_signal: str | None
    adx_slope: float | None
    atr_growth_20: float | None


class IndicatorSnapshotBuilder:
    """Assemble normalized indicator snapshot rows from candle history."""

    def build_rows(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[Candle],
    ) -> list[dict[str, object]]:
        series = self._prepare_series(candles)
        snapshots: list[dict[str, object]] = []
        for index, candle in enumerate(candles):
            if index < 34:
                continue
            features = self._snapshot_features(candles=candles, series=series, index=index)
            snapshots.append(
                self._build_snapshot_row(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle=candle,
                    features=features,
                )
            )
        return snapshots

    def _prepare_series(self, candles: list[Candle]) -> IndicatorSeries:
        closes = [candle.close_price for candle in candles]
        highs = [candle.high_price for candle in candles]
        lows = [candle.low_price for candle in candles]
        volumes = [candle.volume for candle in candles]
        macd_line, macd_signal = macd_series(closes)
        adx_values, plus_di_series, minus_di_series = adx_series(highs, lows, closes, 14)
        return {
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "ema9_series": ema_series(closes, 9),
            "ema50_series": ema_series(closes, 50),
            "ema200_series": ema_series(closes, 200),
            "rsi_series": rsi_series(closes, 14),
            "atr_series": atr_series(highs, lows, closes, 14),
            "macd_line": macd_line,
            "macd_signal": macd_signal,
            "adx_series": adx_values,
            "plus_di_series": plus_di_series,
            "minus_di_series": minus_di_series,
        }

    def _snapshot_features(
        self,
        *,
        candles: list[Candle],
        series: IndicatorSeries,
        index: int,
    ) -> IndicatorFeatures:
        values = self._extract_series_values(series=series, index=index)
        refs = self._build_structure_refs(candles=candles, series=series, index=index, atr=values["atr"])
        merged: IndicatorFeatures = values.copy()
        for key, value in refs.items():
            if key not in merged or value is not None:
                merged[key] = value

        return {
            **merged,
            "vwap_signal": StructureMath.vwap_signal(candles[index].close_price, merged["vwap"]),
            "atr_spike": atr_spike(values["atr"], values["prev_atr"]),
            "ichimoku_signal": StructureMath.ichimoku_signal(
                candles[index].close_price,
                merged["tenkan"],
                merged["kijun"],
            ),
            "adx_slope": adx_slope(values["adx"], values["prev_adx"]),
            "atr_growth_20": atr_growth_20(series["atr_series"], index),
        }

    @staticmethod
    def _extract_series_values(*, series: IndicatorSeries, index: int) -> IndicatorFeatures:
        atr = series["atr_series"][index]
        prev_atr = series["atr_series"][index - 1] if index > 0 else None
        adx = series["adx_series"][index]
        prev_adx = series["adx_series"][index - 1] if index > 0 else None
        return {
            "ema9": series["ema9_series"][index],
            "ema50": series["ema50_series"][index],
            "ema200": series["ema200_series"][index],
            "rsi": series["rsi_series"][index],
            "atr": atr,
            "macd": series["macd_line"][index],
            "macd_sig": series["macd_signal"][index],
            "adx": adx,
            "plus_di": series["plus_di_series"][index],
            "minus_di": series["minus_di_series"][index],
            "prev_atr": prev_atr,
            "prev_adx": prev_adx,
            "atr_spike_threshold": atr_spike_threshold(
                series["atr_series"],
                index,
                settings.ATR_SPIKE_MULTIPLIER,
            ),
            "ema50_slope": ema_slope(series["ema50_series"], index),
            "macd_histogram": macd_histogram(series["macd_line"], series["macd_signal"], index),
            "macd_trend": macd_trend(series["macd_line"][index], series["macd_signal"][index]),
            "adx_slope": None,
            "atr_growth_20": None,
            "tenkan": None,
            "kijun": None,
            "vwap": None,
            "swing_low": None,
            "swing_high": None,
            "avg_volume_10": None,
            "resistance_level": None,
            "liquidity_zone": None,
            "liquidity_tolerance": 0.0,
            "bounce_confirmed": False,
            "vwap_signal": None,
            "atr_spike": None,
            "ichimoku_signal": None,
        }

    def _build_structure_refs(
        self,
        *,
        candles: list[Candle],
        series: IndicatorSeries,
        index: int,
        atr: float | None,
    ) -> IndicatorFeatures:
        closes = series["closes"]
        highs = series["highs"]
        lows = series["lows"]
        volumes = series["volumes"]
        avg_volume_10 = StructureMath.rolling_average(volumes, index, 10)
        swing_low = StructureMath.rolling_min(lows, index, settings.SWING_LOOKBACK)
        resistance_value = StructureMath.resistance_level(
            highs=highs,
            closes=closes,
            index=index,
            lookback=settings.RESISTANCE_LOOKBACK,
        )
        tenkan = StructureMath.rolling_midpoint(highs, lows, index, 9)
        kijun = StructureMath.rolling_midpoint(highs, lows, index, 26)
        vwap = StructureMath.rolling_vwap(closes, volumes, index, 20)
        return {
            "tenkan": tenkan,
            "kijun": kijun,
            "vwap": vwap,
            "swing_low": swing_low,
            "swing_high": StructureMath.rolling_max(highs, index, settings.SWING_LOOKBACK),
            "avg_volume_10": avg_volume_10,
            "resistance_level": resistance_value,
            "liquidity_zone": StructureMath.liquidity_zone(
                highs=highs,
                closes=closes,
                volumes=volumes,
                index=index,
                avg_volume_10=avg_volume_10,
                resistance_level_value=resistance_value,
                lookback=settings.LIQUIDITY_LOOKBACK,
            ),
            "liquidity_tolerance": StructureMath.liquidity_tolerance(
                price=candles[index].close_price,
                atr=atr,
            ),
            "bounce_confirmed": StructureMath.bounce_confirmed(
                candles=candles,
                lows=lows,
                closes=closes,
                index=index,
                swing_low=swing_low,
            ),
            "ema50": None,
            "ema9": None,
            "ema200": None,
            "rsi": None,
            "atr": None,
            "macd": None,
            "macd_sig": None,
            "adx": None,
            "plus_di": None,
            "minus_di": None,
            "prev_atr": None,
            "prev_adx": None,
            "atr_spike_threshold": None,
            "ema50_slope": None,
            # Structure references do not own this series-derived feature.
            # None preserves the real three-point histogram during the merge.
            "macd_histogram": None,
            "macd_trend": None,
            "vwap_signal": None,
            "atr_spike": None,
            "ichimoku_signal": None,
            "adx_slope": None,
            "atr_growth_20": None,
        }

    def _build_snapshot_row(
        self,
        *,
        symbol: str,
        timeframe: str,
        candle: Candle,
        features: IndicatorFeatures,
    ) -> dict[str, object]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp_ms": candle.close_time_ms,
            "open_time_ms": candle.open_time_ms,
            "close_time_ms": candle.close_time_ms,
            "date": SnapshotFormat.ms_to_date(candle.close_time_ms),
            "datetime": SnapshotFormat.ms_to_datetime(candle.close_time_ms),
            "price": candle.close_price,
            "volume": candle.volume,
            "rsi": SnapshotFormat.round_or_none(features["rsi"]),
            "macd": SnapshotFormat.round_or_none(features["macd"]),
            "macd_signal": SnapshotFormat.round_or_none(features["macd_sig"]),
            "macd_trend": features["macd_trend"],
            "macd_histogram": features["macd_histogram"] or [],
            "ema50": SnapshotFormat.round_or_none(features["ema50"]),
            "ema9": SnapshotFormat.round_or_none(features["ema9"]),
            "ema200": SnapshotFormat.round_or_none(features["ema200"]),
            "ema50_slope": features["ema50_slope"],
            "vwap": SnapshotFormat.round_or_none(features["vwap"]),
            "vwap_signal": features["vwap_signal"],
            "adx": SnapshotFormat.round_or_none(features["adx"]),
            "atr": SnapshotFormat.round_or_none(features["atr"]),
            "atr_spike": features["atr_spike"],
            "tenkan": SnapshotFormat.round_or_none(features["tenkan"]),
            "kijun": SnapshotFormat.round_or_none(features["kijun"]),
            "ichimoku_signal": features["ichimoku_signal"],
            "prev_adx": SnapshotFormat.round_or_none(features["prev_adx"]),
            "plus_di": SnapshotFormat.round_or_none(features["plus_di"]),
            "minus_di": SnapshotFormat.round_or_none(features["minus_di"]),
            "adx_slope": features["adx_slope"],
            "atr_growth_20": features["atr_growth_20"],
            "atr_spike_threshold": SnapshotFormat.round_or_none(features["atr_spike_threshold"]),
            "swing_low": SnapshotFormat.round_or_none(features["swing_low"]),
            "swing_high": SnapshotFormat.round_or_none(features["swing_high"]),
            "resistance_level": SnapshotFormat.round_or_none(features["resistance_level"]),
            "liquidity_zone": SnapshotFormat.round_or_none(features["liquidity_zone"]),
            "liquidity_tolerance": SnapshotFormat.round_or_none(features["liquidity_tolerance"]),
            "bounce_confirmed": features["bounce_confirmed"],
            "avg_volume_10": SnapshotFormat.round_or_none(features["avg_volume_10"]),
        }
