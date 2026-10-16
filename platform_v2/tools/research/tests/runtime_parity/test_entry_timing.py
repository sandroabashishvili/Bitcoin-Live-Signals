from platform_v2.futures.domain.entry_timing import classify_entry_timing


def test_true_flip_requires_an_opposite_prior_actionable_direction() -> None:
    result = classify_entry_timing(
        side="SHORT",
        prior_sides=["LONG", "NO_SIGNAL"],
    )
    assert result.timing_type == "FRESH_FLIP"
    assert result.prior_actionable_side == "LONG"


def test_same_direction_after_no_signal_is_reentry_not_flip() -> None:
    result = classify_entry_timing(
        side="SHORT",
        prior_sides=["SHORT", "NO_SIGNAL"],
    )
    assert result.timing_type == "FRESH_REENTRY"
    assert result.prior_actionable_side == "SHORT"


def test_first_actionable_direction_is_fresh_signal_not_flip() -> None:
    result = classify_entry_timing(side="LONG", prior_sides=["NO_SIGNAL"])
    assert result.timing_type == "FRESH_SIGNAL"
    assert result.prior_actionable_side is None


def test_second_signal_keeps_transition_origin() -> None:
    result = classify_entry_timing(
        side="LONG",
        prior_sides=["SHORT", "NO_SIGNAL", "LONG"],
    )
    assert result.timing_type == "FRESH_FLIP"
    assert result.direction_signal_age == 2
