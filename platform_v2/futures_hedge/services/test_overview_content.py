"""Regression coverage for the Hedge overview backend/frontend boundary."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from platform_v2.futures_hedge.config import FuturesHedgeProfile
from platform_v2.futures_hedge.dashboard.overview_hedge.py.page_builder import (
    FuturesHedgeOverviewPageService,
)
from platform_v2.futures_hedge.services import overview_content as content
from platform_v2.shared.backend.runtime_store.hedge import (
    HEDGE_BASKET_SNAPSHOTS_FAMILY,
    HEDGE_DAILY_SUMMARIES_FAMILY,
    HEDGE_ENTRIES_FAMILY,
    HEDGE_EQUITY_TIMELINE_FAMILY,
)


class HedgeOverviewContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = FuturesHedgeProfile(
            starting_capital_usdt=1000.0, position_margin_usdt=50.0,
            leverage=10, entry_fee_pct=0.001,
        )
        self.summary = {
            "date": "2026-10-08", "long_basket": {"side": "LONG"},
            "short_basket": {"side": "SHORT"}, "equity_usdt": 900.0,
            "generated_at": "2026-10-08T20:00:00Z",
            "max_drawdown_pct": 17.0, "peak_equity_usdt": 1300.0,
            "lowest_equity_usdt": 830.0,
        }
        self.rows = {
            HEDGE_ENTRIES_FAMILY: [{"timestamp_ms": 1000}, {"timestamp_ms": 2000}],
            HEDGE_BASKET_SNAPSHOTS_FAMILY: [
                {"timestamp_ms": 2000, "equity_usdt": 900.0},
                {"timestamp_ms": 1000, "equity_usdt": 1500.0},
            ],
            HEDGE_EQUITY_TIMELINE_FAMILY: [],
            HEDGE_DAILY_SUMMARIES_FAMILY: [self.summary],
        }
        self.profile_patch = patch.object(content, "default_profile", return_value=self.profile)
        self.loader_patch = patch.object(
            content, "load_family_rows_all", side_effect=lambda family: self.rows[family]
        )
        self.replay_patch = patch.object(content, "FuturesHedgeReplayService")
        self.profile_patch.start()
        self.loader_patch.start()
        self.replay = self.replay_patch.start()
        self.addCleanup(self.profile_patch.stop)
        self.addCleanup(self.loader_patch.stop)
        self.addCleanup(self.replay_patch.stop)

    def build(self) -> dict:
        return content.FuturesHedgeOverviewContentService().build_page_content()

    def test_latest_summary_and_basket_history_supply_account_and_statistics(self) -> None:
        self.rows[HEDGE_DAILY_SUMMARIES_FAMILY].append({**self.summary, "date": "2026-10-07", "equity_usdt": 25.0})
        report = self.build()
        self.replay.assert_not_called()
        self.assertEqual(900.0, report["final_snapshot"]["equity_usdt"])
        self.assertEqual([2000, 1000], [r["timestamp_ms"] for r in report["entries"]])
        self.assertEqual(1500.0, report["peak_equity_usdt"])
        self.assertEqual(900.0, report["lowest_equity_usdt"])
        self.assertEqual(40.0, report["max_drawdown_pct"])
        self.assertEqual(10.0, report["max_loss_from_start_pct"])
        self.assertEqual(50.5, report["decision_summary"]["next_entry_required_capital_usdt"])
        self.assertEqual([1500.0, 900.0], [r["equity"] for r in report["equity_chart_rows"]])
        self.assertEqual("1970-01-01T00:00:01+00:00", report["equity_chart_rows"][0]["datetime"])

    def test_timeline_is_used_when_basket_history_is_empty(self) -> None:
        self.rows[HEDGE_BASKET_SNAPSHOTS_FAMILY] = []
        self.rows[HEDGE_EQUITY_TIMELINE_FAMILY] = [{"timestamp_ms": 3000, "equity_usdt": 100.0}]
        report = self.build()
        self.assertEqual(90.0, report["max_drawdown_pct"])
        self.assertEqual([100.0], [r["equity"] for r in report["equity_chart_rows"]])
        self.assertEqual([], report["basket_chart_rows"])

    def test_empty_history_preserves_summary_statistics(self) -> None:
        self.rows[HEDGE_BASKET_SNAPSHOTS_FAMILY] = []
        self.rows[HEDGE_EQUITY_TIMELINE_FAMILY] = []
        report = self.build()
        self.assertIsNone(report["max_drawdown_pct"])
        self.assertEqual(17.0, report["max_loss_from_start_pct"])
        self.assertEqual(1300.0, report["peak_equity_usdt"])
        self.assertEqual(830.0, report["lowest_equity_usdt"])
        self.assertEqual([], report["equity_chart_rows"])

    def test_missing_summary_delegates_to_backend_replay(self) -> None:
        self.rows[HEDGE_DAILY_SUMMARIES_FAMILY] = []
        expected = {"system": "futures_hedge", "fallback": True}
        self.replay.return_value.build_report.return_value = expected
        self.assertIs(expected, self.build())
        self.replay.return_value.build_report.assert_called_once_with()

    def test_versioned_summary_keeps_distinct_risk_values_without_history(self) -> None:
        self.rows[HEDGE_BASKET_SNAPSHOTS_FAMILY] = []
        self.rows[HEDGE_EQUITY_TIMELINE_FAMILY] = []
        self.summary.update(drawdown_definition="peak_to_trough_v1", max_drawdown_pct=20.0, max_loss_from_start_pct=0.0)
        report = self.build()
        self.assertEqual(20.0, report["max_drawdown_pct"])
        self.assertEqual(0.0, report["max_loss_from_start_pct"])

    def test_renderer_exposes_both_risk_measures_with_explanations(self) -> None:
        from platform_v2.futures_hedge.dashboard.overview_hedge.py.renderer import FuturesHedgeOverviewRenderer
        html = FuturesHedgeOverviewRenderer().render(self.build())
        self.assertIn("Max Drawdown from Peak", html)
        self.assertIn("Max Loss from Start", html)
        self.assertIn("hedge.capital.max_drawdown", html)
        self.assertIn("hedge.capital.max_loss_from_start", html)
        self.assertIn('"title": "Max Drawdown from Peak"', html)

    def test_versioned_summary_is_authoritative_over_sparser_chart_history(self) -> None:
        self.summary.update(drawdown_definition="peak_to_trough_v1", max_drawdown_pct=6.259, max_loss_from_start_pct=5.9743)
        report = self.build()
        self.assertEqual(6.259, report["max_drawdown_pct"])
        self.assertEqual(5.9743, report["max_loss_from_start_pct"])

    def test_legacy_summary_uses_cycle_history_before_sparse_basket_history(self) -> None:
        self.rows[HEDGE_EQUITY_TIMELINE_FAMILY] = [
            {"timestamp_ms": 1000, "equity_usdt": 1500.0},
            {"timestamp_ms": 2000, "equity_usdt": 750.0},
        ]
        report = self.build()
        self.assertEqual(50.0, report["max_drawdown_pct"])
        self.assertEqual(25.0, report["max_loss_from_start_pct"])

    def test_invalid_latest_basket_delegates_to_backend_replay(self) -> None:
        for key in ("long_basket", "short_basket"):
            with self.subTest(key=key):
                self.replay.reset_mock()
                self.rows[HEDGE_DAILY_SUMMARIES_FAMILY] = [
                    self.summary, {**self.summary, "date": "2026-10-09", key: None}
                ]
                self.assertIs(self.replay.return_value.build_report.return_value, self.build())
                self.replay.return_value.build_report.assert_called_once_with()

    def test_peak_drawdown_is_separate_from_starting_capital_loss(self) -> None:
        self.rows[HEDGE_BASKET_SNAPSHOTS_FAMILY] = [
            {"timestamp_ms": i * 1000, "equity_usdt": equity}
            for i, equity in enumerate((1000.0, 1500.0, 1200.0), start=1)
        ]
        report = self.build()
        self.assertEqual(20.0, report["max_drawdown_pct"])
        self.assertEqual(0.0, report["max_loss_from_start_pct"])

    def test_invalid_chart_values_keep_existing_filter_and_rounding(self) -> None:
        self.rows[HEDGE_BASKET_SNAPSHOTS_FAMILY] = [
            {"timestamp_ms": "bad", "equity_usdt": 600.0},
            {"timestamp_ms": 3000, "equity_usdt": "bad"},
            {"timestamp_ms": 4000, "equity_usdt": 0.0},
            {"timestamp_ms": 5000, "equity_usdt": -10.0},
            {"timestamp_ms": 2000, "equity_usdt": "900.123456"},
        ]
        report = self.build()
        self.assertEqual(101.0, report["max_drawdown_pct"])
        self.assertEqual(101.0, report["max_loss_from_start_pct"])
        self.assertEqual([900.1235], [r["equity"] for r in report["equity_chart_rows"]])


class HedgeOverviewPageBoundaryTests(unittest.TestCase):
    def test_page_renders_prepared_report_and_writes_only_to_selected_target(self) -> None:
        backend = Mock(spec=content.FuturesHedgeOverviewContentService)
        prepared = {"prepared": "backend-owned"}
        backend.build_page_content.return_value = prepared
        page = FuturesHedgeOverviewPageService(content_service=backend)
        module = "platform_v2.futures_hedge.dashboard.overview_hedge.py.page_builder"
        with TemporaryDirectory() as folder, patch(module + ".FuturesHedgeOverviewRenderer") as renderer:
            page._TARGET_DIR = Path(folder) / "preview"
            page._TARGET_PATH = page._TARGET_DIR / "index.html"
            renderer.return_value.render.return_value = "<html><body>Prepared</body></html>"
            output = page.build_and_store()
            backend.build_page_content.assert_called_once_with()
            renderer.return_value.render.assert_called_once_with(prepared)
            self.assertEqual(page._TARGET_PATH, output)
            self.assertIn("Prepared", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
