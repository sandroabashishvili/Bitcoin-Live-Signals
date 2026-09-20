"""Tests for backend duplication, ownership, and unreachable-code checks."""

from __future__ import annotations

from pathlib import Path
import tempfile
from unittest.mock import patch

from platform_v2.tools.diagnostics.checks import backend_architecture_checks as checks


def _write(root: Path, relative: str, source: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_detects_unreachable_code_after_return() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / "platform_v2"
        path = _write(
            root,
            "futures/services/example.py",
            "def value():\n    return 1\n    print('never')\n",
        )
        with patch.object(checks, "V2_ROOT", root):
            findings = checks.backend_architecture_findings([path])
        assert any(item.issue == "unreachable_python_code" for item in findings)


def test_detects_exact_duplicate_function_bodies_across_modules() -> None:
    source = (
        "def normalize(value):\n"
        "    if value is None:\n"
        "        return 0\n"
            "    number = float(value)\n"
            "    if number < 0:\n"
            "        return 0\n"
            "    if number > 100:\n"
            "        number = 100\n"
            "    normalized = round(number, 2)\n"
            "    if normalized == 0:\n"
            "        return 0\n"
            "    return normalized\n"
        )
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / "platform_v2"
        first = _write(root, "spot/services/first.py", source)
        second = _write(root, "futures/services/second.py", source)
        with patch.object(checks, "V2_ROOT", root):
            findings = checks.backend_architecture_findings([first, second])
        assert any(item.issue == "duplicate_backend_function_body" for item in findings)


def test_shared_backend_cannot_import_strategy_modules() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / "platform_v2"
        path = _write(
            root,
            "shared/backend/bad_owner.py",
            "from platform_v2.futures.services.signal import FuturesSignalDecisionService\n",
        )
        with patch.object(checks, "V2_ROOT", root):
            findings = checks.backend_architecture_findings([path])
        assert any(item.issue == "shared_backend_strategy_dependency" for item in findings)
