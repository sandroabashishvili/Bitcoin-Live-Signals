"""Tests for canonical Spot setup confidence normalization."""

from __future__ import annotations

import pytest

from platform_v2.spot.services.trading.setup_confidence import normalized_setup_confidence


def test_setup_confidence_uses_execution_baseline() -> None:
    assert normalized_setup_confidence(9.0) == 0.5


@pytest.mark.parametrize(
    ("score", "expected"),
    ((-1.0, 0.0), (0.0, 0.0), (18.0, 1.0), (20.0, 1.0)),
)
def test_setup_confidence_is_bounded(score: float, expected: float) -> None:
    assert normalized_setup_confidence(score) == expected
