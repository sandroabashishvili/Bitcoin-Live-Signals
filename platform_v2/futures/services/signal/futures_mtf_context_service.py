"""File: mtf_context_service.py
Folder: platform_v2/futures/services/signal
Created date: 2026-03-25
Last updated date: 2026-06-01
Author: Codex
Purpose: Build multi-timeframe directional context for V2 signal gating.
"""

from __future__ import annotations

from platform_v2.futures.config import settings
from platform_v2.futures.domain.models.indicator_snapshot import IndicatorSnapshot


class MultiTimeframeContextService:
    """Resolve per-timeframe LONG/SHORT/NO_SIGNAL context and final MTF direction."""

    def build_signals(
        self,
        *,
        timeframe_snapshots: dict[str, IndicatorSnapshot | None],
        primary_timeframe: str,
    ) -> tuple[dict[str, str], str]:
        """Return per-timeframe signals and the resolved MTF direction."""

        signals: dict[str, str] = {}
        for timeframe, snapshot in timeframe_snapshots.items():
            signals[timeframe] = self._signal_for_timeframe(timeframe=timeframe, snapshot=snapshot)

        long_count = sum(1 for value in signals.values() if value == "LONG")
        short_count = sum(1 for value in signals.values() if value == "SHORT")
        primary_is_long = signals.get(primary_timeframe) == "LONG"
        primary_is_short = signals.get(primary_timeframe) == "SHORT"
        higher_timeframe_is_long = signals.get("4h") == "LONG"
        higher_timeframe_is_short = signals.get("4h") == "SHORT"

        mtf_direction = "NO_SIGNAL"
        if long_count >= 2 and higher_timeframe_is_long:
            mtf_direction = "LONG"
        elif primary_is_long and higher_timeframe_is_long:
            mtf_direction = "LONG"
        elif short_count >= 2 and higher_timeframe_is_short:
            mtf_direction = "SHORT"
        elif primary_is_short and higher_timeframe_is_short:
            mtf_direction = "SHORT"

        return signals, mtf_direction

    @staticmethod
    def _signal_for_timeframe(*, timeframe: str, snapshot: IndicatorSnapshot | None) -> str:
        """Resolve a simple LONG/SHORT/NO_SIGNAL bias per timeframe from indicator data."""

        if snapshot is None:
            return "NO_SIGNAL"

        if timeframe == "5m":
            return MultiTimeframeContextService._signal_for_5m(snapshot)

        if timeframe == "4h":
            return MultiTimeframeContextService._signal_for_4h(snapshot)

        return MultiTimeframeContextService._signal_for_primary(snapshot)

    @staticmethod
    def _signal_for_5m(snapshot: IndicatorSnapshot) -> str:
        long_score = MultiTimeframeContextService._long_5m_timing_score(snapshot)

        short_passed = 0
        if snapshot.rsi is not None and snapshot.rsi < 50.0:
            short_passed += 1
        if snapshot.vwap is not None and snapshot.price < snapshot.vwap:
            short_passed += 1
        if snapshot.adx is not None and snapshot.adx > settings.REGIME_ADX_MIN:
            short_passed += 1

        if long_score >= settings.MTF_5M_TIMING_SCORE_MIN and short_passed < 2:
            return "LONG"
        if short_passed >= 2:
            return "SHORT"
        return "NO_SIGNAL"

    @staticmethod
    def _signal_for_4h(snapshot: IndicatorSnapshot) -> str:
        long_score = MultiTimeframeContextService._long_4h_context_score(snapshot)

        short_passed = 0
        if (
            snapshot.tenkan is not None
            and snapshot.kijun is not None
            and snapshot.tenkan < snapshot.kijun
        ):
            short_passed += 1
        if (
            snapshot.ema50 is not None
            and snapshot.ema200 is not None
            and snapshot.ema50 < snapshot.ema200
        ):
            short_passed += 1
        if snapshot.rsi is not None and snapshot.rsi < 50.0:
            short_passed += 1

        if long_score >= settings.MTF_HIGHER_CONTEXT_SCORE_MIN and short_passed < 2:
            return "LONG"
        if short_passed >= 2:
            return "SHORT"
        return "NO_SIGNAL"

    @staticmethod
    def _signal_for_primary(snapshot: IndicatorSnapshot) -> str:
        long_score = MultiTimeframeContextService._long_primary_setup_score(snapshot)

        short_passed = 0
        if MultiTimeframeContextService._has_falling_macd_histogram(snapshot):
            short_passed += 1
        if snapshot.ema50_slope is not None and snapshot.ema50_slope < 0:
            short_passed += 1
        if snapshot.rsi is not None and snapshot.rsi < 50.0:
            short_passed += 1

        if long_score >= settings.MTF_PRIMARY_SETUP_SCORE_MIN and short_passed < 2:
            return "LONG"
        if short_passed >= 2:
            return "SHORT"
        return "NO_SIGNAL"

    @staticmethod
    def _long_5m_timing_score(snapshot: IndicatorSnapshot) -> float:
        score = MultiTimeframeContextService._entry_rsi_score(snapshot.rsi)
        vwap_distance = MultiTimeframeContextService._distance_atr(
            price=snapshot.price,
            reference=snapshot.vwap,
            atr=snapshot.atr,
        )
        if vwap_distance is not None:
            if -0.4 <= vwap_distance <= 0.8:
                score += 0.9
            elif 0.8 < vwap_distance <= 1.5:
                score += 0.2
            elif vwap_distance > 1.5:
                score -= 0.8
            elif vwap_distance < -0.8:
                score -= 0.2

        high_distance = MultiTimeframeContextService._distance_to_upper_atr(
            price=snapshot.price,
            upper=snapshot.swing_high,
            atr=snapshot.atr,
        )
        if high_distance is not None:
            if 0.5 <= high_distance <= 1.5:
                score -= 0.8
            elif 0 <= high_distance < 0.5:
                score -= 0.2
            elif high_distance > 3.0:
                score += 0.2

        if snapshot.adx is not None:
            if snapshot.adx >= 30.0:
                score += 0.4
            elif snapshot.adx < 20.0:
                score -= 0.3
        return score

    @staticmethod
    def _long_4h_context_score(snapshot: IndicatorSnapshot) -> float:
        score = 0.0
        if snapshot.rsi is not None:
            if 35.0 <= snapshot.rsi < 45.0:
                score += 0.8
            elif 45.0 <= snapshot.rsi <= 50.0:
                score += 0.5
            elif 50.0 < snapshot.rsi <= 55.0:
                score -= 0.4
            elif snapshot.rsi > 55.0:
                score -= 0.8

        vwap_distance = MultiTimeframeContextService._distance_atr(
            price=snapshot.price,
            reference=snapshot.vwap,
            atr=snapshot.atr,
        )
        if vwap_distance is not None:
            if vwap_distance < -1.0:
                score += 0.6
            elif -1.0 <= vwap_distance <= 0.3:
                score += 0.2
            elif vwap_distance > 0.3:
                score -= 0.6

        high_distance = MultiTimeframeContextService._distance_to_upper_atr(
            price=snapshot.price,
            upper=snapshot.swing_high,
            atr=snapshot.atr,
        )
        if high_distance is not None:
            if 0 <= high_distance <= 1.5:
                score -= 0.8
            elif high_distance > 3.0:
                score += 0.4

        if (
            snapshot.tenkan is not None
            and snapshot.kijun is not None
            and snapshot.tenkan > snapshot.kijun
        ):
            score += 0.2
        if (
            snapshot.ema50 is not None
            and snapshot.ema200 is not None
            and snapshot.ema50 > snapshot.ema200
        ):
            score += 0.2
        return score

    @staticmethod
    def _long_primary_setup_score(snapshot: IndicatorSnapshot) -> float:
        score = MultiTimeframeContextService._entry_rsi_score(snapshot.rsi)
        if MultiTimeframeContextService._has_rising_macd_histogram(snapshot):
            score += 0.2
        if snapshot.ema50_slope is not None and snapshot.ema50_slope > 0:
            score += 0.4

        vwap_distance = MultiTimeframeContextService._distance_atr(
            price=snapshot.price,
            reference=snapshot.vwap,
            atr=snapshot.atr,
        )
        if vwap_distance is not None:
            if 0.3 <= vwap_distance <= 1.0:
                score += 0.8
            elif 1.0 < vwap_distance <= 1.5:
                score -= 0.2
            elif vwap_distance > 1.5:
                score -= 0.8

        ema50_distance = MultiTimeframeContextService._distance_atr(
            price=snapshot.price,
            reference=snapshot.ema50,
            atr=snapshot.atr,
        )
        if ema50_distance is not None:
            if 0.3 <= ema50_distance <= 1.0:
                score += 0.5
            elif -0.3 <= ema50_distance < 0.3:
                score -= 0.3
            elif ema50_distance > 1.5:
                score -= 0.8

        high_distance = MultiTimeframeContextService._distance_to_upper_atr(
            price=snapshot.price,
            upper=snapshot.swing_high,
            atr=snapshot.atr,
        )
        if high_distance is not None:
            if 0.5 <= high_distance <= 1.5:
                score -= 0.6
            elif 1.5 < high_distance <= 3.0:
                score -= 0.8
            elif 0 <= high_distance < 0.5:
                score -= 0.2

        if snapshot.adx is not None:
            if 20.0 <= snapshot.adx < 25.0:
                score += 0.4
            elif snapshot.adx < 20.0 or 25.0 <= snapshot.adx < 30.0:
                score -= 0.4
        return score

    @staticmethod
    def _entry_rsi_score(rsi: float | None) -> float:
        if rsi is None:
            return 0.0
        if 40.0 <= rsi <= 55.0:
            return 0.8
        if 35.0 <= rsi < 40.0:
            return 0.4
        if 55.0 < rsi <= 60.0:
            return 0.2
        if 60.0 < rsi < 70.0:
            return -0.5
        if rsi >= 70.0:
            return -1.0
        return -0.2

    @staticmethod
    def _distance_atr(*, price: float | None, reference: float | None, atr: float | None) -> float | None:
        if price is None or reference is None or atr is None or atr <= 0:
            return None
        return (price - reference) / atr

    @staticmethod
    def _distance_to_upper_atr(
        *,
        price: float | None,
        upper: float | None,
        atr: float | None,
    ) -> float | None:
        if price is None or upper is None or atr is None or atr <= 0:
            return None
        return (upper - price) / atr

    @staticmethod
    def _has_rising_macd_histogram(snapshot: IndicatorSnapshot) -> bool:
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
        return len(values) == 3 and values[0] < values[1] < values[2]

    @staticmethod
    def _has_falling_macd_histogram(snapshot: IndicatorSnapshot) -> bool:
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
        return len(values) == 3 and values[0] > values[1] > values[2]
