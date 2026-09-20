from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from platform_v2.tools.research.historical_indicators import build_spot_indicator_history


class HistoricalIndicatorTests(unittest.TestCase):
    def test_short_history_is_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candle_path = root / "data" / "candles" / "BTCUSDT" / "15m.json"
            candle_path.parent.mkdir(parents=True)
            candle_path.write_text(json.dumps([]), encoding="utf-8")
            paths = build_spot_indicator_history(
                spot_data_root=root / "data",
                output_root=root / "output",
                symbol="BTCUSDT",
                timeframes=["15m"],
                include_candidate_ema9=True,
            )
            self.assertEqual([], paths)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
