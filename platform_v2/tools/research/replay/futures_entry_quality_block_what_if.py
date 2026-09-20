"""File: futures_entry_quality_block_what_if.py
Folder: platform_v2/tools/research/replay
Created date: 2026-06-01
Last updated date: 2026-06-02
Author: Codex
Purpose: Report-only what-if audit for Futures entry-quality denied signals.
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
    timeframe_minutes: int,
) -> dict[str, Any]:
    setup = row.get("theoretical_setup")
    setup = setup if isinstance(setup, dict) else {}
    side = str(row.get("selected_direction") or row.get("side") or "").upper()
    entry = _safe_float(setup.get("entry_price"))
    stop_loss = _safe_float(setup.get("stop_loss"))
    take_profit = _safe_float(setup.get("take_profit"))
    ts = _safe_int(row.get("timestamp_ms"))
    if entry <= 0 or stop_loss <= 0 or take_profit <= 0 or ts <= 0 or side not in {"LONG", "SHORT"}:
        return {
            "outcome": "NO_SETUP",
            "bars_to_outcome": None,
            "hours_to_outcome": None,
            "time_bucket": "NO_SETUP",
            "max_favorable_points": 0.0,
            "max_adverse_points": 0.0,
        }

    future = [candle for candle in candles if _safe_int(candle.get("close_time")) > ts]
    max_favorable = 0.0
    max_adverse = 0.0
    for index, candle in enumerate(future, start=1):
        high = _safe_float(candle.get("high"))
        low = _safe_float(candle.get("low"))
        if side == "SHORT":
            max_favorable = max(max_favorable, entry - low)
            max_adverse = max(max_adverse, high - entry)
            hit_tp = low <= take_profit
            hit_sl = high >= stop_loss
        else:
            max_favorable = max(max_favorable, high - entry)
            max_adverse = max(max_adverse, entry - low)
            hit_tp = high >= take_profit
            hit_sl = low <= stop_loss
        if hit_tp and hit_sl:
            return _outcome_row("AMBIGUOUS_BOTH", index, timeframe_minutes, max_favorable, max_adverse)
        if hit_tp:
            return _outcome_row("TP", index, timeframe_minutes, max_favorable, max_adverse)
        if hit_sl:
            return _outcome_row("SL", index, timeframe_minutes, max_favorable, max_adverse)

    return {
        "outcome": "UNRESOLVED_TO_DATA_END",
        "bars_to_outcome": None,
        "hours_to_outcome": None,
        "time_bucket": "UNRESOLVED",
        "max_favorable_points": round(max_favorable, 2),
        "max_adverse_points": round(max_adverse, 2),
    }


def _outcome_row(
    outcome: str,
    bars_to_outcome: int,
    timeframe_minutes: int,
    max_favorable: float,
    max_adverse: float,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "bars_to_outcome": bars_to_outcome,
        "hours_to_outcome": round(bars_to_outcome * timeframe_minutes / 60.0, 2),
        "time_bucket": _time_bucket(
            bars_to_outcome=bars_to_outcome,
            timeframe_minutes=timeframe_minutes,
        ),
        "max_favorable_points": round(max_favorable, 2),
        "max_adverse_points": round(max_adverse, 2),
    }


def _passed_gate_count(row: dict[str, Any]) -> int:
    gates = row.get("gates")
    gates = gates if isinstance(gates, dict) else {}
    return sum(1 for value in gates.values() if bool(value))


def _filtered_rows(rows: list[dict[str, Any]], side: str | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        row_side = str(row.get("selected_direction") or row.get("side") or "").upper()
        if side and row_side != side:
            continue
        if str(row.get("permission_reason") or "").lower() != "entry_quality_block":
            continue
        result.append(row)
    return result


def _is_override_candidate(row: dict[str, Any]) -> bool:
    entry_quality = row.get("entry_quality")
    entry_quality = entry_quality if isinstance(entry_quality, dict) else {}
    side = str(row.get("selected_direction") or row.get("side") or "").upper()
    timing_type = str(entry_quality.get("timing_type") or "").upper()
    return (
        side == "SHORT"
        and timing_type == "LATE_EXTENSION"
        and _passed_gate_count(row) >= 2
        and _safe_float(row.get("score")) >= 9.0
    )


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Futures Entry Quality Block What-If",
        "",
        f"- `generated_at`: `{payload['generated_at']}`",
        f"- `dates`: `{', '.join(payload['dates'])}`",
        f"- `side`: `{payload['side']}`",
        f"- `blocked_rows`: `{summary['blocked_rows']}`",
        f"- `outcomes`: `{summary['outcomes']}`",
        f"- `time_buckets`: `{summary['time_buckets']}`",
        f"- `timing_counts`: `{summary['timing_counts']}`",
        f"- `by_timing_outcome`: `{summary['by_timing_outcome']}`",
        f"- `override_candidates`: `{summary['override_candidates']}`",
        f"- `override_candidate_outcomes`: `{summary['override_candidate_outcomes']}`",
        "",
        "## Interpretation",
        "",
        "This report checks what would have happened if entry-quality denied signals had been allowed, using each signal's theoretical entry, TP, and SL until available data end.",
        "It does not change runtime behavior.",
        "",
        "## Sample Rows",
        "",
    ]
    for row in payload["sample_rows"]:
        lines.extend(
            [
                f"### {row['time_readable']}",
                "",
                f"- `side`: `{row['side']}`",
                f"- `score`: `{row['score']}`",
                f"- `passed_gate_count`: `{row['passed_gate_count']}`",
                f"- `timing`: `{row['timing_type']}`",
                f"- `direction_signal_age`: `{row['direction_signal_age']}`",
                f"- `market_plan_alignment`: `{row['market_plan_alignment']}`",
                f"- `override_candidate`: `{row['override_candidate']}`",
                f"- `outcome`: `{row['outcome']}`",
                f"- `hours_to_outcome`: `{row['hours_to_outcome']}`",
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
    timeframe_minutes: int,
    side: str | None,
    data_root: Path = DATA_ROOT,
) -> dict[str, Any]:
    rows = _filtered_rows(_load_signal_rows(dates, data_root=data_root), side=side)
    candles = _load_candles(symbol, timeframe, data_root=data_root)
    enriched: list[dict[str, Any]] = []
    outcomes: Counter[str] = Counter()
    time_buckets: Counter[str] = Counter()
    timing_counts: Counter[str] = Counter()
    by_timing_outcome: dict[str, Counter[str]] = {}
    override_outcomes: Counter[str] = Counter()

    for row in rows:
        entry_quality = row.get("entry_quality")
        entry_quality = entry_quality if isinstance(entry_quality, dict) else {}
        market_plan = row.get("market_plan_permission")
        market_plan = market_plan if isinstance(market_plan, dict) else {}
        outcome = _future_outcome(row=row, candles=candles, timeframe_minutes=timeframe_minutes)
        timing_type = str(entry_quality.get("timing_type") or "UNKNOWN")
        override_candidate = _is_override_candidate(row)
        result = {
            "time_readable": row.get("time_readable"),
            "timestamp_ms": row.get("timestamp_ms"),
            "side": str(row.get("selected_direction") or row.get("side") or "UNKNOWN").upper(),
            "score": row.get("score"),
            "passed_gate_count": _passed_gate_count(row),
            "timing_type": timing_type,
            "direction_signal_age": entry_quality.get("direction_signal_age"),
            "market_plan_alignment": market_plan.get("alignment"),
            "market_plan_allowed": market_plan.get("allowed"),
            "override_candidate": override_candidate,
            **outcome,
        }
        enriched.append(result)
        outcomes.update([str(outcome["outcome"])])
        time_buckets.update([str(outcome["time_bucket"])])
        timing_counts.update([timing_type])
        by_timing_outcome.setdefault(timing_type, Counter()).update([str(outcome["outcome"])])
        if override_candidate:
            override_outcomes.update([str(outcome["outcome"])])

    summary = {
        "blocked_rows": len(enriched),
        "outcomes": dict(sorted(outcomes.items())),
        "time_buckets": dict(sorted(time_buckets.items())),
        "timing_counts": dict(sorted(timing_counts.items())),
        "by_timing_outcome": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_timing_outcome.items())
        },
        "override_candidates": sum(1 for row in enriched if row["override_candidate"]),
        "override_candidate_outcomes": dict(sorted(override_outcomes.items())),
    }
    return {
        "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
        "dates": dates,
        "symbol": symbol,
        "timeframe": timeframe,
        "timeframe_minutes": timeframe_minutes,
        "side": side or "ALL",
        "summary": summary,
        "rows": enriched,
        "sample_rows": enriched[:12],
    }


def write_outputs(payload: dict[str, Any], *, output_root: Path = OUTPUT_ROOT) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    json_path = output_root / f"futures_entry_quality_block_what_if_{stamp}.json"
    md_path = output_root / f"futures_entry_quality_block_what_if_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only Futures entry-quality block what-if.")
    parser.add_argument("--dates", nargs="+", required=True)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--timeframe-minutes", type=int, default=15)
    parser.add_argument("--side", choices=["LONG", "SHORT"], default=None)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()

    payload = build_report(
        dates=args.dates,
        symbol=args.symbol,
        timeframe=args.timeframe,
        timeframe_minutes=args.timeframe_minutes,
        side=args.side,
        data_root=args.data_root.expanduser().resolve(),
    )
    json_path, md_path = write_outputs(payload, output_root=args.output_root.expanduser().resolve())
    print(f"[OK] JSON: {json_path}")
    print(f"[OK] Markdown: {md_path}")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
