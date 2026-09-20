"""File: signal_decision_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-06-01
Author: Codex
Purpose: Build normalized V2 signal decisions from market context.
"""

from __future__ import annotations

# Historical baseline only; not imported by the Spot runtime.
BUY_REQUIRE_REGIME = False

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.market_context import MarketContext
from platform_v2.spot.domain.models.signal import GateSnapshot, SignalDecision, SignalSide, TheoreticalSetup
from platform_v2.spot.services.trading.sl_tp_service import StopLossTakeProfitService
from platform_v2.spot.services.trading.setup_confidence import normalized_setup_confidence


class SignalDecisionService:
    """Build signal decisions from normalized market context."""

    def __init__(self, sl_tp_service: StopLossTakeProfitService | None = None) -> None:
        self._sl_tp_service = sl_tp_service or StopLossTakeProfitService()

    def build_signal(
        self,
        context: MarketContext,
        timestamp_ms: int | None = None,
    ) -> SignalDecision:
        """Build a normalized signal decision from market context."""

        if timestamp_ms is None:
            timestamp_ms = context.latest_candle.close_time_ms

        atr_spike_block = self._buy_atr_spike_block(context.latest_snapshot)
        buy_component_scores = self._build_buy_component_scores(context)
        buy_gates = self._build_buy_gates(
            context,
            component_scores=buy_component_scores,
            atr_spike_block=atr_spike_block,
        )
        buy_score = self._score_buy_components(component_scores=buy_component_scores)
        buy_reasons = self._build_reasons(side=SignalSide.BUY, context=context, gates=buy_gates)

        buy_is_actionable = self._buy_is_actionable(
            context=context,
            buy_score=buy_score,
            regime_passed=buy_gates.regime,
        )
        if BUY_REQUIRE_REGIME and not buy_gates.regime:
            buy_reasons.append("BUY blocked: regime confirmation is required even when the score passes.")

        if buy_is_actionable:
            return self._build_directional_decision(
                context=context,
                timestamp_ms=timestamp_ms,
                side=SignalSide.BUY,
                score=buy_score,
                threshold=settings.BUY_THRESHOLD,
                gates=buy_gates,
                reasons=buy_reasons,
                component_scores=buy_component_scores,
            )

        return self._build_no_signal_decision(
            context=context,
            timestamp_ms=timestamp_ms,
            buy_score=buy_score,
            buy_gates=buy_gates,
            reasons=buy_reasons,
            component_scores=buy_component_scores,
        )

    def _build_buy_gates(
        self,
        context: MarketContext,
        *,
        component_scores: dict[str, float],
        atr_spike_block: bool,
    ) -> GateSnapshot:
        """Build gate states for a BUY setup."""

        return GateSnapshot(
            mtf=component_scores.get("mtf", 0.0) >= settings.MTF_RAW_GATE_MIN,
            regime=component_scores.get("regime", 0.0) >= settings.REGIME_RAW_GATE_MIN,
            momentum=component_scores.get("momentum", 0.0) >= settings.MOMENTUM_RAW_GATE_MIN,
            trend=component_scores.get("trend", 0.0) >= settings.TREND_RAW_MIN,
            orderbook=component_scores.get("orderbook", 0.0) >= settings.ORDERBOOK_RAW_GATE_MIN,
            structure=(
                not atr_spike_block
                and component_scores.get("structure", 0.0) >= settings.STRUCTURE_RAW_GATE_MIN
            ),
        )

    @staticmethod
    def _score_buy_components(*, component_scores: dict[str, float]) -> float:
        return round(
            (component_scores.get("mtf", 0.0) * settings.MTF_WEIGHT)
            + (component_scores.get("regime", 0.0) * settings.REGIME_WEIGHT)
            + (component_scores.get("trend", 0.0) * settings.TREND_WEIGHT)
            + (component_scores.get("momentum", 0.0) * settings.MOMENTUM_WEIGHT)
            + (component_scores.get("orderbook", 0.0) * settings.ORDERBOOK_WEIGHT)
            + (component_scores.get("structure", 0.0) * settings.STRUCTURE_WEIGHT),
            2,
        )

    @staticmethod
    def _build_reasons(
        side: SignalSide,
        context: MarketContext,
        gates: GateSnapshot,
    ) -> list[str]:
        """Build a readable explanation bundle for the current decision."""

        side_text = side.value
        reasons = [f"{side_text} evaluation started at {context.latest_snapshot.timestamp_text}."]
        reasons.append(
            f"MTF context: direction={context.mtf_direction}, signals={context.mtf_signals}."
        )

        for gate_name in ("mtf", "regime", "momentum", "trend", "orderbook", "structure"):
            gate_value = getattr(gates, gate_name)
            if gate_value:
                reasons.append(f"{gate_name} gate passed for {side_text}.")
            else:
                reasons.append(f"{gate_name} gate failed for {side_text}.")

        if side == SignalSide.BUY and not gates.trend:
            reasons.append("BUY cannot become actionable while trend gate is false.")
        if side == SignalSide.BUY and not gates.orderbook:
            reasons.append("BUY needs clearly bullish orderflow, not weak bullish noise.")
        return reasons

    @staticmethod
    def _buy_is_actionable(
        *,
        context: MarketContext,
        buy_score: float,
        regime_passed: bool,
    ) -> bool:
        return buy_score >= settings.BUY_THRESHOLD and (
            not BUY_REQUIRE_REGIME or regime_passed
        )

    def _build_directional_decision(
        self,
        *,
        context: MarketContext,
        timestamp_ms: int,
        side: SignalSide,
        score: float,
        threshold: float,
        gates: GateSnapshot,
        reasons: list[str],
        component_scores: dict[str, float],
    ) -> SignalDecision:
        return SignalDecision(
            timestamp_ms=timestamp_ms,
            symbol=context.symbol,
            timeframe=context.timeframe,
            side=side,
            snapshot_price=context.latest_snapshot.price,
            score=score,
            threshold=threshold,
            gates=gates,
            reasons=tuple(reasons),
            mtf_signals=dict(context.mtf_signals),
            mtf_direction=context.mtf_direction,
            theoretical_setup=self._build_theoretical_setup(
                side=side,
                context=context,
                score=score,
            ),
            component_scores={
                key: round(float(value), 4)
                for key, value in component_scores.items()
            },
            strategy_version="spot-legacy-score-baseline",
            component_weights=dict(settings.SIGNAL_COMPONENT_WEIGHTS),
        )

    @staticmethod
    def _build_no_signal_decision(
        *,
        context: MarketContext,
        timestamp_ms: int,
        buy_score: float,
        buy_gates: GateSnapshot,
        reasons: list[str],
        component_scores: dict[str, float],
    ) -> SignalDecision:
        return SignalDecision(
            timestamp_ms=timestamp_ms,
            symbol=context.symbol,
            timeframe=context.timeframe,
            side=SignalSide.NO_SIGNAL,
            snapshot_price=context.latest_snapshot.price,
            score=buy_score,
            threshold=settings.BUY_THRESHOLD,
            gates=buy_gates,
            reasons=tuple([*reasons, "No BUY setup cleared the action threshold."]),
            mtf_signals=dict(context.mtf_signals),
            mtf_direction=context.mtf_direction,
            theoretical_setup=None,
            component_scores={
                key: round(float(value), 4)
                for key, value in component_scores.items()
            },
            strategy_version="spot-legacy-score-baseline",
            component_weights=dict(settings.SIGNAL_COMPONENT_WEIGHTS),
        )

    @staticmethod
    def _buy_mtf_score(context: MarketContext) -> float:
        primary_is_buy = context.mtf_signals.get(context.timeframe) == "BUY"
        fast_is_buy = context.mtf_signals.get("5m") == "BUY"
        higher_is_buy = context.mtf_signals.get("4h") == "BUY"
        score = 0.0
        if primary_is_buy:
            score += 2.0
        if fast_is_buy:
            score += 1.0
        if higher_is_buy:
            score += 1.0
        return min(score, 4.0)

    @staticmethod
    def _buy_atr_spike_block(snapshot) -> bool:
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
    def _buy_regime_score(snapshot, *, atr_spike_block: bool) -> float:
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

    def _build_buy_component_scores(self, context: MarketContext) -> dict[str, float]:
        snapshot = context.latest_snapshot
        orderbook = context.latest_orderbook
        atr_spike_block = self._buy_atr_spike_block(snapshot)
        return {
            "mtf": self._buy_mtf_score(context),
            "regime": self._buy_regime_score(snapshot, atr_spike_block=atr_spike_block),
            "trend": self._buy_trend_score(snapshot, snapshot.price),
            "momentum": self._buy_momentum_score(snapshot),
            "orderbook": self._buy_orderbook_score(orderbook),
            "structure": self._buy_structure_score(
                snapshot,
                snapshot.price,
                atr_spike_block,
            ),
        }

    def _buy_trend_score(self, snapshot, price: float) -> float:
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

    def _buy_momentum_score(self, snapshot) -> float:
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
        if self._has_rising_macd_histogram(snapshot):
            score += 0.8
        return min(score, 4.0)

    @staticmethod
    def _buy_orderbook_score(orderbook) -> float:
        if orderbook is None:
            return 0.0
        return SignalDecisionService._directional_orderbook_score(
            directional_volume=orderbook.buyers,
            opposite_volume=orderbook.sellers,
            directional_dominance=orderbook.dominance_ratio,
            directional_imbalance=orderbook.imbalance,
        )

    @staticmethod
    def _directional_orderbook_score(
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
    def _buy_structure_score(snapshot, price: float, atr_spike_block: bool) -> float:
        if atr_spike_block:
            return 0.0
        distance_from_low_atr = SignalDecisionService._distance_from_lower_atr(
            price,
            snapshot.swing_low,
            snapshot.atr,
        )
        room_to_high_atr = SignalDecisionService._distance_to_upper_atr(
            price,
            snapshot.swing_high,
            snapshot.atr,
        )
        if distance_from_low_atr is None or room_to_high_atr is None:
            return 0.0

        score = 0.0
        if (
            settings.STRUCTURE_LONG_LOW_DISTANCE_EARLY_ATR_MIN
            <= distance_from_low_atr
            < settings.STRUCTURE_LONG_LOW_DISTANCE_HEALTHY_ATR_MIN
        ):
            score += 1.0
        elif (
            settings.STRUCTURE_LONG_LOW_DISTANCE_EXTENSION_ATR_MIN
            <= distance_from_low_atr
            < settings.STRUCTURE_LONG_LOW_DISTANCE_BLOWOFF_ATR_MIN
        ):
            score += 0.8
        elif (
            settings.STRUCTURE_LONG_LOW_DISTANCE_MID_ATR_MIN
            <= distance_from_low_atr
            < settings.STRUCTURE_LONG_LOW_DISTANCE_EXTENSION_ATR_MIN
        ):
            score += 0.2
        elif (
            settings.STRUCTURE_LONG_LOW_DISTANCE_HEALTHY_ATR_MIN
            <= distance_from_low_atr
            < settings.STRUCTURE_LONG_LOW_DISTANCE_MID_ATR_MIN
        ):
            score += 0.1

        if (
            settings.STRUCTURE_LONG_SWING_HIGH_ROOM_MIN_ATR
            <= room_to_high_atr
            < settings.STRUCTURE_LONG_SWING_HIGH_ROOM_EXTENDED_ATR
        ):
            score += 0.8
        elif 0.5 <= room_to_high_atr < settings.STRUCTURE_LONG_SWING_HIGH_ROOM_MIN_ATR:
            score += 0.1
        elif room_to_high_atr < 0.5:
            score -= 0.8
        elif room_to_high_atr >= settings.STRUCTURE_LONG_SWING_HIGH_ROOM_EXTENDED_ATR:
            score += 0.1

        if bool(snapshot.bounce_confirmed):
            score += 0.2
        return round(max(0.0, min(3.0, score)), 2)

    @staticmethod
    def _distance_from_lower_atr(price: float, lower: float | None, atr: float | None) -> float | None:
        if lower is None or atr is None or atr <= 0:
            return None
        return (price - lower) / atr

    @staticmethod
    def _distance_to_upper_atr(price: float, upper: float | None, atr: float | None) -> float | None:
        if upper is None or atr is None or atr <= 0:
            return None
        return (upper - price) / atr

    @staticmethod
    def _has_rising_macd_histogram(snapshot) -> bool:
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

    def _build_theoretical_setup(
        self,
        side: SignalSide,
        context: MarketContext,
        score: float,
    ) -> TheoreticalSetup | None:
        """Build a structure-aware theoretical setup from current market context."""

        return self._sl_tp_service.build_theoretical_setup(
            side=side,
            entry_price=context.latest_snapshot.price,
            snapshot=context.latest_snapshot,
            confidence=normalized_setup_confidence(score),
        )
