from platform_v2.futures.domain.flip_confirmation import FlipConfirmationTracker


STEP = 15 * 60 * 1000


def test_flip_opens_only_after_same_side_next_candle() -> None:
    tracker = FlipConfirmationTracker(required_sides={"LONG", "SHORT"}, timeframe_ms=STEP)
    assert tracker.observe(side="LONG", timestamp_ms=0).allowed
    pending = tracker.observe(side="SHORT", timestamp_ms=STEP)
    confirmed = tracker.observe(side="SHORT", timestamp_ms=2 * STEP)
    assert not pending.allowed
    assert pending.status == "PENDING_FLIP"
    assert confirmed.allowed
    assert confirmed.status == "CONFIRMED_FLIP"


def test_no_signal_cancels_pending_flip() -> None:
    tracker = FlipConfirmationTracker(required_sides={"LONG", "SHORT"}, timeframe_ms=STEP)
    tracker.observe(side="LONG", timestamp_ms=0)
    assert not tracker.observe(side="SHORT", timestamp_ms=STEP).allowed
    tracker.observe(side="NO_SIGNAL", timestamp_ms=2 * STEP)
    assert not tracker.observe(side="SHORT", timestamp_ms=3 * STEP).allowed


def test_return_to_confirmed_side_cancels_pending_flip() -> None:
    tracker = FlipConfirmationTracker(required_sides={"LONG", "SHORT"}, timeframe_ms=STEP)
    tracker.observe(side="LONG", timestamp_ms=0)
    assert not tracker.observe(side="SHORT", timestamp_ms=STEP).allowed
    result = tracker.observe(side="LONG", timestamp_ms=2 * STEP)
    assert result.allowed
    assert result.status == "CONFIRMED_DIRECTION"


def test_direction_specific_candidate_leaves_other_side_unfiltered() -> None:
    tracker = FlipConfirmationTracker(required_sides={"LONG"}, timeframe_ms=STEP)
    tracker.observe(side="LONG", timestamp_ms=0)
    result = tracker.observe(side="SHORT", timestamp_ms=STEP)
    assert result.allowed
    assert result.status == "UNFILTERED_FLIP"
