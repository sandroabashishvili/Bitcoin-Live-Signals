"""Compute Spot BUY decisions entirely from Spot market context."""

from platform_v2.spot.config import settings
from platform_v2.spot.config import long_strategy_settings as rules
from platform_v2.spot.domain.models.signal import GateSnapshot, SignalDecision, SignalSide
from platform_v2.spot.services.signal.long_component_score_service import SpotLongComponentScoreService
from platform_v2.spot.services.trading.sl_tp_service import StopLossTakeProfitService
from dataclasses import asdict
from platform_v2.spot.services.signal.entry_quality_service import SpotEntryQualityService


class IndependentLongSignalService:
    def __init__(self, component_service=None, setup_service=None):
        self._components = component_service or SpotLongComponentScoreService()
        self._setups = setup_service or StopLossTakeProfitService()

    def build_signal(self, context, timestamp_ms=None, prior_signals=()):
        components = self._components.build_long_component_scores(context)
        weights = {name: getattr(rules, name.upper() + '_WEIGHT') for name in components}
        score = self._score_components(components)
        short_components = self._components.build_short_component_scores(context)
        short_score = self._score_components(short_components)
        direction = ('LONG' if score >= rules.BUY_THRESHOLD and score >= short_score else
                     'SHORT' if short_score >= rules.BUY_THRESHOLD and short_score > score else 'NO_SIGNAL')
        stamp = context.latest_candle.close_time_ms if timestamp_ms is None else timestamp_ms
        history = [dict(row, side=row.get('evaluated_direction', 'NO_SIGNAL')) for row in prior_signals]
        quality = SpotEntryQualityService().evaluate(signal_side=direction, timestamp_ms=stamp, prior_signals=history)
        thresholds = {'mtf': rules.MTF_RAW_GATE_MIN, 'regime': rules.REGIME_RAW_GATE_MIN,
                      'trend': rules.TREND_RAW_MIN, 'momentum': rules.MOMENTUM_RAW_GATE_MIN,
                      'orderbook': rules.ORDERBOOK_RAW_GATE_MIN, 'structure': rules.LONG_STRUCTURE_RAW_GATE_MIN}
        gate_values = {name: components[name] >= minimum for name, minimum in thresholds.items()}
        gate_values['structure'] &= not self._components.atr_spike_block(context.latest_snapshot)
        gates = GateSnapshot(**gate_values)
        confidence = min(1., max(0., score/rules.SETUP_CONFIDENCE_MAX_SCORE))
        allowed = direction == 'LONG'
        setup = self._setups.build_theoretical_setup(
            side=SignalSide.BUY, entry_price=context.latest_snapshot.price,
            snapshot=context.latest_snapshot, confidence=confidence) if allowed else None
        reasons = [f'Spot {name} gate {"passed" if passed else "failed"}.' for name, passed in gate_values.items()]
        if allowed and (setup is None or not 0 < setup.stop_loss < setup.entry_price < setup.take_profit):
            allowed = False
            reasons.append('Spot execution setup unavailable.')
        elif not allowed:
            reasons.append('Spot BUY blocked: opposite direction stronger.' if direction == 'SHORT'
                           else 'Spot BUY score below threshold.')
        return SignalDecision(
            timestamp_ms=context.latest_candle.close_time_ms if timestamp_ms is None else timestamp_ms,
            symbol=context.symbol, timeframe=context.timeframe,
            side=SignalSide.BUY if allowed else SignalSide.NO_SIGNAL,
            snapshot_price=context.latest_snapshot.price, score=score, threshold=rules.BUY_THRESHOLD,
            gates=gates, reasons=tuple(reasons), mtf_signals=dict(context.mtf_signals),
            mtf_direction=context.mtf_direction, theoretical_setup=setup,
            component_scores=components, component_weights=weights,
            strategy_version=settings.STRATEGY_VERSION, source_market='spot',
            setup_confidence=confidence, profit_lock_enabled=True,
            evaluated_direction=direction, direction_scores={'long': score, 'short': short_score},
            entry_quality=asdict(quality),
        )

    @staticmethod
    def _score_components(scores):
        # Preserve the original left-to-right arithmetic, including half-cent
        # rounding. Python's compensated sum() can change boundary decisions.
        return round(
            scores.get('mtf', 0.)*rules.MTF_WEIGHT
            + scores.get('regime', 0.)*rules.REGIME_WEIGHT
            + scores.get('trend', 0.)*rules.TREND_WEIGHT
            + scores.get('momentum', 0.)*rules.MOMENTUM_WEIGHT
            + scores.get('orderbook', 0.)*rules.ORDERBOOK_WEIGHT
            + scores.get('structure', 0.)*rules.STRUCTURE_WEIGHT, 2)
