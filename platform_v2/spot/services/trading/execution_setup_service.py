"""File: execution_setup_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Build execution-time SL/TP setup from a live entry price.
"""

from __future__ import annotations

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.market_context import MarketContext
from platform_v2.spot.domain.models.position import ExecutionSetup
from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide
from platform_v2.spot.services.trading.sl_tp_service import StopLossTakeProfitService
from platform_v2.spot.services.trading.setup_confidence import normalized_setup_confidence


class ExecutionSetupService:
    """Build an execution setup from a live entry and a signal decision."""

    def __init__(self, sl_tp_service: StopLossTakeProfitService | None = None) -> None:
        self._sl_tp_service = sl_tp_service or StopLossTakeProfitService()

    def build_setup(
        self,
        signal: SignalDecision,
        *,
        live_entry_price: float,
        position_size: float = settings.DEFAULT_POSITION_SIZE,
        market_context: MarketContext | None = None,
    ) -> ExecutionSetup:
        """Build execution-time SL/TP from a real entry price."""

        if live_entry_price <= 0:
            raise ValueError(f"live_entry_price must be > 0, got {live_entry_price!r}")

        if market_context is not None:
            adaptive_setup = self._sl_tp_service.build_execution_setup(
                side=signal.side,
                live_entry_price=live_entry_price,
                snapshot=market_context.latest_snapshot,
                position_size=position_size,
                confidence=(signal.setup_confidence if signal.setup_confidence is not None
                            else normalized_setup_confidence(signal.score)),
            )
            if adaptive_setup is not None:
                return adaptive_setup

        rr_ratio = settings.SETUP_RR_RATIO
        mode = "fallback_pct_seeded"
        if signal.theoretical_setup is not None:
            rr_ratio = signal.theoretical_setup.rr_ratio
            risk_distance = abs(
                signal.theoretical_setup.entry_price - signal.theoretical_setup.stop_loss
            )
            mode = signal.theoretical_setup.mode
        else:
            risk_distance = live_entry_price * (settings.FALLBACK_RISK_PCT / 100.0)

        if signal.side == SignalSide.SELL:
            stop_loss = live_entry_price + risk_distance
            take_profit = live_entry_price - (risk_distance * rr_ratio)
        else:
            stop_loss = live_entry_price - risk_distance
            take_profit = live_entry_price + (risk_distance * rr_ratio)

        return ExecutionSetup(
            entry_price=live_entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rr_ratio=rr_ratio,
            position_size=position_size,
            mode=mode,
        )
