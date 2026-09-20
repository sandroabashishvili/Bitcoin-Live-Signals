"""Telegram alerts for Futures simulation events."""

from __future__ import annotations

from typing import Any

from platform_v2.futures.config import ExecutionProfile
from platform_v2.futures.config import settings
from platform_v2.shared.backend.runtime_store.futures import (
    POSITION_EVENTS_FAMILY,
    SIGNALS_FAMILY,
    daily_json_path,
    load_json_dict,
    load_json_list,
)
from platform_v2.shared.backend.persistence import read_runtime_state, write_runtime_state
from platform_v2.futures.services.simulation.models import FuturesCycleSummary
from platform_v2.tools.telegram_bot_system.message_builder import (
    build_position_closed_message,
    build_signal_opened_message,
)
from platform_v2.tools.telegram_bot_system.notifier import broadcast_message


class FuturesTelegramNotificationService:
    _STATE_KEY = "telegram_notifications"

    def notify_cycle(
        self,
        *,
        profile: ExecutionProfile,
        summary: FuturesCycleSummary,
        date_iso: str,
    ) -> None:
        if not settings.TELEGRAM_BOT_ENABLED:
            return

        event = str(summary.position_event or "").strip().upper()

        metrics = load_json_dict(summary.metrics_path)
        snapshot_kwargs = self._snapshot_kwargs(metrics)

        # Always scan closed rows directly; summary.position_event can be overwritten
        # in the same cycle by ENTRY_DENIED/OPENED after an earlier close event.
        self._notify_unseen_closed_events(
            profile=profile,
            date_iso=date_iso,
            snapshot_kwargs=snapshot_kwargs,
        )

        if event.startswith("ENTRY_DENIED") or event in {"NO_EVENT", "NO_DATA", ""}:
            return

        if event == "OPENED":
            opened = self._latest_position_row(
                date_iso=date_iso,
                predicate=lambda row: str(row.get("event") or "").upper() == "OPENED",
            )
            if opened is None:
                return
            event_key = f"OPENED:{opened.get('position_id')}:{opened.get('timestamp_ms')}"
            if self._already_sent(event_key):
                return
            score = self._latest_signal_score(date_iso=date_iso)
            message = build_signal_opened_message(
                symbol=profile.symbol,
                timeframe=profile.timeframe,
                position_id=str(opened.get("position_id") or ""),
                event_time=str(opened.get("time_readable") or opened.get("timestamp_ms") or ""),
                side=self._position_side(opened),
                entry=float(opened.get("entry_price") or 0.0),
                take_profit=float(opened.get("tp_price") or 0.0),
                stop_loss=float(opened.get("sl_price") or 0.0),
                score=score,
                source_label="Futures",
                **snapshot_kwargs,
            )
            if self._broadcast(message):
                self._mark_sent(event_key)
            return

        closed = self._latest_position_row(
            date_iso=date_iso,
            predicate=lambda row: str(row.get("event") or "").upper() == "CLOSED"
            and str(row.get("outcome") or "").upper() == event,
        )
        if closed is None:
            return
        event_key = (
            f"CLOSED:{closed.get('position_id')}:{closed.get('timestamp_ms')}:{closed.get('outcome')}"
        )
        if self._is_sent(event_key):
            return
        outcome_label = event.replace("_", " ")
        message = build_position_closed_message(
            symbol=profile.symbol,
            timeframe=profile.timeframe,
            position_id=str(closed.get("position_id") or ""),
            event_time=str(closed.get("time_readable") or closed.get("timestamp_ms") or ""),
            side=self._position_side(closed),
            outcome=outcome_label,
            exit_price=self._as_optional_float(closed.get("exit_price")),
            net_pnl=self._as_optional_float(closed.get("net_pnl")),
            source_label="Futures",
            **snapshot_kwargs,
        )
        if self._broadcast(message):
            self._mark_sent(event_key)

    def _notify_unseen_closed_events(
        self,
        *,
        profile: ExecutionProfile,
        date_iso: str,
        snapshot_kwargs: dict[str, Any],
    ) -> None:
        rows = load_json_list(daily_json_path(POSITION_EVENTS_FAMILY, date_iso))
        closed_rows = [
            row
            for row in rows
            if str(row.get("event") or "").upper() == "CLOSED"
            and str(row.get("outcome") or "").strip() != ""
        ]
        if not closed_rows:
            return

        # Keep a stable order and avoid flooding too many historical rows in one cycle.
        closed_rows.sort(key=lambda row: int(row.get("timestamp_ms") or 0))
        unsent_rows: list[dict[str, Any]] = []
        for row in closed_rows:
            event_key = (
                f"CLOSED:{row.get('position_id')}:{row.get('timestamp_ms')}:{row.get('outcome')}"
            )
            if not self._is_sent(event_key):
                unsent_rows.append(row)
        if not unsent_rows:
            return

        for row in unsent_rows[-5:]:
            outcome_text = str(row.get("outcome") or "CLOSED").upper().replace("_", " ")
            event_key = (
                f"CLOSED:{row.get('position_id')}:{row.get('timestamp_ms')}:{row.get('outcome')}"
            )
            message = build_position_closed_message(
                symbol=profile.symbol,
                timeframe=profile.timeframe,
                position_id=str(row.get("position_id") or ""),
                event_time=str(row.get("time_readable") or row.get("timestamp_ms") or ""),
                side=self._position_side(row),
                outcome=outcome_text,
                exit_price=self._as_optional_float(row.get("exit_price")),
                net_pnl=self._as_optional_float(row.get("net_pnl")),
                source_label="Futures",
                **snapshot_kwargs,
            )
            if self._broadcast(message):
                self._mark_sent(event_key)

    def _latest_position_row(self, *, date_iso: str, predicate) -> dict[str, Any] | None:
        path = daily_json_path(POSITION_EVENTS_FAMILY, date_iso)
        rows = load_json_list(path)
        for row in reversed(rows):
            if predicate(row):
                return row
        return None

    def _latest_signal_score(self, *, date_iso: str) -> float | None:
        path = daily_json_path(SIGNALS_FAMILY, date_iso)
        rows = load_json_list(path)
        if not rows:
            return None
        return self._as_optional_float(rows[-1].get("score"))

    @staticmethod
    def _snapshot_kwargs(metrics: dict[str, Any]) -> dict[str, Any]:
        return {
            "open_positions": FuturesTelegramNotificationService._as_optional_int(
                metrics.get("open_positions")
            ),
            "active_exposure": FuturesTelegramNotificationService._as_optional_float(
                metrics.get("active_exposure")
            ),
            "available_balance": FuturesTelegramNotificationService._as_optional_float(
                metrics.get("available_balance")
            ),
            "equity": FuturesTelegramNotificationService._as_optional_float(metrics.get("equity")),
            "annualized_return": FuturesTelegramNotificationService._as_optional_float(
                metrics.get("annualized_return")
            ),
            "net_return_pct": FuturesTelegramNotificationService._as_optional_float(
                metrics.get("net_return_pct")
            ),
            "total_net_pnl": FuturesTelegramNotificationService._as_optional_float(
                metrics.get("total_net_pnl")
            ),
            "unrealized_pnl": FuturesTelegramNotificationService._as_optional_float(
                metrics.get("unrealized_pnl")
            ),
            "total_positions": FuturesTelegramNotificationService._as_optional_int(
                metrics.get("total_positions")
            ),
            "closed_positions": FuturesTelegramNotificationService._as_optional_int(
                metrics.get("closed_positions")
            ),
            "tp_hits": FuturesTelegramNotificationService._as_optional_int(metrics.get("tp_hits")),
            "sl_hits": FuturesTelegramNotificationService._as_optional_int(metrics.get("sl_hits")),
            "force_close_events": FuturesTelegramNotificationService._as_optional_int(
                metrics.get("force_close_events")
            ),
        }

    @staticmethod
    def _position_side(row: dict[str, Any]) -> str:
        side = str(row.get("side") or row.get("position_side") or "").strip().upper()
        return side if side in {"LONG", "SHORT"} else "UNKNOWN"

    def _already_sent(self, event_key: str) -> bool:
        return self._is_sent(event_key)

    def _is_sent(self, event_key: str) -> bool:
        payload = read_runtime_state(system="futures", state_key=self._STATE_KEY) or {}
        last_event_key = str(payload.get("last_event_key") or "")
        if last_event_key == event_key:
            return True
        sent_event_keys = payload.get("sent_event_keys")
        if isinstance(sent_event_keys, list):
            return event_key in [str(item) for item in sent_event_keys]
        return False

    def _mark_sent(self, event_key: str) -> None:
        payload = read_runtime_state(system="futures", state_key=self._STATE_KEY) or {}
        raw_keys = payload.get("sent_event_keys")
        keys: list[str] = []
        if isinstance(raw_keys, list):
            for item in raw_keys:
                text = str(item).strip()
                if text:
                    keys.append(text)
        if event_key not in keys:
            keys.append(event_key)
        if len(keys) > 500:
            keys = keys[-500:]
        write_runtime_state(
            system="futures",
            state_key=self._STATE_KEY,
            payload={"last_event_key": event_key, "sent_event_keys": keys},
        )

    @staticmethod
    def _broadcast(message: str) -> bool:
        result = broadcast_message(message)
        return int(result.get("sent", 0)) > 0

    @staticmethod
    def _as_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _money(value: float | None) -> str:
        if value is None:
            return "—"
        return f"${value:.2f}"

    @staticmethod
    def _signed_money(value: float | None) -> str:
        if value is None:
            return "—"
        sign = "+" if value > 0 else ""
        return f"{sign}${value:.2f}"
