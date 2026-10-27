from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from platform_v2.tools.analytics_system import baseline, cli
from platform_v2.tools.analytics_system.baseline import BaselineDataRoots, build_baseline, _number, _performance_summary


class BaselineTests(unittest.TestCase):
    def test_cli_defaults_to_sqlite_and_does_not_mix_partial_json_roots(self) -> None:
        with patch("sys.argv", ["analytics", "baseline"]), patch.object(cli, "build_baseline", return_value={}) as build, patch.object(cli, "write_baseline", return_value=[]):
            self.assertEqual(cli.main(), 0)
            self.assertTrue(build.call_args.args[0].database_primary)
        with patch("sys.argv", ["analytics", "baseline", "--spot-data", "/tmp/export"]), patch.object(cli, "build_baseline") as build:
            with self.assertRaises(SystemExit) as caught:
                cli.main()
            self.assertEqual(caught.exception.code, 2)
            build.assert_not_called()

    def test_cli_explicit_json_roots_remain_supported(self) -> None:
        with patch("sys.argv", ["analytics", "baseline", "--spot-data", "/tmp/s", "--futures-data", "/tmp/f", "--hedge-data", "/tmp/h"]), patch.object(cli, "build_baseline", return_value={}) as build, patch.object(cli, "write_baseline", return_value=[]):
            cli.main()
            self.assertFalse(build.call_args.args[0].database_primary)

    def test_cli_fails_missing_data_but_still_writes_report(self) -> None:
        with patch("sys.argv", ["analytics", "baseline"]), patch.object(cli, "build_baseline", return_value={"data_available": {"spot": False}}), patch.object(cli, "write_baseline", return_value=[]) as write:
            self.assertEqual(cli.main(), 1)
            write.assert_called_once()

    def test_missing_and_invalid_inputs_are_not_successful_zero_counts(self) -> None:
        for value in (None, "invalid", float("nan"), float("inf")):
            self.assertIsNone(_number(value))
        self.assertEqual(_number(0), 0)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = build_baseline(BaselineDataRoots(root, root, root))
            self.assertFalse(any(report['data_available'].values()))
            self.assertIsNone(report['hedge']['equity'])
            self.assertNotIn('consistency_checks', report)

    def test_outcomes_deduplicate_updates_and_separate_sides(self):
        report = _performance_summary([
            {'position_id': '1', 'status': 'OPEN', 'side': 'LONG'},
            {'position_id': '1', 'status': 'CLOSED', 'side': 'LONG', 'net_pnl': 2.},
            {'position_id': '2', 'status': 'CLOSED', 'side': 'SHORT', 'net_pnl': -1.},
            {'position_id': '3', 'status': 'CLOSED', 'side': 'SHORT', 'net_pnl': 0.},
            {'position_id': '4', 'status': 'CLOSED', 'side': 'SHORT', 'net_pnl': None},
        ])
        self.assertEqual(report['total_positions'], 4)
        self.assertEqual(report['valid_net_outcomes'], 3)
        self.assertEqual(report['missing_net_outcomes'], 1)
        self.assertEqual(report['net_pnl'], 1)
        self.assertEqual(report['profit_factor'], 2)
        self.assertEqual(report['breakeven'], 1)
        self.assertEqual(report['by_side']['LONG']['wins'], 1)
        self.assertEqual(report['by_side']['SHORT']['losses'], 1)
        self.assertIsNone(report['by_side']['LONG']['profit_factor'])

    def test_invalid_report_dates_are_rejected_before_any_service_runs(self):
        for value in ('2026-02-30', '26-10-2026', '20261026'):
            with self.assertRaises(SystemExit):
                cli.build_parser().parse_args(['futures-gates', '--date', value])

    def test_report_renders_descriptive_results_not_health_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = build_baseline(BaselineDataRoots(root, root, root))
            paths = baseline.write_baseline(report, root / 'output')
            saved = json.loads(paths[0].read_text())
            text = paths[1].read_text()
            self.assertEqual(saved['report_version'], 2)
            self.assertIn('Closed-trade outcomes', text)
            self.assertNotIn('Consistency checks', text)
            self.assertIn('Source available: False', text)

    def test_database_mode_reads_documents_not_json_directories(self) -> None:
        with patch.object(baseline, "load_latest_spot_document", return_value={"equity": 123}), patch.object(baseline, "load_latest_futures_document", return_value={"equity": 456}), patch.object(baseline, "load_latest_hedge_document", return_value=[]), patch.object(baseline, "load_spot_rows_all", return_value=[]), patch.object(baseline, "load_futures_rows_all", return_value=[]), patch.object(baseline, "load_hedge_rows_all", return_value=[]), patch.object(baseline, "list_documents", return_value=[{"system": "spot", "date_iso": "2026-10-18"}, {"system": "futures", "date_iso": "2026-10-26"}]), patch.object(baseline, "_latest_dict", side_effect=AssertionError("JSON read")):
            report = build_baseline(BaselineDataRoots.live())
        self.assertEqual(report['spot']['equity'], 123)
        self.assertEqual(report['futures']['equity'], 456)
        self.assertEqual(report['storage_mode'], 'sqlite')
        self.assertEqual(report['date_range'], {'start': '2026-10-18', 'end': '2026-10-26'})

    def test_builds_cross_system_report_without_writing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            roots = BaselineDataRoots(root / "spot", root / "futures", root / "hedge")
            self._write_dict(
                roots.spot / "metrics" / "metrics_2026-01-01.json",
                {"force_close_events": 1, "equity": 3001},
            )
            self._write_list(roots.spot / "force_closes" / "force_closes_2026-01-01.json", [{}])
            self._write_dict(
                roots.futures / "futures_metrics" / "futures_metrics_2026-01-01.json",
                {"closed_positions": 1, "trades_opened_since_start": 2, "equity": 2990},
            )
            self._write_list(
                roots.futures / "futures_trade_entry_audits" / "futures_trade_entry_audits_2026-01-01.json",
                [{"position_id": "FUT-1"}],
            )
            self._write_list(
                roots.hedge / "hedge_entries" / "hedge_entries_2026-01-01.json",
                [{"hedge_entry_id": "H-1"}, {"hedge_entry_id": "H-2"}],
            )
            self._write_list(
                roots.hedge / "hedge_reset_events" / "hedge_reset_events_2026-01-01.json",
                [{"reset_id": 1}],
            )
            self._write_list(
                roots.hedge / "hedge_daily_summaries" / "hedge_daily_summaries_2026-01-01.json",
                [{"date": "2026-01-01", "hedge_entries_accepted": 2, "reset_count": 1}],
            )

            before = sorted(str(path) for path in root.rglob("*"))
            report = build_baseline(roots)
            after = sorted(str(path) for path in root.rglob("*"))

            self.assertEqual(before, after)
            self.assertTrue(all(report['data_available'].values()))
            self.assertNotIn('consistency_checks', report)
            self.assertEqual(report['report_version'], 2)

    @staticmethod
    def _write_dict(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _write_list(path: Path, payload: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
