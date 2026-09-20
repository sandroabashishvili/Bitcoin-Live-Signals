"""File: futures_short_zone_block_what_if.py
Folder: platform_v2/tools/research/replay
Created date: 2026-06-01
Last updated date: 2026-06-02
Author: Codex
Purpose: Report-only what-if audit for Futures SHORT market-plan zone blocks.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots

DATA_ROOT = ResearchDataRoots.live().futures
OUTPUT_ROOT = CANONICAL_OUTPUT_ROOT


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _load_signal_rows(dates: list[str], *, data_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date_iso in dates:
        path = data_root / "futures_signals" / f"futures_signals_{date_iso}.json"
        for row in _load_json_list(path):
            row = dict(row)
            row["_source_date"] = date_iso
            rows.append(row)
    rows.sort(key=lambda row: _safe_int(row.get("timestamp_ms")))
    return rows


def _load_candles(symbol: str, timeframe: str, *, data_root: Path) -> list[dict[str, Any]]:
    return _load_json_list(data_root / "candles_futures" / symbol / f"candles_{timeframe}.json")


def _short_zone_distance(row: dict[str, Any]) -> dict[str, Any]:
    permission = row.get("market_plan_permission")
    permission = permission if isinstance(permission, dict) else {}
    zone = permission.get("nearest_zone")
    zone = zone if isinstance(zone, dict) else {}
    entry = _safe_float(row.get("theoretical_setup", {}).get("entry_price") if isinstance(row.get("theoretical_setup"), dict) else row.get("snapshot_price"))
    zone_from = _safe_float(zone.get("from"))
    zone_to = _safe_float(zone.get("to"))
    if entry <= 0 or zone_from <= 0 or zone_to <= 0:
        return {"distance_points": 0.0, "position": "UNKNOWN"}
    if entry < zone_from:
        return {"distance_points": round(zone_from - entry, 2), "position": "BELOW_ZONE"}
    if entry > zone_to:
        return {"distance_points": round(entry - zone_to, 2), "position": "ABOVE_ZONE"}
    return {"distance_points": 0.0, "position": "IN_ZONE"}


def _is_continuation_candidate(row: dict[str, Any]) -> bool:
    permission = row.get("market_plan_permission")
    permission = permission if isinstance(permission, dict) else {}
    location = permission.get("plan_location")
    location = location if isinstance(location, dict) else {}
    entry_quality = row.get("entry_quality")
    entry_quality = entry_quality if isinstance(entry_quality, dict) else {}
    timing = str(entry_quality.get("timing_type") or "").upper()
    distance = _short_zone_distance(row)
    swing_low_atr = _safe_float(location.get("distance_to_swing_low_atr"))
    passed_gate_count = _passed_gate_count(row)
    score = _safe_float(row.get("score"))
    return (
        distance.get("position") == "BELOW_ZONE"
        and timing in {"FRESH_FLIP", "EARLY_CONTINUATION"}
        and swing_low_atr > 0.3
        and (passed_gate_count >= 3 or score >= 10.5)
    )


def _passed_gate_count(row: dict[str, Any]) -> int:
    gates = row.get("gates")
    gates = gates if isinstance(gates, dict) else {}
    return sum(1 for value in gates.values() if bool(value))


def _time_bucket(*, bars_to_outcome: int | None, timeframe_minutes: int) -> str:
    if bars_to_outcome is None:
        return "UNRESOLVED"
    minutes = bars_to_outcome * timeframe_minutes
    if minutes <= 12 * 60:
        return "<=12H"
    if minutes <= 24 * 60:
        return "<=24H"
    if minutes <= 48 * 60:
        return "<=48H"
    return ">48H"


def _future_outcome(
    *,
    row: dict[str, Any],
    candles: list[dict[str, Any]],
    max_lookahead_candles: int | None,
    timeframe_minutes: int,
) -> dict[str, Any]:
    setup = row.get("theoretical_setup")
    setup = setup if isinstance(setup, dict) else {}
    entry = _safe_float(setup.get("entry_price"))
    stop_loss = _safe_float(setup.get("stop_loss"))
    take_profit = _safe_float(setup.get("take_profit"))
    ts = _safe_int(row.get("timestamp_ms"))
    if entry <= 0 or stop_loss <= 0 or take_profit <= 0 or ts <= 0:
        return {
            "outcome": "NO_SETUP",
            "bars_to_outcome": None,
            "hours_to_outcome": None,
            "time_bucket": "NO_SETUP",
            "max_favorable_points": 0.0,
            "max_adverse_points": 0.0,
        }

    future = [candle for candle in candles if _safe_int(candle.get("close_time")) > ts]
    if max_lookahead_candles is not None:
        future = future[:max_lookahead_candles]
    max_favorable = 0.0
    max_adverse = 0.0
    for index, candle in enumerate(future, start=1):
        high = _safe_float(candle.get("high"))
        low = _safe_float(candle.get("low"))
        max_favorable = max(max_favorable, entry - low)
        max_adverse = max(max_adverse, high - entry)
        hit_tp = low <= take_profit
        hit_sl = high >= stop_loss
        if hit_tp and hit_sl:
            return {
                "outcome": "AMBIGUOUS_BOTH",
                "bars_to_outcome": index,
                "hours_to_outcome": round(index * timeframe_minutes / 60.0, 2),
                "time_bucket": _time_bucket(bars_to_outcome=index, timeframe_minutes=timeframe_minutes),
                "max_favorable_points": round(max_favorable, 2),
                "max_adverse_points": round(max_adverse, 2),
            }
        if hit_tp:
            return {
                "outcome": "TP",
                "bars_to_outcome": index,
                "hours_to_outcome": round(index * timeframe_minutes / 60.0, 2),
                "time_bucket": _time_bucket(bars_to_outcome=index, timeframe_minutes=timeframe_minutes),
                "max_favorable_points": round(max_favorable, 2),
                "max_adverse_points": round(max_adverse, 2),
            }
        if hit_sl:
            return {
                "outcome": "SL",
                "bars_to_outcome": index,
                "hours_to_outcome": round(index * timeframe_minutes / 60.0, 2),
                "time_bucket": _time_bucket(bars_to_outcome=index, timeframe_minutes=timeframe_minutes),
                "max_favorable_points": round(max_favorable, 2),
                "max_adverse_points": round(max_adverse, 2),
            }
    return {
        "outcome": "UNRESOLVED_TO_DATA_END",
        "bars_to_outcome": None,
        "hours_to_outcome": None,
        "time_bucket": "UNRESOLVED",
        "max_favorable_points": round(max_favorable, 2),
        "max_adverse_points": round(max_adverse, 2),
    }


def _filtered_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("selected_direction") or row.get("side") or "").upper() != "SHORT":
            continue
        if str(row.get("permission_reason") or "").lower() != "short_market_plan_zone_block":
            continue
        result.append(row)
    return result


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Futures SHORT Zone Block What-If",
        "",
        f"- `generated_at`: `{payload['generated_at']}`",
        f"- `dates`: `{', '.join(payload['dates'])}`",
        f"- `max_lookahead_candles`: `{payload['max_lookahead_candles']}`",
        f"- `timeframe_minutes`: `{payload['timeframe_minutes']}`",
        f"- `blocked_short_rows`: `{summary['blocked_short_rows']}`",
        f"- `continuation_candidates`: `{summary['continuation_candidates']}`",
        f"- `outcomes`: `{summary['outcomes']}`",
        f"- `time_buckets`: `{summary['time_buckets']}`",
        "",
        "## Interpretation",
        "",
        "Rows marked as continuation candidates were below the nearest short zone, but still had fresh or early SHORT timing, clean short location, and bearish EMA/VWAP location.",
        "This report does not change runtime behavior; it only shows whether the current hard block may be skipping useful continuation entries.",
        "",
        "## Sample Rows",
        "",
    ]
    for row in payload["sample_rows"]:
        lines.extend(
            [
                f"### {row['time_readable']}",
                "",
                f"- `score`: `{row['score']}`",
                f"- `entry`: `{row['entry_price']}`",
                f"- `zone`: `{row['nearest_zone']}`",
                f"- `zone_position`: `{row['zone_position']}`",
                f"- `distance_points`: `{row['distance_points']}`",
                f"- `timing`: `{row['timing_type']}`",
                f"- `continuation_candidate`: `{row['continuation_candidate']}`",
                f"- `outcome`: `{row['outcome']}`",
                f"- `bars_to_outcome`: `{row['bars_to_outcome']}`",
                f"- `hours_to_outcome`: `{row['hours_to_outcome']}`",
                f"- `time_bucket`: `{row['time_bucket']}`",
                f"- `max_favorable_points`: `{row['max_favorable_points']}`",
                f"- `max_adverse_points`: `{row['max_adverse_points']}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_report(
    *,
    dates: list[str],
    symbol: str,
    timeframe: str,
    max_lookahead_candles: int | None,
    timeframe_minutes: int,
    data_root: Path = DATA_ROOT,
) -> dict[str, Any]:
    rows = _filtered_rows(_load_signal_rows(dates, data_root=data_root))
    candles = _load_candles(symbol, timeframe, data_root=data_root)
    enriched: list[dict[str, Any]] = []
    outcomes: Counter[str] = Counter()
    time_buckets: Counter[str] = Counter()
    timing_counts: Counter[str] = Counter()
    continuation_outcomes: Counter[str] = Counter()
    continuation_time_buckets: Counter[str] = Counter()

    for row in rows:
        setup = row.get("theoretical_setup")
        setup = setup if isinstance(setup, dict) else {}
        permission = row.get("market_plan_permission")
        permission = permission if isinstance(permission, dict) else {}
        nearest_zone = permission.get("nearest_zone")
        nearest_zone = nearest_zone if isinstance(nearest_zone, dict) else {}
        entry_quality = row.get("entry_quality")
        entry_quality = entry_quality if isinstance(entry_quality, dict) else {}
        distance = _short_zone_distance(row)
        outcome = _future_outcome(
            row=row,
            candles=candles,
            max_lookahead_candles=max_lookahead_candles,
            timeframe_minutes=timeframe_minutes,
        )
        candidate = _is_continuation_candidate(row)
        timing_type = str(entry_quality.get("timing_type") or "UNKNOWN")
        result = {
            "time_readable": row.get("time_readable"),
            "timestamp_ms": row.get("timestamp_ms"),
            "score": row.get("score"),
            "entry_price": setup.get("entry_price"),
            "stop_loss": setup.get("stop_loss"),
            "take_profit": setup.get("take_profit"),
            "nearest_zone": {
                "name": nearest_zone.get("name"),
                "from": nearest_zone.get("from"),
                "to": nearest_zone.get("to"),
                "center": nearest_zone.get("center"),
            },
            "zone_position": distance["position"],
            "distance_points": distance["distance_points"],
            "timing_type": timing_type,
            "direction_signal_age": entry_quality.get("direction_signal_age"),
            "continuation_candidate": candidate,
            **outcome,
        }
        enriched.append(result)
        outcomes.update([str(outcome["outcome"])])
        time_buckets.update([str(outcome["time_bucket"])])
        timing_counts.update([timing_type])
        if candidate:
            continuation_outcomes.update([str(outcome["outcome"])])
            continuation_time_buckets.update([str(outcome["time_bucket"])])

    summary = {
        "blocked_short_rows": len(enriched),
        "continuation_candidates": sum(1 for row in enriched if row["continuation_candidate"]),
        "outcomes": dict(sorted(outcomes.items())),
        "time_buckets": dict(sorted(time_buckets.items())),
        "timing_counts": dict(sorted(timing_counts.items())),
        "continuation_candidate_outcomes": dict(sorted(continuation_outcomes.items())),
        "continuation_candidate_time_buckets": dict(sorted(continuation_time_buckets.items())),
    }
    return {
        "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
        "dates": dates,
        "symbol": symbol,
        "timeframe": timeframe,
        "max_lookahead_candles": max_lookahead_candles,
        "timeframe_minutes": timeframe_minutes,
        "summary": summary,
        "rows": enriched,
        "sample_rows": enriched[:12],
    }


def write_outputs(payload: dict[str, Any], *, output_root: Path = OUTPUT_ROOT) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    json_path = output_root / f"futures_short_zone_block_what_if_{stamp}.json"
    md_path = output_root / f"futures_short_zone_block_what_if_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only Futures SHORT market-plan zone block what-if.")
    parser.add_argument("--dates", nargs="+", required=True)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument(
        "--max-lookahead-candles",
        type=int,
        default=None,
        help="Optional cap. Default checks all available future candles until data end.",
    )
    parser.add_argument("--timeframe-minutes", type=int, default=15)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()

    payload = build_report(
        dates=args.dates,
        symbol=args.symbol,
        timeframe=args.timeframe,
        max_lookahead_candles=args.max_lookahead_candles,
        timeframe_minutes=args.timeframe_minutes,
        data_root=args.data_root.expanduser().resolve(),
    )
    json_path, md_path = write_outputs(payload, output_root=args.output_root.expanduser().resolve())
    print(f"[OK] JSON: {json_path}")
    print(f"[OK] Markdown: {md_path}")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
