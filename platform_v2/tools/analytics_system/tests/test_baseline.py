from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from platform_v2.tools.analytics_system.baseline import BaselineDataRoots, build_baseline


class BaselineTests(unittest.TestCase):
    def test_builds_cross_system_consistency_checks_without_writing_inputs(self) -> None:
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
            self.assertTrue(all(check["status"] == "pass" for check in report["consistency_checks"]))

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
