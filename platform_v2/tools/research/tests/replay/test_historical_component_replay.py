from __future__ import annotations

from platform_v2.tools.research.replay.historical_component_replay import (
    _AsOfIndex,
    _cycle_decision_times,
    _indicator_index,
    _score,
    _single_weight_search,
    _timestamp_ms,
)
import json


def test_asof_index_never_reads_future_without_explicit_tolerance() -> None:
    index = _AsOfIndex([(1_000, "old"), (2_000, "new")])

    assert index.at(1_999) == "old"
    assert index.at(1_999, tolerance_ms=1) == "new"


def test_timestamp_parser_can_align_candle_close_to_millisecond() -> None:
    parsed = _timestamp_ms("2026-07-31 15:29:59", end_of_second=True)

    assert parsed == 1_785_511_799_999


def test_remove_one_score_excludes_only_selected_component() -> None:
    components = {"mtf": 2.0, "trend": 3.0, "regime": 1.0}
    weights = {"mtf": 1.0, "trend": 2.0, "regime": 0.5}

    assert _score(components, weights) == 8.5
    assert _score(components, weights, omit="trend") == 2.5


def test_cycle_decision_time_maps_candle_close_to_actual_runtime_time(tmp_path) -> None:
    (tmp_path / "cycle.json").write_text(
        json.dumps(
            [
                {
                    "cycle_note": "1785510899999",
                    "datetime": "2026-07-31 15:19:45",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert _cycle_decision_times(tmp_path) == {1_785_510_899_999: 1_785_511_185_000}


def test_single_weight_search_requires_positive_train_and_test() -> None:
    rows = []
    for index in range(15):
        rows.append(
            {
                "date": f"2026-07-{index + 1:02d}",
                "components": {"mtf": 9.0, "momentum": 2.0},
                "net_pnl": 1.0,
            }
        )

    result = _single_weight_search(
        rows,
        weights={"mtf": 1.0, "momentum": 1.0},
        baseline_threshold=8.5,
    )

    assert result["stable_positive_candidates"] > 0
    assert result["top_candidates"][0]["stable_positive"] is True


def test_indicator_index_can_repair_histogram_without_future_values(tmp_path) -> None:
    rows = [
        {"datetime": f"2026-07-31 00:0{index}:59", "macd": float(index), "macd_signal": 0.0}
        for index in range(4)
    ]
    (tmp_path / "15m.json").write_text(json.dumps(rows), encoding="utf-8")

    def parser(**kwargs):
        return kwargs["row"]

    index = _indicator_index(
        tmp_path / "15m.json",
        symbol="BTCUSDT",
        timeframe="15m",
        parser=parser,
        repair_macd_histogram=True,
    )

    assert index.values[0]["macd_histogram"] == [0.0]
    assert index.values[-1]["macd_histogram"] == [1.0, 2.0, 3.0]
