"""Build adaptive SL/TP setups by composing domain stop-loss and take-profit rules."""

from __future__ import annotations

from platform_v2.futures.domain.models.indicator_snapshot import IndicatorSnapshot
from platform_v2.futures.domain.models.position import ExecutionSetup
from platform_v2.futures.domain.models.signal import SignalSide, TheoreticalSetup
from platform_v2.shared.backend.trading import (
    SlTpInputs,
    SlTpPayload,
    compute_stop_loss,
    compute_take_profit,
)
from platform_v2.futures.domain.short_stop_policy import apply_short_stop_cap
from platform_v2.futures.config import settings


class StopLossTakeProfitService:
    """Build structure-aware theoretical and execution setups for V2."""

    def __init__(
        self,
        *,
        short_stop_cap_enabled: bool = settings.SHORT_STOP_CAP_ENABLED,
        short_stop_cap_band_min_atr: float = settings.SHORT_STOP_CAP_BAND_MIN_ATR,
        short_stop_cap_band_max_atr: float = settings.SHORT_STOP_CAP_BAND_MAX_ATR,
        short_stop_cap_atr: float = settings.SHORT_STOP_CAP_ATR,
    ) -> None:
        self._short_stop_cap_enabled = bool(short_stop_cap_enabled)
        self._short_stop_cap_band_min_atr = float(short_stop_cap_band_min_atr)
        self._short_stop_cap_band_max_atr = float(short_stop_cap_band_max_atr)
        self._short_stop_cap_atr = float(short_stop_cap_atr)

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
        stop_loss = float(stop_loss_result.stop_loss)
        risk = float(stop_loss_result.risk)
        mode = "adaptive_v2"
        debug = [*stop_loss_result.debug, *take_profit_result.debug]
        if self._short_stop_cap_enabled:
            cap = apply_short_stop_cap(
                side=side.value,
                entry=entry_price,
                stop_loss=stop_loss,
                atr=atr,
                band_min_atr=self._short_stop_cap_band_min_atr,
                band_max_atr=self._short_stop_cap_band_max_atr,
                cap_atr=self._short_stop_cap_atr,
            )
            if cap.applied:
                stop_loss = cap.stop_loss
                risk = abs(float(entry_price) - stop_loss)
                mode = "adaptive_v2_short_stop_cap_25"
                debug.append(
                    f"SHORT stop cap: {cap.baseline_stop_atr:.4f} ATR -> "
                    f"{self._short_stop_cap_atr:.4f} ATR"
                )
        reward = abs(float(take_profit_result.take_profit) - float(entry_price))
        return SlTpPayload(
            stop_loss=stop_loss,
            take_profit=take_profit_result.take_profit,
            rr_ratio=reward / risk if risk > 0 else 0.0,
            risk=risk,
            mode=mode,
            debug=tuple(debug),
        )
