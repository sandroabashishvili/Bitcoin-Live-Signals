from __future__ import annotations

import json
import ast
from pathlib import Path
import tempfile
import unittest

from platform_v2.tools.diagnostics.checks.strategy_contract_checks import (
    spot_entry_location_contract_findings,
)
from platform_v2.tools.diagnostics.checks.dead_code_checks import (
    TopLevelDef,
    module_symbol_uses,
    should_skip_dead_candidate,
)
from platform_v2.tools.diagnostics.core.config import SCAN_ROOTS


class StrategyContractChecksTests(unittest.TestCase):
    def test_reports_missing_classifier_input(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "15m.json"
            path.write_text(json.dumps([{"atr": 1.0, "vwap": 100.0}]), encoding="utf-8")
            findings = spot_entry_location_contract_findings(path)
            self.assertEqual(1, len(findings))
            self.assertIn("ema9", findings[0].detail)

    def test_dead_code_scan_skips_pytest_functions(self) -> None:
        item = TopLevelDef(
            path=Path("/tmp/platform_v2/tools/research/tests/test_example.py"),
            name="test_expected_behavior",
            kind="function",
            lineno=1,
        )

        self.assertTrue(should_skip_dead_candidate(item))

    def test_dead_code_scan_counts_reexport_imports_as_symbol_uses(self) -> None:
        tree = ast.parse("from package.module import exported_helper\n")

        self.assertEqual(1, module_symbol_uses(tree)["exported_helper"])

    def test_diagnostics_scan_includes_futures_hedge(self) -> None:
        self.assertIn("futures_hedge", SCAN_ROOTS)


if __name__ == "__main__":
    unittest.main()
