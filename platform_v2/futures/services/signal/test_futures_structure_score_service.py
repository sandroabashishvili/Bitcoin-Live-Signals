"""Regression tests for Futures structure component scoring."""

from types import SimpleNamespace

from platform_v2.futures.services.signal.futures_component_score_service import (
    FuturesComponentScoreService,
)
from platform_v2.futures.services.signal.futures_structure_score_service import (
    FuturesStructureScoreService,
)


def _snapshot(**overrides):
    values = {
        "atr": 100.0,
        "swing_low": 900.0,
        "swing_high": 1_200.0,
        "bounce_confirmed": False,
        "extras": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_component_service_preserves_long_structure_facade() -> None:
    snapshot = _snapshot()

    expected = FuturesStructureScoreService.long_score(snapshot, 1_000.0, False)

    assert FuturesComponentScoreService.long_structure_score(snapshot, 1_000.0, False) == expected


def test_component_service_preserves_short_structure_facade() -> None:
    snapshot = _snapshot(extras={"rejection_confirmed": True})

    expected = FuturesStructureScoreService.short_score(snapshot, 1_000.0, False)

    assert FuturesComponentScoreService.short_structure_score(snapshot, 1_000.0, False) == expected


def test_atr_spike_blocks_structure_scores() -> None:
    snapshot = _snapshot()

    assert FuturesStructureScoreService.long_score(snapshot, 1_000.0, True) == 0.0
    assert FuturesStructureScoreService.short_score(snapshot, 1_000.0, True) == 0.0


def test_missing_atr_has_no_structure_score() -> None:
    snapshot = _snapshot(atr=None)

    assert FuturesStructureScoreService.long_score(snapshot, 1_000.0, False) == 0.0
    assert FuturesStructureScoreService.short_score(snapshot, 1_000.0, False) == 0.0
