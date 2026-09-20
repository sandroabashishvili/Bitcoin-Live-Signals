"""File: position_update_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Update open positions against closed candles and close them when levels are hit.
"""

from __future__ import annotations

from dataclasses import replace

from platform_v2.shared.backend.market.candle import Candle
from platform_v2.spot.domain.models.position import ExitReason, PositionRecord, PositionStatus
from platform_v2.spot.domain.models.signal import SignalSide
from platform_v2.spot.services.account.fee_service import FeeService
from platform_v2.spot.services.account.profit_lock import POLICY, update_managed_position


class PositionUpdateService:
    """Evaluate one open position against one closed candle."""

    def update_from_candles(
        self,
        position: PositionRecord,
        candles: list[Candle],
    ) -> PositionRecord:
        """Return an updated position state after evaluating multiple candles in order."""

        if position.is_closed or not candles:
            return position

        if (position.position_management or {}).get("policy") == POLICY and position.side == SignalSide.BUY:
            return update_managed_position(position, candles)

        last_candle = candles[-1]
        for candle in candles:
            exit_price, exit_reason = self._pick_exit(position, candle)
            if exit_reason is None or exit_price is None:
                continue

            pnl = self._compute_pnl(position, exit_price)
            net_pnl = self._compute_net_pnl(position, gross_pnl=pnl)
            return replace(
                position,
                status=PositionStatus.CLOSED,
                closed_at=str(candle.close_time_ms),
                exit_price=exit_price,
                exit_reason=exit_reason,
                pnl=pnl,
                net_pnl=net_pnl,
                unrealized_pnl=0.0,
                was_force_closed=exit_reason == ExitReason.FORCE_CLOSE,
                exit_check_timeframe=candle.timeframe,
                exit_trigger_candle_close_ms=candle.close_time_ms,
                exit_trigger_price=exit_price,
                exit_trigger_type=exit_reason.value,
            )

        unrealized_pnl = self._compute_pnl(position, last_candle.close_price)
        return replace(position, unrealized_pnl=unrealized_pnl)

    def update_from_candle(
        self,
        position: PositionRecord,
        candle: Candle,
    ) -> PositionRecord:
        """Return an updated position state after evaluating one candle."""
        return self.update_from_candles(position, [candle])

    def force_close(
        self,
        position: PositionRecord,
        *,
        close_price: float,
        closed_at: str,
        reason_text: str = "manual_force_close",
    ) -> PositionRecord:
        """Force-close an open position outside TP/SL evaluation."""

        if position.is_closed:
            return position

        pnl = self._compute_pnl(position, close_price)
        net_pnl = self._compute_net_pnl(position, gross_pnl=pnl)
        return replace(
            position,
            status=PositionStatus.CLOSED,
            closed_at=closed_at,
            exit_price=close_price,
            exit_reason=ExitReason.FORCE_CLOSE,
            pnl=pnl,
            net_pnl=net_pnl,
            unrealized_pnl=0.0,
            was_force_closed=True,
            force_close_reason=reason_text,
            exit_trigger_price=close_price,
            exit_trigger_type=ExitReason.FORCE_CLOSE.value,
        )

    def _pick_exit(
        self,
        position: PositionRecord,
        candle: Candle,
    ) -> tuple[float | None, ExitReason | None]:
        """Pick the exit outcome for one candle.

        Conservative rule:
        - if both TP and SL are touched in the same candle, count it as SL.
        """

        stop_loss = position.execution.stop_loss
        take_profit = position.execution.take_profit

        if position.side == SignalSide.BUY:
            sl_hit = candle.low_price <= stop_loss
            tp_hit = candle.high_price >= take_profit
            if sl_hit:
                return stop_loss, ExitReason.SL_HIT
            if tp_hit:
                return take_profit, ExitReason.TP_HIT
            return None, None

        if position.side == SignalSide.SELL:
            sl_hit = candle.high_price >= stop_loss
            tp_hit = candle.low_price <= take_profit
            if sl_hit:
                return stop_loss, ExitReason.SL_HIT
            if tp_hit:
                return take_profit, ExitReason.TP_HIT
            return None, None

        return None, None

    @staticmethod
    def _compute_pnl(position: PositionRecord, exit_price: float) -> float:
        """Compute simple gross PnL from entry, exit, and position size."""

        entry = position.execution.entry_price
        size = position.execution.position_size
        if entry <= 0:
            raise ValueError(
                f"Invalid entry_price for position {position.position_id}: {entry!r}"
            )
        if size <= 0:
            raise ValueError(
                f"Invalid position_size for position {position.position_id}: {size!r}"
            )
        quantity = size / entry

        if position.side == SignalSide.SELL:
            return (entry - exit_price) * quantity
        return (exit_price - entry) * quantity

    @staticmethod
    def _compute_net_pnl(position: PositionRecord, *, gross_pnl: float) -> float:
        """Compute deterministic paper net PnL after entry and exit fees."""

        position_size = float(position.execution.position_size or 0.0)
        return FeeService.net_pnl_from_gross(notional=position_size, gross_pnl=gross_pnl)
