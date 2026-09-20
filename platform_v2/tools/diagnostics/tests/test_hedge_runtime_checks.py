from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from platform_v2.shared.backend.runtime_store.families.hedge import ALL_FAMILIES
from platform_v2.tools.diagnostics.checks.hedge_runtime_checks import (
    hedge_runtime_integrity_findings,
    hedge_runtime_schema_findings,
    hedge_runtime_structure_findings,
)


class HedgeRuntimeChecksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.data_root = Path(self.temp.name)
        for family in ALL_FAMILIES:
            (self.data_root / family).mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_structure_detects_missing_family(self) -> None:
        (self.data_root / ALL_FAMILIES[0]).rmdir()
        findings = hedge_runtime_structure_findings(self.data_root)
        self.assertEqual(["missing_runtime_family_dir"], [item.issue for item in findings])

    def test_schema_detects_missing_keys(self) -> None:
        self._write("hedge_entries", [{"hedge_entry_id": "HEDGE-1"}])
        findings = hedge_runtime_schema_findings(self.data_root)
        self.assertEqual(1, len(findings))
        self.assertEqual("runtime_missing_keys", findings[0].issue)
        self.assertIn("source_position_id", findings[0].detail)

    def test_integrity_detects_duplicate_and_orphan(self) -> None:
        entry = {"hedge_entry_id": "HEDGE-1", "source_position_id": "FUT-1"}
        self._write("hedge_entries", [entry, entry])
        self._write(
            "hedge_basket_snapshots",
            [{"snapshot_id": "SNAP-1", "hedge_entry_id": "MISSING"}],
        )
        findings = hedge_runtime_integrity_findings(self.data_root)
        issues = {item.issue for item in findings}
        self.assertIn("duplicate_hedge_runtime_id", issues)
        self.assertIn("orphan_hedge_snapshot", issues)

    def _write(self, family: str, rows: list[dict[str, object]]) -> None:
        path = self.data_root / family / f"{family}_2026-07-30.json"
        path.write_text(json.dumps(rows), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
