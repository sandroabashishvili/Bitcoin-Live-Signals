from __future__ import annotations

from unittest.mock import patch
import unittest

from platform_v2.futures.services.analytics.trade_audit.entry_audit_service import (
    FuturesTradeEntryAuditService,
)
from platform_v2.spot.services.metrics_system.summary_service import MetricsSummaryService


class _RecordingPositionStateService:
    def __init__(self) -> None:
        self.lookback_days: int | None = 999

    def load_latest_positions(self, *, lookback_days, as_of_date_iso):
        self.lookback_days = lookback_days
        return []


class AnalyticsSourceBoundaryTests(unittest.TestCase):
    def test_spot_cumulative_metrics_request_all_position_history(self) -> None:
        state = _RecordingPositionStateService()
        MetricsSummaryService(position_state_service=state).build_summary(date_iso="2026-07-30")
        self.assertIsNone(state.lookback_days)

    def test_futures_audit_uses_runtime_file_day_not_close_timestamp_day(self) -> None:
        service = FuturesTradeEntryAuditService()
        opened = {
            "event": "OPENED",
            "status": "OPEN",
            "position_id": "FUT-1",
            "side": "LONG",
            "timestamp_ms": 100,
        }
        just_before_midnight = {
            "event": "CLOSED",
            "status": "CLOSED",
            "position_id": "FUT-1",
            "side": "LONG",
            "timestamp_ms": 200,
            "time_readable": "2026-07-29 23:59:59Z",
        }
        with (
            patch(
                "platform_v2.futures.services.analytics.trade_audit.entry_audit_service.load_family_rows_all",
                side_effect=([opened, just_before_midnight], [], []),
            ),
            patch(
                "platform_v2.futures.services.analytics.trade_audit.entry_audit_service.load_family_rows",
                return_value=[just_before_midnight],
            ),
            patch.object(
                service,
                "_build_audit_row",
                return_value={"position_id": "FUT-1", "close_timestamp_ms": 200},
            ),
        ):
            rows = service.build_rows(date_iso="2026-07-30")
        self.assertEqual([{"position_id": "FUT-1", "close_timestamp_ms": 200}], rows)


if __name__ == "__main__":
    unittest.main()
