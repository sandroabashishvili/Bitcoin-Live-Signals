"""File: signal_decision_service.py
Folder: platform_v2/futures/services/signal
Created date: 2026-03-25
Last updated date: 2026-06-01
Author: Codex
Purpose: Build normalized V2 signal decisions from market context.
"""

from __future__ import annotations

from platform_v2.futures.config import settings
from platform_v2.futures.domain.models.market_context import MarketContext
from platform_v2.futures.domain.models.signal import GateSnapshot, SignalDecision, SignalSide, TheoreticalSetup
from platform_v2.futures.services.signal.futures_component_score_service import (
    FuturesComponentScoreService,
)
from platform_v2.futures.services.trading.futures_sl_tp_service import StopLossTakeProfitService


class SignalDecisionService:
    """Build signal decisions from normalized market context."""

    def __init__(
        self,
        sl_tp_service: StopLossTakeProfitService | None = None,
        component_score_service: FuturesComponentScoreService | None = None,
    ) -> None:
        self._sl_tp_service = sl_tp_service or StopLossTakeProfitService()
        self._component_score_service = component_score_service or FuturesComponentScoreService()

    def build_signal(
        self,
        context: MarketContext,
        timestamp_ms: int | None = None,
    ) -> SignalDecision:
        """Build a normalized signal decision from market context."""

        if timestamp_ms is None:
            timestamp_ms = context.latest_candle.close_time_ms

        atr_spike_block = self._component_score_service.atr_spike_block(context.latest_snapshot)
        long_component_scores = self._component_score_service.build_long_component_scores(context)
        long_gates = self._build_direction_gates(
            context,
            direction="LONG",
            component_scores=long_component_scores,
            atr_spike_block=atr_spike_block,
        )
        long_score = self._score_components(component_scores=long_component_scores)
        long_reasons = self._build_reasons(direction="LONG", context=context, gates=long_gates)

        short_component_scores = self._component_score_service.build_short_component_scores(context)
        short_gates = self._build_direction_gates(
            context,
            direction="SHORT",
            component_scores=short_component_scores,
            atr_spike_block=atr_spike_block,
        )
        short_score = self._score_components(component_scores=short_component_scores)
        short_reasons = self._build_reasons(direction="SHORT", context=context, gates=short_gates)

        long_is_actionable = self._direction_is_actionable(
            context=context,
            direction="LONG",
            score=long_score,
        )
        short_is_actionable = self._direction_is_actionable(
            context=context,
            direction="SHORT",
            score=short_score,
        )
        direction_scores = {"long": long_score, "short": short_score}
        direction_gates = {"long": long_gates, "short": short_gates}
        direction_reasons = {
            "long": tuple(long_reasons),
            "short": tuple(short_reasons),
        }
        direction_component_scores = {
            "long": dict(long_component_scores),
            "short": dict(short_component_scores),
        }

        if long_is_actionable and (not short_is_actionable or long_score >= short_score):
            return self._build_directional_decision(
                context=context,
                timestamp_ms=timestamp_ms,
                side=SignalSide.BUY,
                selected_direction="LONG",
                score=long_score,
                threshold=settings.BUY_THRESHOLD,
                gates=long_gates,
                reasons=long_reasons,
                direction_scores=direction_scores,
                direction_gates=direction_gates,
                direction_reasons=direction_reasons,
                direction_component_scores=direction_component_scores,
            )

        if short_is_actionable and short_score > long_score:
            return self._build_directional_decision(
                context=context,
                timestamp_ms=timestamp_ms,
                side=SignalSide.SELL,
                selected_direction="SHORT",
                score=short_score,
                threshold=settings.BUY_THRESHOLD,
                gates=short_gates,
                reasons=short_reasons,
                direction_scores=direction_scores,
                direction_gates=direction_gates,
                direction_reasons=direction_reasons,
                direction_component_scores=direction_component_scores,
            )

        return self._build_no_signal_decision(
            context=context,
            timestamp_ms=timestamp_ms,
            long_score=long_score,
            short_score=short_score,
            long_gates=long_gates,
            short_gates=short_gates,
            long_reasons=long_reasons,
            short_reasons=short_reasons,
            direction_scores=direction_scores,
            direction_gates=direction_gates,
            direction_reasons=direction_reasons,
            direction_component_scores=direction_component_scores,
        )

    def _build_direction_gates(
        self,
        context: MarketContext,
        *,
        direction: str,
        component_scores: dict[str, float],
        atr_spike_block: bool,
    ) -> GateSnapshot:
        """Build gate states from raw directional component scores."""

        momentum_gate_min = (
            settings.SHORT_MOMENTUM_RAW_GATE_MIN
            if direction == "SHORT"
            else settings.MOMENTUM_RAW_GATE_MIN
        )
        structure_gate_min = (
            settings.SHORT_STRUCTURE_RAW_GATE_MIN
            if direction == "SHORT"
            else settings.LONG_STRUCTURE_RAW_GATE_MIN
        )
        return GateSnapshot(
            mtf=component_scores.get("mtf", 0.0) >= settings.MTF_RAW_GATE_MIN,
            regime=component_scores.get("regime", 0.0) >= settings.REGIME_RAW_GATE_MIN,
            momentum=component_scores.get("momentum", 0.0) >= momentum_gate_min,
            trend=component_scores.get("trend", 0.0) >= settings.TREND_RAW_MIN,
            orderbook=component_scores.get("orderbook", 0.0) >= settings.ORDERBOOK_RAW_GATE_MIN,
            structure=(
                not atr_spike_block
                and component_scores.get("structure", 0.0) >= structure_gate_min
            ),
        )

    @staticmethod
    def _score_components(*, component_scores: dict[str, float]) -> float:
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
        direction: str,
        context: MarketContext,
        gates: GateSnapshot,
    ) -> list[str]:
        """Build a readable explanation bundle for the current decision."""

        direction_text = direction.upper()
        reasons = [f"{direction_text} evaluation started at {context.latest_snapshot.timestamp_text}."]
        reasons.append(
            f"MTF context: direction={context.mtf_direction}, signals={context.mtf_signals}."
        )

        for gate_name in ("mtf", "regime", "momentum", "trend", "orderbook", "structure"):
            gate_value = getattr(gates, gate_name)
            if gate_value:
                reasons.append(f"{gate_name} gate passed for {direction_text}.")
            else:
                reasons.append(f"{gate_name} gate failed for {direction_text}.")

        return reasons

    @staticmethod
    def _direction_is_actionable(
        *,
        context: MarketContext,
        direction: str,
        score: float,
    ) -> bool:
        return score >= settings.BUY_THRESHOLD

    def _build_directional_decision(
        self,
        *,
        context: MarketContext,
        timestamp_ms: int,
        side: SignalSide,
        selected_direction: str,
        score: float,
        threshold: float,
        gates: GateSnapshot,
        reasons: list[str],
        direction_scores: dict[str, float],
        direction_gates: dict[str, GateSnapshot],
        direction_reasons: dict[str, tuple[str, ...]],
        direction_component_scores: dict[str, dict[str, float]],
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
            selected_direction=selected_direction,
            direction_scores=dict(direction_scores),
            direction_gates=dict(direction_gates),
            direction_reasons=dict(direction_reasons),
            direction_component_scores={
                direction: {
                    key: round(float(value), 4)
                    for key, value in scores.items()
                }
                for direction, scores in direction_component_scores.items()
            },
            strategy_version=settings.STRATEGY_VERSION,
            direction_thresholds=self._direction_thresholds(),
            direction_component_weights=self._direction_component_weights(),
        )

    @staticmethod
    def _build_no_signal_decision(
        *,
        context: MarketContext,
        timestamp_ms: int,
        long_score: float,
        short_score: float,
        long_gates: GateSnapshot,
        short_gates: GateSnapshot,
        long_reasons: list[str],
        short_reasons: list[str],
        direction_scores: dict[str, float],
        direction_gates: dict[str, GateSnapshot],
        direction_reasons: dict[str, tuple[str, ...]],
        direction_component_scores: dict[str, dict[str, float]],
    ) -> SignalDecision:
        primary_direction = context.mtf_signals.get(context.timeframe)
        if primary_direction == "LONG":
            selected_score = long_score
            selected_gates = long_gates
            reasons = [*long_reasons, "No LONG setup cleared the action threshold."]
        elif primary_direction == "SHORT":
            selected_score = short_score
            selected_gates = short_gates
            reasons = [*short_reasons, "No SHORT setup cleared the action threshold."]
        else:
            selected_score = 0.0
            selected_gates = GateSnapshot()
            reasons = (
                [*long_reasons, *short_reasons, "No directional setup cleared the action threshold."]
            )
        return SignalDecision(
            timestamp_ms=timestamp_ms,
            symbol=context.symbol,
            timeframe=context.timeframe,
            side=SignalSide.NO_SIGNAL,
            snapshot_price=context.latest_snapshot.price,
            score=round(float(selected_score), 2),
            threshold=settings.BUY_THRESHOLD,
            gates=selected_gates,
            reasons=tuple(reasons),
            mtf_signals=dict(context.mtf_signals),
            mtf_direction=context.mtf_direction,
            theoretical_setup=None,
            selected_direction="NO_SIGNAL",
            direction_scores=dict(direction_scores),
            direction_gates=dict(direction_gates),
            direction_reasons=dict(direction_reasons),
            direction_component_scores={
                direction: {
                    key: round(float(value), 4)
                    for key, value in scores.items()
                }
                for direction, scores in direction_component_scores.items()
            },
            strategy_version=settings.STRATEGY_VERSION,
            direction_thresholds=SignalDecisionService._direction_thresholds(),
            direction_component_weights=SignalDecisionService._direction_component_weights(),
        )

    @staticmethod
    def _direction_thresholds() -> dict[str, float]:
        return {
            "long": float(settings.BUY_THRESHOLD),
            "short": float(settings.BUY_THRESHOLD),
        }

    @staticmethod
    def _direction_component_weights() -> dict[str, dict[str, float]]:
        weights = {
            key: float(value)
            for key, value in settings.SIGNAL_COMPONENT_WEIGHTS.items()
        }
        return {
            "long": dict(weights),
            "short": dict(weights),
        }

    def _build_theoretical_setup(
        self,
        side: SignalSide,
        context: MarketContext,
        score: float,
    ) -> TheoreticalSetup | None:
        """Build a structure-aware theoretical setup from current market context."""

        max_score = 14.6
        confidence = min(1.0, max(0.0, score / max_score))
        return self._sl_tp_service.build_theoretical_setup(
            side=side,
            entry_price=context.latest_snapshot.price,
            snapshot=context.latest_snapshot,
            confidence=confidence,
        )
