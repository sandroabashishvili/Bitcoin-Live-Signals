"""File: futures_component_score_service.py
Folder: platform_v2/futures/services/signal
Created date: 2026-06-01
Last updated date: 2026-06-01
Author: Codex
Purpose: Score Futures signal components for LONG and SHORT decisions.
"""

from __future__ import annotations

from platform_v2.futures.config import settings
from platform_v2.futures.domain.models.market_context import MarketContext
from platform_v2.futures.services.signal.futures_structure_score_service import (
    FuturesStructureScoreService,
)


class FuturesComponentScoreService:
    """Build raw component scores for Futures LONG and SHORT directions."""

    def build_long_component_scores(self, context: MarketContext) -> dict[str, float]:
        snapshot = context.latest_snapshot
        orderbook = context.latest_orderbook
        atr_spike_block = self.atr_spike_block(snapshot)
        return {
            "mtf": self.direction_mtf_score(context, direction="LONG"),
            "regime": self.long_regime_score(snapshot, atr_spike_block=atr_spike_block),
            "trend": self.long_trend_score(snapshot, snapshot.price),
            "momentum": self.long_momentum_score(snapshot),
            "orderbook": self.long_orderbook_score(orderbook),
            "structure": self.long_structure_score(
                snapshot,
                snapshot.price,
                atr_spike_block,
            ),
        }

    def build_short_component_scores(self, context: MarketContext) -> dict[str, float]:
        snapshot = context.latest_snapshot
        orderbook = context.latest_orderbook
        atr_spike_block = self.atr_spike_block(snapshot)
        return {
            "mtf": self.direction_mtf_score(context, direction="SHORT"),
            "regime": self.regime_score(snapshot, atr_spike_block=atr_spike_block),
            "trend": self.short_trend_score(snapshot, snapshot.price),
            "momentum": self.short_momentum_score(snapshot),
            "orderbook": self.short_orderbook_score(orderbook),
            "structure": self.short_structure_score(
                snapshot,
                snapshot.price,
                atr_spike_block,
            ),
        }

    @staticmethod
    def direction_mtf_score(context: MarketContext, *, direction: str) -> float:
        direction_text = direction.upper()
        primary_matches = context.mtf_signals.get(context.timeframe) == direction_text
        fast_matches = context.mtf_signals.get("5m") == direction_text
        higher_matches = context.mtf_signals.get("4h") == direction_text
        score = 0.0
        if primary_matches:
            score += 2.0
        if fast_matches:
            score += 1.0
        if higher_matches:
            score += 1.0
        return min(score, 4.0)

    @staticmethod
    def atr_spike_block(snapshot) -> bool:
        atr_spike_threshold = snapshot.atr_spike_threshold
        atr_spike_block = bool(snapshot.atr_spike)
        if (
            not atr_spike_block
            and snapshot.atr is not None
            and atr_spike_threshold is not None
            and atr_spike_threshold > 0
        ):
            atr_spike_block = snapshot.atr > atr_spike_threshold
        return atr_spike_block

    @staticmethod
    def regime_score(snapshot, *, atr_spike_block: bool) -> float:
        if atr_spike_block:
            return 0.0
        if snapshot.adx is None:
            return 0.0
        if snapshot.adx >= settings.REGIME_ADX_MIN:
            return 2.0
        if snapshot.adx >= (settings.REGIME_ADX_MIN - 2.0):
            return 1.0
        return 0.5

    @staticmethod
    def long_regime_score(snapshot, *, atr_spike_block: bool) -> float:
        if snapshot.adx is None:
            return 0.0

        adx = snapshot.adx
        score = 0.0
        if adx < 15.0:
            score += 0.0
        elif adx < 18.0:
            score += 0.2
        elif adx < settings.REGIME_ADX_MIN:
            score += 0.6
        elif adx < 25.0:
            score += 1.6
        elif adx < 30.0:
            score += 0.7
        else:
            score += 1.1

        if snapshot.plus_di is not None and snapshot.minus_di is not None:
            di_delta = snapshot.plus_di - snapshot.minus_di
            if 0.0 < di_delta <= 8.0:
                score += 0.4
            elif di_delta > 8.0:
                score += 0.1 if adx >= 30.0 else -0.4
            elif -8.0 < di_delta <= 0.0:
                score -= 0.3
            else:
                score -= 0.8

        if snapshot.adx_slope is not None:
            if 0.5 <= snapshot.adx_slope < 2.0:
                score -= 0.3
            elif snapshot.adx_slope >= 2.0:
                score += 0.1

        if snapshot.atr_growth_20 is not None:
            if snapshot.atr_growth_20 >= 0.20:
                score -= 0.6
            elif -0.05 <= snapshot.atr_growth_20 <= 0.05:
                score += 0.5
            elif snapshot.atr_growth_20 <= -0.20:
                score -= 0.3

        if atr_spike_block:
            score -= 1.0

        return round(max(0.0, min(2.0, score)), 2)

    @staticmethod
    def long_trend_score(snapshot, price: float) -> float:
        score = 0.0
        if snapshot.ema50 is not None and price > snapshot.ema50:
            score += 0.7
        if (
            snapshot.ema50 is not None
            and snapshot.ema200 is not None
            and snapshot.ema50 > snapshot.ema200
            and price > snapshot.ema50
        ):
            score += 0.8
        if snapshot.ema50_slope is not None and snapshot.ema50_slope > 0:
            score += 0.8
        if (
            snapshot.adx is not None
            and snapshot.plus_di is not None
            and snapshot.minus_di is not None
            and snapshot.adx >= settings.REGIME_ADX_MIN
            and snapshot.plus_di > snapshot.minus_di
        ):
            score += 0.8
        return min(score, 4.0)

    @staticmethod
    def short_trend_score(snapshot, price: float) -> float:
        score = 0.0
        if snapshot.ema50 is not None and price < snapshot.ema50:
            score += 1.0
        if (
            snapshot.ema50 is not None
            and snapshot.ema200 is not None
            and snapshot.ema50 < snapshot.ema200
            and price < snapshot.ema50
        ):
            score += 1.0
        if snapshot.ema50_slope is not None and snapshot.ema50_slope < 0:
            score += 1.0
        if (
            snapshot.adx is not None
            and snapshot.plus_di is not None
            and snapshot.minus_di is not None
            and snapshot.adx >= settings.REGIME_ADX_MIN
            and snapshot.minus_di > snapshot.plus_di
        ):
            score += 1.0
        return min(score, 4.0)

    def long_momentum_score(self, snapshot) -> float:
        score = 0.0
        if snapshot.rsi is not None:
            if 52.0 <= snapshot.rsi < 58.0:
                score += 1.0
            elif 58.0 <= snapshot.rsi < 65.0:
                score += 1.4
            elif 65.0 <= snapshot.rsi < 72.0:
                score += 0.8
            elif 50.0 <= snapshot.rsi < 52.0:
                score += 0.5
        if (
            snapshot.macd is not None
            and snapshot.macd_signal is not None
            and snapshot.macd >= snapshot.macd_signal
        ):
            score += 0.8
        if self.has_rising_macd_histogram(snapshot):
            score += 0.8
        return min(score, 4.0)

    @staticmethod
    def short_momentum_score(snapshot) -> float:
        if snapshot.rsi is None or snapshot.macd is None or snapshot.macd_signal is None:
            return 0.0

        directional_rsi = 100.0 - snapshot.rsi
        macd_spread = snapshot.macd_signal - snapshot.macd
        macd_spread_atr = (macd_spread / snapshot.atr) if snapshot.atr else 0.0
        score = 0.0

        if (
            settings.SHORT_MOMENTUM_DIRECTIONAL_RSI_EARLY_MIN
            <= directional_rsi
            < settings.SHORT_MOMENTUM_DIRECTIONAL_RSI_HEALTHY_MIN
        ):
            score += 1.0
        elif (
            settings.SHORT_MOMENTUM_DIRECTIONAL_RSI_HEALTHY_MIN
            <= directional_rsi
            < settings.SHORT_MOMENTUM_DIRECTIONAL_RSI_LATE_MIN
        ):
            score += 1.4
        elif (
            settings.SHORT_MOMENTUM_DIRECTIONAL_RSI_LATE_MIN
            <= directional_rsi
            < settings.SHORT_MOMENTUM_DIRECTIONAL_RSI_EXHAUSTED_MIN
        ):
            score += 0.4
        elif directional_rsi < settings.SHORT_MOMENTUM_DIRECTIONAL_RSI_EARLY_MIN:
            score += 0.3

        if (
            settings.SHORT_MOMENTUM_MACD_SPREAD_EARLY_ATR_MIN
            <= macd_spread_atr
            < settings.SHORT_MOMENTUM_MACD_SPREAD_CONFIRM_ATR_MIN
        ):
            score += 0.8
        elif (
            settings.SHORT_MOMENTUM_MACD_SPREAD_CONFIRM_ATR_MIN
            <= macd_spread_atr
            < settings.SHORT_MOMENTUM_MACD_SPREAD_LATE_ATR_MIN
        ):
            score += 0.9
        elif (
            settings.SHORT_MOMENTUM_MACD_SPREAD_LATE_ATR_MIN
            <= macd_spread_atr
            < settings.SHORT_MOMENTUM_MACD_SPREAD_EXTREME_ATR_MIN
        ):
            score += 0.4
        elif macd_spread_atr >= settings.SHORT_MOMENTUM_MACD_SPREAD_EXTREME_ATR_MIN:
            score -= 0.4
        elif macd_spread_atr < settings.SHORT_MOMENTUM_MACD_SPREAD_EARLY_ATR_MIN:
            score += 0.2

        return round(max(0.0, min(4.0, score)), 2)

    @staticmethod
    def long_orderbook_score(orderbook) -> float:
        if orderbook is None:
            return 0.0
        return FuturesComponentScoreService.directional_orderbook_score(
            directional_volume=orderbook.buyers,
            opposite_volume=orderbook.sellers,
            directional_dominance=orderbook.dominance_ratio,
            directional_imbalance=orderbook.imbalance,
        )

    @staticmethod
    def short_orderbook_score(orderbook) -> float:
        if orderbook is None:
            return 0.0
        return FuturesComponentScoreService.directional_orderbook_score(
            directional_volume=orderbook.sellers,
            opposite_volume=orderbook.buyers,
            directional_dominance=-orderbook.dominance_ratio,
            directional_imbalance=-orderbook.imbalance,
        )

    @staticmethod
    def directional_orderbook_score(
        *,
        directional_volume: float,
        opposite_volume: float,
        directional_dominance: float,
        directional_imbalance: float,
    ) -> float:
        if directional_volume <= 0 or opposite_volume <= 0:
            return 0.0

        ratio = directional_volume / opposite_volume
        score = 0.0

        if settings.ORDERBOOK_DIRECTIONAL_RATIO_NEUTRAL_MIN <= ratio < settings.ORDERBOOK_DIRECTIONAL_RATIO_HEALTHY_MIN:
            score += 0.75
        elif settings.ORDERBOOK_DIRECTIONAL_RATIO_HEALTHY_MIN <= ratio < settings.ORDERBOOK_DIRECTIONAL_RATIO_STRONG_MIN:
            score += 1.5
        elif settings.ORDERBOOK_DIRECTIONAL_RATIO_STRONG_MIN <= ratio < settings.ORDERBOOK_DIRECTIONAL_RATIO_EXTREME_MIN:
            score += 1.25
        elif settings.ORDERBOOK_DIRECTIONAL_RATIO_EXTREME_MIN <= ratio < settings.ORDERBOOK_DIRECTIONAL_RATIO_BLOWOFF_MIN:
            score += 0.25

        if 0.0 <= directional_dominance < settings.ORDERBOOK_DIRECTIONAL_DOMINANCE_HEALTHY_MIN:
            score += 0.5
        elif settings.ORDERBOOK_DIRECTIONAL_DOMINANCE_HEALTHY_MIN <= directional_dominance < settings.ORDERBOOK_DIRECTIONAL_DOMINANCE_STRONG_MIN:
            score += 0.75
        elif settings.ORDERBOOK_DIRECTIONAL_DOMINANCE_STRONG_MIN <= directional_dominance < settings.ORDERBOOK_DIRECTIONAL_DOMINANCE_EXTREME_MIN:
            score += 0.35
        elif directional_dominance >= settings.ORDERBOOK_DIRECTIONAL_DOMINANCE_EXTREME_MIN:
            score -= 0.5

        if settings.ORDERBOOK_DIRECTIONAL_IMBALANCE_CONFIRM_MIN <= directional_imbalance < settings.ORDERBOOK_DIRECTIONAL_IMBALANCE_EXTREME_MIN:
            score += 0.25
        elif directional_imbalance >= settings.ORDERBOOK_DIRECTIONAL_IMBALANCE_EXTREME_MIN:
            score -= 0.25

        return round(max(0.0, min(3.0, score)), 2)

    @staticmethod
    def long_structure_score(snapshot, price: float, atr_spike_block: bool) -> float:
        return FuturesStructureScoreService.long_score(snapshot, price, atr_spike_block)

    @staticmethod
    def short_structure_score(snapshot, price: float, atr_spike_block: bool) -> float:
        return FuturesStructureScoreService.short_score(snapshot, price, atr_spike_block)

    @staticmethod
    def distance_from_lower_atr(price: float, lower: float | None, atr: float | None) -> float | None:
        return FuturesStructureScoreService.distance_from_lower_atr(price, lower, atr)

    @staticmethod
    def distance_to_lower_atr(price: float, lower: float | None, atr: float | None) -> float | None:
        return FuturesStructureScoreService.distance_to_lower_atr(price, lower, atr)

    @staticmethod
    def distance_from_upper_atr(price: float, upper: float | None, atr: float | None) -> float | None:
        return FuturesStructureScoreService.distance_from_upper_atr(price, upper, atr)

    @staticmethod
    def distance_to_upper_atr(price: float, upper: float | None, atr: float | None) -> float | None:
        return FuturesStructureScoreService.distance_to_upper_atr(price, upper, atr)

    @staticmethod
    def has_rising_macd_histogram(snapshot) -> bool:
        if not settings.MACD_HISTOGRAM_SIGNAL_ENABLED:
            return False
        histogram = snapshot.extras.get("macd_histogram", [])
        if not isinstance(histogram, list) or len(histogram) < 3:
            return False
        tail = histogram[-3:]
        try:
            values = [float(value) for value in tail]
        except (TypeError, ValueError):
            return False
        return values[0] < values[1] < values[2]

    @staticmethod
    def has_falling_macd_histogram(snapshot) -> bool:
        if not settings.MACD_HISTOGRAM_SIGNAL_ENABLED:
            return False
        histogram = snapshot.extras.get("macd_histogram", [])
        if not isinstance(histogram, list) or len(histogram) < 3:
            return False
        tail = histogram[-3:]
        try:
            values = [float(value) for value in tail]
        except (TypeError, ValueError):
            return False
        return values[0] > values[1] > values[2]
