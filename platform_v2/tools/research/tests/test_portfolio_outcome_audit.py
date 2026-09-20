from platform_v2.tools.research.replay.portfolio_outcome_audit import build_outcome_audit


def _row(timestamp, pnl, *, rsi=40.0):
    return {
        "entry_timestamp_ms": timestamp,
        "exit_timestamp_ms": timestamp + 1,
        "side": "SHORT",
        "score": 9.2,
        "timing_type": "FRESH_FLIP",
        "gate_count": 3,
        "resolution": "TP" if pnl > 0 else "SL",
        "net_pnl": pnl,
        "features": {
            "rsi": rsi,
            "adx": 25,
            "atr_growth_20": 0.1,
            "directional_di_delta": 10,
            "directional_macd_spread_atr": 0.1,
            "entry_from_swing_atr": 2,
            "room_to_opposite_swing_atr": 1,
        },
    }


def test_outcome_audit_marks_negative_cohort_in_both_segments() -> None:
    rows = [_row(index, -1.0) for index in (1, 2, 3, 11, 12, 13)]
    report = build_outcome_audit(rows, split_timestamp_ms=10)
    rsi = [row for row in report["SHORT"]["stable_negative"] if row["feature"] == "rsi"]
    assert rsi
    assert rsi[0]["all"]["trades"] == 6
