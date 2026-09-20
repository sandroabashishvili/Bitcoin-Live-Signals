"""Fail-fast checks for generated and publishable website files."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re


MEASUREMENT_ID_PATTERN = re.compile(r"G-[A-Z0-9]{6,}")
SCANNED_SUFFIXES = {".html", ".js", ".py"}


def validate_analytics_ids(*, roots: Iterable[Path], expected_id: str) -> None:
    """Reject unexpected Analytics IDs instead of rewriting generated output."""

    unexpected: list[tuple[Path, str]] = []
    found_expected = False
    for root in roots:
        if not root.exists():
            continue
        candidates = (root,) if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in SCANNED_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for measurement_id in MEASUREMENT_ID_PATTERN.findall(text):
                if measurement_id == expected_id:
                    found_expected = True
                else:
                    unexpected.append((path, measurement_id))

    if unexpected:
        details = "\n".join(f"- {path}: {measurement_id}" for path, measurement_id in unexpected)
        raise RuntimeError(
            f"Unexpected Google Analytics Measurement ID; expected {expected_id}:\n{details}"
        )
    if not found_expected:
        raise RuntimeError(f"Google Analytics Measurement ID {expected_id} was not found in publish sources.")
