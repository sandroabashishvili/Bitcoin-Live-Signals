from __future__ import annotations

import unittest

from platform_v2.tools.research.replay.spot_entry_quality_what_if import (
    _missing_gate_filter_matches,
)


class SpotGateFilterTests(unittest.TestCase):
    def test_any_and_all_missing_gate_modes(self) -> None:
        row = {"missing_gates": ["MTF", "STRUCTURE"]}
        self.assertTrue(
            _missing_gate_filter_matches(
                row,
                block_missing_gates={"MTF", "ORDERBOOK"},
                require_all_missing_gates=False,
            )
        )
        self.assertFalse(
            _missing_gate_filter_matches(
                row,
                block_missing_gates={"MTF", "ORDERBOOK"},
                require_all_missing_gates=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
