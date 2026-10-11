import unittest

from platform_v2.shared.backend.chart_payloads import (
    build_equity_chart_payload, build_gate_chart_payload, build_orderflow_chart_rows,
)
from platform_v2.spot.services.analytics.strategy_effectiveness.gate_stats import build_closed_trade_group_rows


class ChartPayloadTests(unittest.TestCase):
    def test_directional_theoretical_counts_match_both_gate_types(self):
        logic = {"long_primary_totals": {"tp": 99, "sl": 116, "open": 14},
                 "long_confirmation_totals": {"tp": 59, "sl": 79, "open": 15},
                 "short_primary_totals": {"tp": 797, "sl": 1708, "open": 17},
                 "short_confirmation_totals": {"tp": 299, "sl": 889, "open": 13}}
        long, short = build_gate_chart_payload(logic, directional=True)["charts"]
        self.assertEqual(("LONG", 382), (long["title"], long["total"]))
        self.assertEqual(("SHORT", 3723), (short["title"], short["total"]))
        self.assertEqual(2597, short["outcomes"][1]["value"])
        self.assertAlmostEqual(100 * 1096 / 3693, short["win_rate"], places=4)

    def test_futures_profit_lock_retained(self):
        logic = {"chart_mode": "outcomes", "primary_totals": {
            "tp": 41, "sl": 96, "profit_lock": 12, "force_close": 0,
            "wins": 53, "participated": 149, "win_rate": 999}}
        chart = build_gate_chart_payload(logic)["charts"][0]
        self.assertEqual(149, chart["total"])
        self.assertEqual(12, chart["outcomes"][2]["value"])
        self.assertEqual("35.6%", chart["win_rate_text"])
        self.assertAlmostEqual(100, sum(r["percent"] for r in chart["outcomes"]), places=3)

    def test_spot_legacy_lock_normalized_and_weighted(self):
        chart = build_gate_chart_payload({"chart_mode": "outcomes", "primary_totals": {
            "tp": 14, "sl": 37, "lock": 16, "wins": 25, "win_rate": 31.81}})["charts"][0]
        self.assertEqual(67, chart["total"])
        self.assertEqual("37.3%", chart["win_rate_text"])
        self.assertEqual("Profit Lock", chart["outcomes"][2]["name"])

    def test_empty_data_never_invents_counts(self):
        for chart in build_gate_chart_payload({})["charts"]:
            self.assertFalse(chart["has_data"])
            self.assertEqual("—", chart["win_rate_text"])
            self.assertEqual(0, sum(o["value"] for o in chart["outcomes"]))

    def test_open_outcomes_have_unknown_win_rate(self):
        chart = build_gate_chart_payload({"primary_totals": {"open": 3}})["charts"][0]
        self.assertTrue(chart["has_data"])
        self.assertIsNone(chart["win_rate"])

    def test_missing_closed_wins_does_not_guess_from_tp(self):
        chart = build_gate_chart_payload({"chart_mode": "outcomes", "primary_totals": {"tp": 2}})["charts"][0]
        self.assertIsNone(chart["win_rate"])

    def test_equity_only_real_points_sorted_and_negative_equity_retained(self):
        result = build_equity_chart_payload([
            {"datetime": "2026-10-10T01:00:00Z", "starting_capital": 1000, "equity": -100},
            {"datetime": "2026-10-10T00:00:00Z", "starting_capital": 1000, "equity": 1200}])
        self.assertEqual(2, len(result["rows"]))
        self.assertEqual([20, -110], [r["delta_pct"] for r in result["rows"]])
        self.assertEqual(-1100, result["rows"][-1]["delta_abs"])
        self.assertEqual(-137.5, result["axis_min"])
        self.assertEqual(20, result["max_point"][1])

    def test_equity_missing_nonfinite_and_zero_baseline_skipped(self):
        result = build_equity_chart_payload([
            {"date": "2026-10-10", "starting_capital": 1000, "equity": None},
            {"date": "2026-10-10", "starting_capital": 1000, "equity": float('nan')},
            {"date": "2026-10-10", "starting_capital": 0, "equity": 100}])
        self.assertEqual([], result["rows"])
        self.assertIsNone(result["min_point"])

    def test_orderflow_uses_authoritative_values_and_preserves_baseline(self):
        rows = build_orderflow_chart_rows([{"timestamp_text": "2026-10-10 12:00:00",
            "buyers": "6.62", "sellers": "12.14", "delta": "-5.51", "cumulative_delta": "78.54"}])
        self.assertEqual(-5.51, rows[0]["delta_value"])
        self.assertEqual(78.54, rows[0]["positive_cumulative"])
        self.assertIsNone(rows[0]["negative_cumulative"])

    def test_orderflow_missing_metric_not_recomputed(self):
        self.assertEqual([], build_orderflow_chart_rows([{"timestamp_text": "2026-10-10 12:00:00", "buyers": 3, "sellers": 2}]))

    def test_spot_service_aggregate_uses_wins_over_participations(self):
        rows, totals = build_closed_trade_group_rows(("small", "large"), {
            "small": {"participated": 1, "tp": 1, "sl": 0, "force_close": 0, "lock": 0, "wins": 1, "win_rate": 100},
            "large": {"participated": 9, "tp": 0, "sl": 9, "force_close": 0, "lock": 0, "wins": 0, "win_rate": 0}})
        self.assertEqual(10, totals["win_rate"])


if __name__ == "__main__":
    unittest.main()
