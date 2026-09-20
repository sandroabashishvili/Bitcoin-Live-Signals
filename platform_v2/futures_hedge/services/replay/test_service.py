"""Regression tests for Futures Hedge replay timeline handling."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from platform_v2.futures_hedge.services.replay.service import FuturesHedgeReplayService


class FuturesHedgeReplayTimelineTests(unittest.TestCase):
    def test_zero_price_reset_point_is_not_kept_as_latest_market_snapshot(self) -> None:
        stored_points = [
            {
                "point_type": "cycle_snapshot",
                "timestamp_ms": 2000,
                "mark_price": 0.0,
                "hedge_entries_accepted": 0,
            },
            {
                "point_type": "cycle_snapshot",
                "timestamp_ms": 1000,
                "mark_price": 62000.0,
                "hedge_entries_accepted": 1,
            },
        ]
        current_point = {
            "point_type": "cycle_snapshot",
            "timestamp_ms": 1000,
            "mark_price": 62000.0,
            "hedge_entries_accepted": 1,
        }

        with patch(
            "platform_v2.futures_hedge.services.replay.service.load_hedge_family_rows_all",
            return_value=stored_points,
        ):
            merged = FuturesHedgeReplayService()._merged_cycle_equity_points(current_point)

        self.assertEqual([1000], [row["timestamp_ms"] for row in merged])
        self.assertEqual(1, merged[-1]["hedge_entries_accepted"])


if __name__ == "__main__":
    unittest.main()
