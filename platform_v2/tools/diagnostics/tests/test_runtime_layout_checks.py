from __future__ import annotations

from pathlib import Path
import tempfile
from unittest.mock import patch

from platform_v2.tools.diagnostics.checks import runtime_layout_checks


def test_central_runtime_layout_is_clean() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / "platform_v2"
        (root / "shared" / "backend" / "runtime_store").mkdir(parents=True)
        with patch.object(runtime_layout_checks, "V2_ROOT", root):
            assert runtime_layout_checks.runtime_layout_findings() == []


def test_legacy_runtime_layout_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / "platform_v2"
        (root / "shared" / "backend" / "runtime_store").mkdir(parents=True)
        (root / "spot" / "runtime_ledger").mkdir(parents=True)
        with patch.object(runtime_layout_checks, "V2_ROOT", root):
            findings = runtime_layout_checks.runtime_layout_findings()
        assert any(item.issue == "legacy_runtime_layout" for item in findings)
