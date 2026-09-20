from __future__ import annotations

import pytest

from platform_v2.tools.github_publish_system.validation import validate_analytics_ids


def test_analytics_validation_accepts_expected_id(tmp_path) -> None:
    (tmp_path / "index.html").write_text(
        '<script data-measurement-id="G-CURRENT123"></script>',
        encoding="utf-8",
    )

    validate_analytics_ids(roots=(tmp_path,), expected_id="G-CURRENT123")


def test_analytics_validation_reports_source_file_with_wrong_id(tmp_path) -> None:
    page = tmp_path / "generated.html"
    page.write_text('<script data-measurement-id="G-STALE123"></script>', encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"generated\.html: G-STALE123"):
        validate_analytics_ids(roots=(tmp_path,), expected_id="G-CURRENT123")
