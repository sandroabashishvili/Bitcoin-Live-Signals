"""Contract tests for both Hedge equity risk measures."""
import unittest

from platform_v2.futures_hedge.services.equity_risk import equity_risk_metrics


class EquityRiskTests(unittest.TestCase):
    def metrics(self, values):
        return equity_risk_metrics([
            {"timestamp_ms": i * 1000, "equity_usdt": value}
            for i, value in enumerate(values, 1)
        ], 1000.0)

    def test_profit_then_drop(self):
        result = self.metrics([1000, 1500, 1200])
        self.assertEqual(20.0, result["max_drawdown_pct"])
        self.assertEqual(0.0, result["max_loss_from_start_pct"])

    def test_starting_capital_counts_as_initial_peak(self):
        result = self.metrics([900, 800])
        self.assertEqual(20.0, result["max_drawdown_pct"])
        self.assertEqual(20.0, result["max_loss_from_start_pct"])

    def test_chronology_and_multiple_peaks(self):
        rows = [{"timestamp_ms": i * 1000, "equity_usdt": value} for i, value in enumerate([1000, 1500, 1200, 2000, 1900], 1)]
        self.assertEqual(20.0, equity_risk_metrics(list(reversed(rows)), 1000)["max_drawdown_pct"])

    def test_missing_invalid_and_nonfinite_values_are_not_zero_equity(self):
        result = self.metrics([1000, None, "bad", float("nan"), float("inf"), 900])
        self.assertEqual(10.0, result["max_drawdown_pct"])
        self.assertEqual(10.0, result["max_loss_from_start_pct"])

    def test_zero_and_negative_equity_are_real_losses(self):
        self.assertEqual(100.0, self.metrics([1000, 0])["max_drawdown_pct"])
        self.assertEqual(110.0, self.metrics([1000, -100])["max_drawdown_pct"])

    def test_missing_market_time_and_history_are_unknown(self):
        self.assertIsNone(equity_risk_metrics([{"equity_usdt": 0}], 1000)["max_drawdown_pct"])
        self.assertIsNone(self.metrics([])["max_loss_from_start_pct"])

    def test_invalid_baseline_is_unknown(self):
        rows = [{"timestamp_ms": 1000, "equity_usdt": 900}]
        for capital in (0, -1, float("nan"), float("inf")):
            self.assertIsNone(equity_risk_metrics(rows, capital)["max_drawdown_pct"])


if __name__ == "__main__":
    unittest.main()
