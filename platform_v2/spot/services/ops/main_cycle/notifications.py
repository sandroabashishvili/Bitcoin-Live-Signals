from __future__ import annotations

import re
from typing import Any

from platform_v2.spot.services.metrics_system import MetricsSummaryService
from platform_v2.spot.domain.models.position import ExitReason, PositionRecord
from platform_v2.spot.services.permission.signal_permission_runtime_service import (
    SignalPermissionRunResult,
)
from platform_v2.tools.telegram_bot_system.message_builder import (
    build_position_closed_message,
    build_signal_opened_message,
)
from platform_v2.tools.telegram_bot_system.notifier import broadcast_message

from .models import TelegramSignalSnapshot


class MainCycleNotificationService:
    """Handle Telegram notifications triggered by one main-cycle result."""

    def __init__(
        self,
        metrics_summary_service: MetricsSummaryService | None = None,
    ) -> None:
        self._metrics_summary_service = metrics_summary_service or MetricsSummaryService()

    def notify_buy_opened(
        self,
        signal_result: SignalPermissionRunResult | None,
        *,
        date_iso: str,
        starting_balance: float,
    ) -> None:
        if not self._is_buy_opened_result(signal_result):
            return
        assert signal_result is not None
        assert signal_result.signal is not None
        assert signal_result.position is not None

        signal = signal_result.signal
        position = signal_result.position
        snapshot = self._build_telegram_signal_snapshot(
            date_iso=date_iso,
            starting_balance=starting_balance,
        )
        message = build_signal_opened_message(
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            position_id=position.position_id,
            event_time=position.opened_at,
            side=signal.side.value,
            entry=position.execution.entry_price,
            take_profit=position.execution.take_profit,
            stop_loss=position.execution.stop_loss,
            score=signal.score,
            source_label="Spot",
            open_positions=snapshot.open_positions,
            active_exposure=snapshot.active_exposure,
            available_balance=snapshot.available_balance,
            equity=snapshot.equity,
            annualized_return=snapshot.annualized_return,
            net_return_pct=snapshot.net_return_pct,
            total_net_pnl=snapshot.total_net_pnl,
            unrealized_pnl=snapshot.unrealized_pnl,
            total_positions=snapshot.total_positions,
            closed_positions=snapshot.closed_positions,
            tp_hits=snapshot.tp_hits,
            sl_hits=snapshot.sl_hits,
            force_close_events=snapshot.force_close_events,
        )
        self._broadcast_telegram_message(message)

    def notify_position_closes(
        self,
        updated_positions: tuple[PositionRecord, ...],
        *,
        date_iso: str,
        starting_balance: float,
    ) -> None:
        closed_positions = [position for position in updated_positions if position.is_closed]
        if not closed_positions:
            return

        for position in closed_positions:
            outcome = self._close_outcome_text(position)
            if outcome is None:
                continue
            snapshot = self._build_telegram_signal_snapshot(
                date_iso=date_iso,
                starting_balance=starting_balance,
            )
            message = build_position_closed_message(
                symbol=position.symbol,
                timeframe=position.timeframe,
                position_id=position.position_id,
                event_time=position.closed_at,
                side=position.side.value,
                outcome=outcome,
                exit_price=position.exit_price,
                net_pnl=(
                    position.net_pnl
                    if position.net_pnl is not None
                    else position.pnl
                ),
                exit_check_timeframe=position.exit_check_timeframe,
                source_label="Spot",
                open_positions=snapshot.open_positions,
                active_exposure=snapshot.active_exposure,
                available_balance=snapshot.available_balance,
                equity=snapshot.equity,
                annualized_return=snapshot.annualized_return,
                net_return_pct=snapshot.net_return_pct,
                total_net_pnl=snapshot.total_net_pnl,
                unrealized_pnl=snapshot.unrealized_pnl,
                total_positions=snapshot.total_positions,
                closed_positions=snapshot.closed_positions,
                tp_hits=snapshot.tp_hits,
                sl_hits=snapshot.sl_hits,
                force_close_events=snapshot.force_close_events,
            )
            self._broadcast_telegram_message(message)

    @staticmethod
    def _is_buy_opened_result(signal_result: SignalPermissionRunResult | None) -> bool:
        if signal_result is None:
            return False
        signal = signal_result.signal
        order_result = signal_result.order_result
        position = signal_result.position
        if signal is None or order_result is None or position is None:
            return False
        if getattr(signal.side, "value", None) != "BUY":
            return False
        return bool(order_result.is_filled)

    @staticmethod
    def _broadcast_telegram_message(message: str) -> None:
        result = broadcast_message(message)
        if result.get("sent", 0) <= 0:
            print(
                "[WARN] Telegram BUY OPENED alert was not delivered. "
                f"sent={result.get('sent', 0)} failed={result.get('failed', 0)}",
                flush=True,
            )

    @staticmethod
    def _close_outcome_text(position: PositionRecord) -> str | None:
        if position.was_force_closed or position.exit_reason == ExitReason.FORCE_CLOSE:
            return "FORCE CLOSED"
        if position.exit_reason == ExitReason.TP_HIT:
            return "TP HIT"
        if position.exit_reason == ExitReason.SL_HIT:
            return "SL HIT"
        return None

    def _build_telegram_signal_snapshot(
        self,
        *,
        date_iso: str,
        starting_balance: float,
    ) -> TelegramSignalSnapshot:
        metrics = self._metrics_summary_service.build_summary(
            date_iso=date_iso,
            starting_balance=starting_balance,
        )
        return TelegramSignalSnapshot(
            open_positions=self._coerce_int(metrics, "open_positions"),
            active_exposure=self._coerce_float(metrics, "active_exposure"),
            available_balance=self._coerce_float(metrics, "available_balance"),
            equity=self._coerce_float(metrics, "equity"),
            annualized_return=self._coerce_float(metrics, "annualized_return"),
            net_return_pct=self._coerce_float(metrics, "net_return_pct"),
            total_net_pnl=self._coerce_float(metrics, "total_net_pnl"),
            unrealized_pnl=self._coerce_float(metrics, "unrealized_pnl"),
            total_positions=self._coerce_int(metrics, "total_positions"),
            closed_positions=self._coerce_int(metrics, "closed_positions"),
            tp_hits=self._coerce_int(metrics, "tp_hits"),
            sl_hits=self._coerce_int(metrics, "sl_hits"),
            force_close_events=self._coerce_int(metrics, "force_close_events"),
        )

    @staticmethod
    def _coerce_int(mapping: dict[str, object], key: str) -> int:
        value: Any = mapping.get(key, 0)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if not text or not MainCycleNotificationService._NUMBER_PATTERN.match(text):
                return 0
            return int(float(text))
        if value is None:
            return 0
        return 0

    @staticmethod
    def _coerce_float(mapping: dict[str, object], key: str) -> float:
        value: Any = mapping.get(key, 0.0)
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text or not MainCycleNotificationService._NUMBER_PATTERN.match(text):
                return 0.0
            return float(text)
        if value is None:
            return 0.0
        return 0.0
    _NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)$")
