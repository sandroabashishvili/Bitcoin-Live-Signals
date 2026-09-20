from __future__ import annotations

import json

from platform_v2.tools.diagnostics.checks import runtime_duplication_checks


def test_cross_family_duplicate_rows_are_reported(tmp_path, monkeypatch) -> None:
    runtime_root = tmp_path / "futures"
    for family in ("events", "positions"):
        folder = runtime_root / "data" / family
        folder.mkdir(parents=True)
        (folder / f"{family}_2026-08-01.json").write_text(
            json.dumps([{"position_id": "F-1", "status": "OPEN"}]),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        runtime_duplication_checks,
        "system_runtime_root",
        lambda system: runtime_root if system == "futures" else tmp_path / system,
    )
    findings = runtime_duplication_checks.runtime_cross_family_duplication_findings()
    assert [finding.issue for finding in findings] == ["cross_family_exact_duplicate_rows"]
