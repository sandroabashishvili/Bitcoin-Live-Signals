"""Cohort audit for positions admitted by the state-aware baseline replay."""

from __future__ import annotations

from math import inf
from typing import Any

from platform_v2.tools.research.replay.candidate_signal_outcome_replay import _stats


NUMERIC_BINS: dict[str, tuple[float, ...]] = {
    "score": (8.5, 9.0, 9.5, 10.0, 11.0, inf),
    "rsi": (0, 30, 35, 40, 50, 58, 65, 100),
    "adx": (0, 18, 20, 25, 30, 40, inf),
    "atr_growth_20": (-inf, -0.2, -0.05, 0.05, 0.2, 0.5, inf),
    "directional_di_delta": (-inf, -8, 0, 8, 20, inf),
    "directional_macd_spread_atr": (-inf, -0.2, 0, 0.2, 0.5, inf),
    "entry_from_swing_atr": (-inf, 0, 1, 1.5, 2.5, 4, inf),
    "room_to_opposite_swing_atr": (-inf, 0, 0.5, 1, 1.5, 2.5, 4, inf),
    "stop_distance_atr": (0, 0.8, 1.0, 1.5, 2.0, 2.5, 3.5, inf),
    "target_distance_atr": (0, 1.0, 1.5, 2.0, 3.0, 4.0, inf),
    "effective_rr": (0, 1.5, 1.8, 2.0, 2.2, 2.5, inf),
}


def build_outcome_audit(
    outcomes: list[dict[str, Any]],
    *,
    split_timestamp_ms: int,
) -> dict[str, Any]:
    direction_reports: dict[str, Any] = {}
    for side in ("LONG", "SHORT"):
        rows = [row for row in outcomes if str(row.get("side") or "").upper() == side]
        cohorts: list[dict[str, Any]] = []
        for feature, edges in NUMERIC_BINS.items():
            for lower, upper in zip(edges, edges[1:]):
                selected = [
                    row
                    for row in rows
                    if (value := _feature_value(row, feature)) is not None and lower <= value < upper
                ]
                if selected:
                    cohorts.append(
                        _cohort(
                            feature=feature,
                            value=_band(lower, upper),
                            rows=selected,
                            split_timestamp_ms=split_timestamp_ms,
                        )
                    )
        for feature in ("timing_type", "gate_count"):
            values = sorted({str(row.get(feature)) for row in rows if row.get(feature) is not None})
            for value in values:
                cohorts.append(
                    _cohort(
                        feature=feature,
                        value=value,
                        rows=[row for row in rows if str(row.get(feature)) == value],
                        split_timestamp_ms=split_timestamp_ms,
                    )
                )
        direction_reports[side] = {
            "all": _stats(rows),
            "stable_negative": sorted(
                [row for row in cohorts if row["stability"] == "negative"],
                key=lambda row: float(row["all"]["net_pnl"]),
            ),
            "stable_positive": sorted(
                [row for row in cohorts if row["stability"] == "positive"],
                key=lambda row: float(row["all"]["net_pnl"]),
                reverse=True,
            ),
            "cohorts": cohorts,
        }
    return direction_reports


def _cohort(
    *,
    feature: str,
    value: str,
    rows: list[dict[str, Any]],
    split_timestamp_ms: int,
) -> dict[str, Any]:
    train = [row for row in rows if int(row.get("entry_timestamp_ms") or 0) <= split_timestamp_ms]
    test = [row for row in rows if int(row.get("entry_timestamp_ms") or 0) > split_timestamp_ms]
    train_stats = _stats(train)
    test_stats = _stats(test)
    stability = "insufficient"
    if train_stats["trades"] >= 3 and test_stats["trades"] >= 3:
        if train_stats["net_pnl"] > 0 and test_stats["net_pnl"] > 0:
            stability = "positive"
        elif train_stats["net_pnl"] < 0 and test_stats["net_pnl"] < 0:
            stability = "negative"
        else:
            stability = "mixed"
    return {
        "feature": feature,
        "value": value,
        "all": _stats(rows),
        "train": train_stats,
        "test": test_stats,
        "stability": stability,
    }


def _feature_value(row: dict[str, Any], feature: str) -> float | None:
    value = row.get(feature) if feature == "score" else (row.get("features") or {}).get(feature)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _band(lower: float, upper: float) -> str:
    lower_text = "-inf" if lower == -inf else f"{lower:g}"
    upper_text = "inf" if upper == inf else f"{upper:g}"
    return f"[{lower_text}, {upper_text})"
