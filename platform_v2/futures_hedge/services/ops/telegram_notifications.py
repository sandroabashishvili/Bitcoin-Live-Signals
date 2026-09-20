"""Meaningful Telegram alerts for Hedge state changes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from platform_v2.shared.backend.persistence import read_runtime_state, write_runtime_state
from platform_v2.shared.backend.runtime_store.hedge import (
    HEDGE_DAILY_SUMMARIES_FAMILY,
    HEDGE_RESET_EVENTS_FAMILY,
    load_family_rows_all,
)
from platform_v2.tools.telegram_bot_system.message_builder import (
    build_hedge_reset_message,
    build_hedge_risk_change_message,
)
from platform_v2.tools.telegram_bot_system.notifier import broadcast_message


class HedgeTelegramNotificationService:
    """Send reset and risk-transition alerts without replaying old history."""

    _STATE_KEY = "telegram_notifications"

    def notify_cycle(self) -> None:
        reset_rows = self._sorted_reset_rows()
        summary = self._latest_summary()
        state = self._load_state()

        if not state.get("initialized"):
            self._store_state(
                {
                    "initialized": True,
                    "last_reset_id": self._latest_reset_id(reset_rows),
                    "last_risk": self._risk_label(summary),
                }
            )
            return

        last_reset_id = self._as_int(state.get("last_reset_id"))
        for row in reset_rows:
            reset_id = self._as_int(row.get("reset_id"))
            if reset_id <= last_reset_id:
                continue
            if not self._broadcast(self._build_reset_message(row)):
                break
            last_reset_id = reset_id
            state["last_reset_id"] = last_reset_id
            self._store_state(state)

        previous_risk = str(state.get("last_risk") or "UNKNOWN").upper()
        current_risk = self._risk_label(summary)
        if current_risk and current_risk != previous_risk:
            message = build_hedge_risk_change_message(
                previous_risk=previous_risk,
                current_risk=current_risk,
                worst_basket_roe_pct=self._as_optional_float(
                    summary.get("worst_basket_roe_pct")
                ),
                margin_used_pct=self._as_optional_float(summary.get("margin_used_pct")),
                net_exposure_side=str(summary.get("net_exposure_side") or "FLAT"),
                net_exposure_usdt=self._as_optional_float(summary.get("net_exposure_usdt")),
            )
            if self._broadcast(message):
                state["last_risk"] = current_risk
                self._store_state(state)

    def _sorted_reset_rows(self) -> list[dict[str, Any]]:
        rows = load_family_rows_all(HEDGE_RESET_EVENTS_FAMILY)
        rows.sort(key=lambda row: self._as_int(row.get("reset_id")))
        return rows

    @staticmethod
    def _latest_summary() -> dict[str, Any]:
        rows = load_family_rows_all(HEDGE_DAILY_SUMMARIES_FAMILY)
        if not rows:
            return {}
        return max(rows, key=lambda row: str(row.get("generated_at") or row.get("date") or ""))

    @staticmethod
    def _risk_label(summary: dict[str, Any]) -> str:
        return str(summary.get("liquidation_risk") or "UNKNOWN").strip().upper()

    @staticmethod
    def _latest_reset_id(rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        return max(HedgeTelegramNotificationService._as_int(row.get("reset_id")) for row in rows)

    @staticmethod
    def _build_reset_message(row: dict[str, Any]) -> str:
        return build_hedge_reset_message(
            reset_id=HedgeTelegramNotificationService._as_int(row.get("reset_id")),
            event_time=str(row.get("time_readable") or row.get("timestamp_ms") or ""),
            reason=str(row.get("reason") or "unspecified"),
            mark_price=HedgeTelegramNotificationService._as_optional_float(row.get("mark_price")),
            net_pnl=HedgeTelegramNotificationService._as_optional_float(row.get("net_pnl")),
            equity_before_reset=HedgeTelegramNotificationService._as_optional_float(
                row.get("equity_before_reset")
            ),
            cash_after_reset=HedgeTelegramNotificationService._as_optional_float(
                row.get("cash_after_reset")
            ),
        )

    def _load_state(self) -> dict[str, Any]:
        return read_runtime_state(system="hedge", state_key=self._STATE_KEY) or {}

    def _store_state(self, state: dict[str, Any]) -> None:
        payload = dict(state)
        payload["updated_at"] = datetime.now(tz=UTC).replace(microsecond=0).isoformat()
        write_runtime_state(system="hedge", state_key=self._STATE_KEY, payload=payload)

    @staticmethod
    def _broadcast(message: str) -> bool:
        result = broadcast_message(message)
        return int(result.get("sent", 0)) > 0

    @staticmethod
    def _as_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _as_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
