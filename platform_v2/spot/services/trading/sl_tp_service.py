"""Build adaptive SL/TP setups by composing domain stop-loss and take-profit rules."""

from __future__ import annotations

from platform_v2.spot.domain.models.indicator_snapshot import IndicatorSnapshot
from platform_v2.spot.domain.models.position import ExecutionSetup
from platform_v2.spot.domain.models.signal import SignalSide, TheoreticalSetup
from platform_v2.shared.backend.trading import (
    SlTpInputs,
    SlTpPayload,
    compute_stop_loss,
    compute_take_profit,
)


class StopLossTakeProfitService:
    """Build structure-aware theoretical and execution setups for V2."""

    def build_theoretical_setup(
        self,
        *,
        side: SignalSide,
        entry_price: float,
        snapshot: IndicatorSnapshot,
        confidence: float | None = None,
    ) -> TheoreticalSetup | None:
        """Build one theoretical setup from a signal snapshot."""

        payload = self._build_payload(
            side=side,
            entry_price=entry_price,
            snapshot=snapshot,
            confidence=confidence,
        )
        if payload is None:
            return None

        return TheoreticalSetup(
            entry_price=entry_price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
            rr_ratio=payload.rr_ratio,
            mode=payload.mode,
        )

    def build_execution_setup(
        self,
        *,
        side: SignalSide,
        live_entry_price: float,
        snapshot: IndicatorSnapshot,
        position_size: float,
        confidence: float | None = None,
    ) -> ExecutionSetup | None:
        """Build one execution-time setup from a real entry and fresh context."""

        payload = self._build_payload(
            side=side,
            entry_price=live_entry_price,
            snapshot=snapshot,
            confidence=confidence,
        )
        if payload is None:
            return None

        return ExecutionSetup(
            entry_price=live_entry_price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
            rr_ratio=payload.rr_ratio,
            position_size=position_size,
            mode=payload.mode,
        )

    def _build_payload(
        self,
        *,
        side: SignalSide,
        entry_price: float,
        snapshot: IndicatorSnapshot,
        confidence: float | None = None,
    ) -> SlTpPayload | None:
        """Build one adaptive payload using domain SL/TP calculators."""

        atr = snapshot.atr
        if atr is None or atr <= 0:
            return None

        inputs = SlTpInputs(
            side="long" if side == SignalSide.BUY else "short",
            entry=entry_price,
            atr=atr,
            swing_low=snapshot.swing_low,
            swing_high=snapshot.swing_high,
            ema50=snapshot.ema50,
            kijun=snapshot.kijun,
            resistance_level=(
                snapshot.resistance_level or snapshot.swing_high
                if side == SignalSide.BUY
                else snapshot.swing_low
            ),
            liquidity_zone=(
                snapshot.liquidity_zone or snapshot.resistance_level or snapshot.swing_high
                if side == SignalSide.BUY
                else snapshot.liquidity_zone or snapshot.swing_low
            ),
            liquidity_tolerance=snapshot.liquidity_tolerance or 100.0,
            adx=snapshot.adx,
            confidence=confidence,
            fee_buffer_pct=0.0006,
        )
        stop_loss_result = compute_stop_loss(inputs)
        take_profit_result = compute_take_profit(inputs, risk=stop_loss_result.risk)
        return SlTpPayload(
            stop_loss=stop_loss_result.stop_loss,
            take_profit=take_profit_result.take_profit,
            rr_ratio=take_profit_result.rr_ratio,
            risk=stop_loss_result.risk,
            mode="adaptive_v2",
            debug=tuple([*stop_loss_result.debug, *take_profit_result.debug]),
        )
