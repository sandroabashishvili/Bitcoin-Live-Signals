from __future__ import annotations

from platform_v2.tools.research.replay.futures_entry_quality_what_if import (
    _is_blocked,
)


def _row(*, timing: str, alignment: str) -> dict[str, object]:
    return {
        "side": "SHORT",
        "entry_timing_type": timing,
        "entry_market_plan_alignment": alignment,
        "entry_location_type": "CLEAN",
        "entry_signal": {"gates": {}},
    }


def _evaluate(row: dict[str, object]) -> tuple[bool, list[str]]:
    return _is_blocked(
        row,
        side="SHORT",
        block_timing=set(),
        block_side_location=set(),
        block_market_plan_alignment=set(),
        block_missing_gates=set(),
        require_all_missing_gates=False,
        max_signal_age=None,
        max_abs_ema50_atr=None,
        max_abs_vwap_atr=None,
        conjunction_timing={"FRESH_FLIP"},
        conjunction_market_plan_alignment={"IN_ZONE"},
    )


def test_conjunction_blocks_only_when_all_configured_fields_match() -> None:
    blocked, reasons = _evaluate(_row(timing="FRESH_FLIP", alignment="IN_ZONE"))

    assert blocked is True
    assert reasons == [
        "conjunction:timing=FRESH_FLIP,market_plan_alignment=IN_ZONE"
    ]


def test_conjunction_does_not_apply_to_partial_match() -> None:
    timing_only, timing_reasons = _evaluate(
        _row(timing="FRESH_FLIP", alignment="OUTSIDE_ZONE")
    )
    alignment_only, alignment_reasons = _evaluate(
        _row(timing="EARLY_CONTINUATION", alignment="IN_ZONE")
    )

    assert timing_only is False
    assert timing_reasons == []
    assert alignment_only is False
    assert alignment_reasons == []
