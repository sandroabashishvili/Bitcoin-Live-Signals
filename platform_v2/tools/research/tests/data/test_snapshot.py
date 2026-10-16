from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from platform_v2.tools.research.paths import ResearchDataRoots
from platform_v2.tools.research.snapshot import create_snapshot, verify_snapshot


class ResearchSnapshotTests(unittest.TestCase):
    def test_snapshot_copies_only_json_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sources = ResearchDataRoots(root / "live-spot", root / "live-futures", root / "live-hedge")
            for source in (sources.spot, sources.futures, sources.hedge):
                source.mkdir()
                (source / "family").mkdir()
                (source / "family" / "rows_2026-01-01.json").write_text(
                    json.dumps([{"value": source.name}]),
                    encoding="utf-8",
                )
                (source / "ignored.txt").write_text("not copied", encoding="utf-8")

            snapshot = create_snapshot(source_roots=sources, snapshot_parent=root / "snapshots")
            self.assertEqual([], verify_snapshot(snapshot))
            self.assertFalse((snapshot / "spot" / "data" / "ignored.txt").exists())

            copied = snapshot / "spot" / "data" / "family" / "rows_2026-01-01.json"
            copied.write_text("[]", encoding="utf-8")
            self.assertTrue(any("hash mismatch" in item for item in verify_snapshot(snapshot)))


if __name__ == "__main__":
    unittest.main()
