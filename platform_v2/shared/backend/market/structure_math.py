"""Shared structure, liquidity, and snapshot formatting helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from platform_v2.shared.backend.market.candle import Candle


class StructureMathBase:
    """Configurable calculations shared by Spot and Futures snapshots."""

    BOUNCE_LOOKBACK = 3
    LIQUIDITY_VOLUME_MULTIPLIER = 1.15
    LIQUIDITY_TOLERANCE_ATR_MULTIPLIER = 0.8

    @staticmethod
    def rolling_midpoint(highs: list[float], lows: list[float], index: int, period: int) -> float | None:
        if index + 1 < period:
            return None
        start = index + 1 - period
        return (max(highs[start : index + 1]) + min(lows[start : index + 1])) / 2.0

    @staticmethod
    def rolling_vwap(closes: list[float], volumes: list[float], index: int, period: int) -> float | None:
        if index + 1 < period:
            period = index + 1
        start = index + 1 - period
        price_volume = sum(closes[i] * volumes[i] for i in range(start, index + 1))
        volume_sum = sum(volumes[start : index + 1])
        if volume_sum == 0:
            return None
        return price_volume / volume_sum

    @staticmethod
    def rolling_min(values: list[float], index: int, period: int) -> float | None:
        if index < 0:
            return None
        window = values[max(0, index + 1 - max(1, period)) : index + 1]
        return min(window) if window else None

    @staticmethod
    def rolling_max(values: list[float], index: int, period: int) -> float | None:
        if index < 0:
            return None
        window = values[max(0, index + 1 - max(1, period)) : index + 1]
        return max(window) if window else None

    @staticmethod
    def rolling_average(values: list[float], index: int, period: int) -> float | None:
        if index < 0:
            return None
        window = values[max(0, index + 1 - max(1, period)) : index + 1]
        return sum(window) / len(window) if window else None

    @classmethod
    def bounce_confirmed(
        cls,
        *,
        candles: list[Candle],
        lows: list[float],
        closes: list[float],
        index: int,
        swing_low: float | None,
    ) -> bool:
        if swing_low is None or index < 1:
            return False
        tolerance = swing_low * 0.003
        start = max(0, index - cls.BOUNCE_LOOKBACK)
        if not any(abs(low - swing_low) <= tolerance for low in lows[start : index + 1]):
            return False
        current_close = closes[index]
        return (
            current_close > swing_low
            and current_close > candles[index].open_price
            and current_close >= closes[index - 1]
        )

    @staticmethod
    def resistance_level(
        *, highs: list[float], closes: list[float], index: int, lookback: int
    ) -> float | None:
        if index < 2:
            return None
        current_close = closes[index]
        start = max(1, index - lookback + 1)
        candidates = [
            highs[pivot]
            for pivot in range(start, index)
            if highs[pivot] >= highs[pivot - 1]
            and highs[pivot] >= (highs[pivot + 1] if pivot + 1 <= index else highs[pivot])
            and highs[pivot] > current_close
        ]
        if candidates:
            return min(candidates)
        overhead_highs = [high for high in highs[start : index + 1] if high > current_close]
        return min(overhead_highs) if overhead_highs else None

    @classmethod
    def liquidity_zone(
        cls,
        *,
        highs: list[float],
        closes: list[float],
        volumes: list[float],
        index: int,
        avg_volume_10: float | None,
        resistance_level_value: float | None,
        lookback: int,
    ) -> float | None:
        current_close = closes[index]
        start = max(0, index - lookback + 1)
        avg_volume = avg_volume_10 or 0.0
        volume_threshold = avg_volume * cls.LIQUIDITY_VOLUME_MULTIPLIER if avg_volume > 0 else 0.0
        weighted_sum = 0.0
        total_weight = 0.0
        cluster_candidates: list[float] = []
        for candle_index in range(start, index + 1):
            high = highs[candle_index]
            close = closes[candle_index]
            volume = volumes[candle_index]
            if high <= current_close or (volume_threshold > 0 and volume < volume_threshold):
                continue
            level = max(high, close)
            if resistance_level_value is not None and abs(level - resistance_level_value) > current_close * 0.01:
                continue
            weighted_sum += level * volume
            total_weight += volume
            cluster_candidates.append(level)
        if total_weight > 0:
            return weighted_sum / total_weight
        if cluster_candidates:
            return sum(cluster_candidates) / len(cluster_candidates)
        return resistance_level_value

    @classmethod
    def liquidity_tolerance(cls, *, price: float, atr: float | None) -> float:
        if atr is not None and atr > 0:
            return atr * cls.LIQUIDITY_TOLERANCE_ATR_MULTIPLIER
        return price * 0.0015

    @staticmethod
    def vwap_signal(price: float, vwap: float | None) -> str | None:
        if vwap is None:
            return None
        return "Above" if price >= vwap else "Below"

    @staticmethod
    def ichimoku_signal(price: float, tenkan: float | None, kijun: float | None) -> str | None:
        if tenkan is None or kijun is None:
            return None
        return "Bullish" if price >= tenkan and price >= kijun else "Bearish"


class SnapshotFormat:
    """Formatting helpers for snapshot serialization."""

    @staticmethod
    def round_or_none(value: float | None, digits: int = 5) -> float | None:
        return None if value is None else round(value, digits)

    @staticmethod
    def ms_to_datetime(timestamp_ms: int) -> str:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def ms_to_date(timestamp_ms: int) -> str:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
