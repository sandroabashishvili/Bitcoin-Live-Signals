from __future__ import annotations

import unittest
from unittest.mock import patch

from platform_v2.shared.backend.runtime_store.hedge import (
    HEDGE_DAILY_SUMMARIES_FAMILY,
    HEDGE_RESET_EVENTS_FAMILY,
)
from platform_v2.futures_hedge.services.ops import telegram_notifications
from platform_v2.futures_hedge.services.ops.telegram_notifications import (
    HedgeTelegramNotificationService,
)


class HedgeTelegramNotificationServiceTests(unittest.TestCase):
    def test_first_cycle_creates_baseline_without_historical_alerts(self) -> None:
        state: dict[str, object] = {}
        service = HedgeTelegramNotificationService()

        def load_rows(family: str):
            if family == HEDGE_RESET_EVENTS_FAMILY:
                return [{"reset_id": 5}]
            if family == HEDGE_DAILY_SUMMARIES_FAMILY:
                return [{"generated_at": "2026-07-30", "liquidation_risk": "LOW"}]
            return []

        def store_state(**kwargs):
            state.clear()
            state.update(kwargs["payload"])

        with (
            patch.object(telegram_notifications, "read_runtime_state", return_value=None),
            patch.object(telegram_notifications, "write_runtime_state", side_effect=store_state),
            patch.object(telegram_notifications, "load_family_rows_all", side_effect=load_rows),
            patch.object(telegram_notifications, "broadcast_message") as broadcast,
        ):
            service.notify_cycle()

        self.assertEqual(state["last_reset_id"], 5)
        self.assertEqual(state["last_risk"], "LOW")
        broadcast.assert_not_called()

    def test_new_reset_and_risk_transition_are_sent_once(self) -> None:
        state: dict[str, object] = {
            "initialized": True,
            "last_reset_id": 5,
            "last_risk": "LOW",
        }
        service = HedgeTelegramNotificationService()

        def load_rows(family: str):
            if family == HEDGE_RESET_EVENTS_FAMILY:
                return [
                    {"reset_id": 5},
                    {
                        "reset_id": 6,
                        "time_readable": "2026-07-30 20:00:00Z",
                        "reason": "capital_required_before_next_entry",
                        "mark_price": 65000,
                        "net_pnl": -12,
                        "equity_before_reset": 2500,
                        "cash_after_reset": 2488,
                    },
                ]
            if family == HEDGE_DAILY_SUMMARIES_FAMILY:
                return [
                    {
                        "generated_at": "2026-07-30 20:00:00Z",
                        "liquidation_risk": "ELEVATED",
                        "worst_basket_roe_pct": -30,
                        "margin_used_pct": 90,
                        "net_exposure_side": "SHORT",
                        "net_exposure_usdt": 2500,
                    }
                ]
            return []

        def store_state(**kwargs):
            state.clear()
            state.update(kwargs["payload"])

        with (
            patch.object(telegram_notifications, "read_runtime_state", side_effect=lambda **_: dict(state)),
            patch.object(telegram_notifications, "write_runtime_state", side_effect=store_state),
            patch.object(telegram_notifications, "load_family_rows_all", side_effect=load_rows),
            patch.object(
                telegram_notifications,
                "broadcast_message",
                return_value={"sent": 1, "failed": 0},
            ) as broadcast,
        ):
            service.notify_cycle()

        self.assertEqual(broadcast.call_count, 2)
        self.assertEqual(state["last_reset_id"], 6)
        self.assertEqual(state["last_risk"], "ELEVATED")


if __name__ == "__main__":
    unittest.main()
