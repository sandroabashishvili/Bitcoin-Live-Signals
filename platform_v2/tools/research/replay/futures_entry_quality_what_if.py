"""File: futures_entry_quality_what_if.py
Folder: platform_v2/tools/research/replay
Created date: 2026-05-25
Last updated date: 2026-06-02
Author: Codex
Purpose: What-if research for Futures entry-quality filters.

This tool reads closed-trade audit rows and simulates whether a proposed
entry-quality filter would have skipped losing/late entries.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots

FUTURES_DATA_ROOT = ResearchDataRoots.live().futures
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


def _parse_side_location_filter(values: list[str]) -> set[tuple[str, str]]:
    filters: set[tuple[str, str]] = set()
    for value in values:
        raw = str(value).strip().upper()
        if not raw:
            continue
        if ":" not in raw:
            raise SystemExit(f"Invalid --block-side-location value: {value!r}. Expected SIDE:LOCATION.")
        side, location = raw.split(":", 1)
        if side not in {"LONG", "SHORT"}:
            raise SystemExit(f"Invalid side in --block-side-location: {side!r}. Expected LONG or SHORT.")
        if not location:
            raise SystemExit(f"Invalid location in --block-side-location: {value!r}.")
        filters.add((side, location))
    return filters


def _load_audit_rows(dates: list[str], *, data_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date_iso in dates:
        path = data_root / "futures_trade_entry_audits" / f"futures_trade_entry_audits_{date_iso}.json"
        for row in _load_json_list(path):
            row = dict(row)
            row["_source_date"] = date_iso
            rows.append(row)
    rows.sort(key=lambda row: _safe_int(row.get("close_timestamp_ms")))
    return rows


def _trade_stats(rows: list[dict[str, Any]], *, include_groups: bool = True) -> dict[str, Any]:
    total = len(rows)
    wins = sum(1 for row in rows if _safe_float(row.get("net_pnl")) > 0)
    net = round(sum(_safe_float(row.get("net_pnl")) for row in rows), 2)
    outcomes = Counter(str(row.get("outcome") or "UNKNOWN") for row in rows)
    by_side: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_timing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_side[str(row.get("side") or "UNKNOWN")].append(row)
        by_timing[str(row.get("entry_timing_type") or "UNKNOWN")].append(row)
    result: dict[str, Any] = {
        "trades": total,
        "wins": wins,
        "win_rate": round((wins / total) * 100.0, 2) if total else 0.0,
        "net_pnl": net,
        "avg_net_pnl": round(net / total, 4) if total else 0.0,
        "outcomes": dict(sorted(outcomes.items())),
    }
    if include_groups:
        result["by_side"] = {
            key: _trade_stats(value, include_groups=False)
            for key, value in sorted(by_side.items())
        }
        result["by_timing"] = {
            key: _trade_stats(value, include_groups=False)
            for key, value in sorted(by_timing.items())
        }
    return result


def _is_blocked(
    row: dict[str, Any],
    *,
    side: str | None,
    block_timing: set[str],
    block_side_location: set[tuple[str, str]],
    block_market_plan_alignment: set[str],
    block_missing_gates: set[str],
    require_all_missing_gates: bool,
    max_signal_age: int | None,
    max_abs_ema50_atr: float | None,
    max_abs_vwap_atr: float | None,
    conjunction_timing: set[str],
    conjunction_market_plan_alignment: set[str],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if side and str(row.get("side") or "").upper() != side:
        return False, reasons

    timing = str(row.get("entry_timing_type") or "UNKNOWN").upper()
    if timing in block_timing:
        reasons.append(f"timing:{timing}")

    row_side = str(row.get("side") or "UNKNOWN").upper()
    location = str(row.get("entry_location_type") or "UNKNOWN").upper()
    if (row_side, location) in block_side_location:
        reasons.append(f"side_location:{row_side}:{location}")

    alignment = str(row.get("entry_market_plan_alignment") or "UNKNOWN").upper()
    if alignment in block_market_plan_alignment:
        reasons.append(f"market_plan_alignment:{alignment}")

    missing_gates = {gate.upper() for gate in _gate_names(row, passed=False)}
    if block_missing_gates:
        if require_all_missing_gates:
            matched_gates = sorted(block_missing_gates & missing_gates)
            if block_missing_gates.issubset(missing_gates):
                reasons.append("missing_gates_all:" + "+".join(sorted(block_missing_gates)))
        else:
            matched_gates = sorted(block_missing_gates & missing_gates)
            if matched_gates:
                reasons.append("missing_gates_any:" + "+".join(matched_gates))

    age = _safe_int(row.get("entry_direction_signal_age"))
    if max_signal_age is not None and age > max_signal_age:
        reasons.append(f"signal_age>{max_signal_age}")

    ema_distance = abs(_safe_float(row.get("distance_from_ema50_atr")))
    if max_abs_ema50_atr is not None and ema_distance > max_abs_ema50_atr:
        reasons.append(f"abs_ema50_atr>{max_abs_ema50_atr}")

    vwap_distance = abs(_safe_float(row.get("distance_from_vwap_atr")))
    if max_abs_vwap_atr is not None and vwap_distance > max_abs_vwap_atr:
        reasons.append(f"abs_vwap_atr>{max_abs_vwap_atr}")

    conjunction_filters_enabled = bool(
        conjunction_timing or conjunction_market_plan_alignment
    )
    conjunction_matches = (
        (not conjunction_timing or timing in conjunction_timing)
        and (
            not conjunction_market_plan_alignment
            or alignment in conjunction_market_plan_alignment
        )
    )
    if conjunction_filters_enabled and conjunction_matches:
        parts: list[str] = []
        if conjunction_timing:
            parts.append("timing=" + "+".join(sorted(conjunction_timing)))
        if conjunction_market_plan_alignment:
            parts.append(
                "market_plan_alignment="
                + "+".join(sorted(conjunction_market_plan_alignment))
            )
        reasons.append("conjunction:" + ",".join(parts))

    return bool(reasons), reasons


def _gate_names(row: dict[str, Any], *, passed: bool) -> list[str]:
    signal_value = row.get("entry_signal")
    signal: dict[str, Any] = signal_value if isinstance(signal_value, dict) else {}

    direction_gates_value = signal.get("direction_gates")
    direction_gates: dict[str, Any] = direction_gates_value if isinstance(direction_gates_value, dict) else {}

    side = str(row.get("side") or "").lower()

    side_gate_value = direction_gates.get(side)
    side_gates: dict[str, Any] = side_gate_value if isinstance(side_gate_value, dict) else {}

    fallback_gates_value = signal.get("gates")
    fallback_gates: dict[str, Any] = fallback_gates_value if isinstance(fallback_gates_value, dict) else {}

    gates: dict[str, Any] = side_gates or fallback_gates
    return [str(name).upper() for name, value in gates.items() if bool(value) is passed]


def _chronological_validation(
    *,
    rows: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
) -> dict[str, Any]:
    dates = sorted(
        {
            str(row.get("_source_date") or "")
            for row in rows
            if str(row.get("_source_date") or "")
        }
    )
    if not dates:
        return {"train": {}, "test": {}, "weekly": []}

    test_start_index = max(1, (len(dates) * 2) // 3)
    test_start_index = min(test_start_index, len(dates) - 1)
    test_start = dates[test_start_index]

    def partition(
        source_rows: list[dict[str, Any]], *, before_test: bool
    ) -> list[dict[str, Any]]:
        return [
            row
            for row in source_rows
            if (
                str(row.get("_source_date") or "") < test_start
                if before_test
                else str(row.get("_source_date") or "") >= test_start
            )
        ]

    def segment_payload(
        baseline_rows: list[dict[str, Any]],
        blocked_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        baseline = _trade_stats(baseline_rows, include_groups=False)
        blocked_stats = _trade_stats(blocked_rows, include_groups=False)
        return {
            "baseline": baseline,
            "blocked": blocked_stats,
            "net_pnl_improvement": round(-blocked_stats["net_pnl"], 2),
        }

    weekly: list[dict[str, Any]] = []
    for index in range(0, len(dates), 7):
        week_dates = dates[index : index + 7]
        date_set = set(week_dates)
        weekly.append(
            {
                "date_from": week_dates[0],
                "date_to": week_dates[-1],
                **segment_payload(
                    [
                        row
                        for row in rows
                        if str(row.get("_source_date") or "") in date_set
                    ],
                    [
                        row
                        for row in blocked
                        if str(row.get("_source_date") or "") in date_set
                    ],
                ),
            }
        )

    return {
        "test_start": test_start,
        "train": segment_payload(
            partition(rows, before_test=True),
            partition(blocked, before_test=True),
        ),
        "test": segment_payload(
            partition(rows, before_test=False),
            partition(blocked, before_test=False),
        ),
        "weekly": weekly,
    }


def build_report(
    *,
    dates: list[str],
    side: str | None,
    block_timing: set[str],
    block_side_location: set[tuple[str, str]],
    block_market_plan_alignment: set[str],
    block_missing_gates: set[str],
    require_all_missing_gates: bool,
    max_signal_age: int | None,
    max_abs_ema50_atr: float | None,
    max_abs_vwap_atr: float | None,
    conjunction_timing: set[str] | None = None,
    conjunction_market_plan_alignment: set[str] | None = None,
    data_root: Path = FUTURES_DATA_ROOT,
) -> dict[str, Any]:
    conjunction_timing = conjunction_timing or set()
    conjunction_market_plan_alignment = conjunction_market_plan_alignment or set()
    rows = _load_audit_rows(dates, data_root=data_root)
    kept: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()

    for row in rows:
        is_blocked, reasons = _is_blocked(
            row,
            side=side,
            block_timing=block_timing,
            block_side_location=block_side_location,
            block_market_plan_alignment=block_market_plan_alignment,
            block_missing_gates=block_missing_gates,
            require_all_missing_gates=require_all_missing_gates,
            max_signal_age=max_signal_age,
            max_abs_ema50_atr=max_abs_ema50_atr,
            max_abs_vwap_atr=max_abs_vwap_atr,
            conjunction_timing=conjunction_timing,
            conjunction_market_plan_alignment=conjunction_market_plan_alignment,
        )
        if is_blocked:
            blocked_row = dict(row)
            blocked_row["what_if_block_reasons"] = reasons
            blocked.append(blocked_row)
            reason_counts.update(reasons)
        else:
            kept.append(row)

    baseline = _trade_stats(rows)
    after_filter = _trade_stats(kept)
    blocked_stats = _trade_stats(blocked)
    validation = _chronological_validation(rows=rows, blocked=blocked)
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "dates": dates,
        "filter": {
            "side": side,
            "block_timing": sorted(block_timing),
            "block_side_location": [f"{side}:{location}" for side, location in sorted(block_side_location)],
            "block_market_plan_alignment": sorted(block_market_plan_alignment),
            "block_missing_gates": sorted(block_missing_gates),
            "require_all_missing_gates": require_all_missing_gates,
            "max_signal_age": max_signal_age,
            "max_abs_ema50_atr": max_abs_ema50_atr,
            "max_abs_vwap_atr": max_abs_vwap_atr,
            "conjunction_timing": sorted(conjunction_timing),
            "conjunction_market_plan_alignment": sorted(
                conjunction_market_plan_alignment
            ),
        },
        "baseline": baseline,
        "after_filter": after_filter,
        "blocked": blocked_stats,
        "validation": validation,
        "delta": {
            "trades": after_filter["trades"] - baseline["trades"],
            "net_pnl": round(after_filter["net_pnl"] - baseline["net_pnl"], 2),
            "win_rate": round(after_filter["win_rate"] - baseline["win_rate"], 2),
        },
        "block_reason_counts": dict(reason_counts.most_common()),
        "blocked_positions": [
            {
                "position_id": row.get("position_id"),
                "date": row.get("_source_date"),
                "side": row.get("side"),
                "timing": row.get("entry_timing_type"),
                "location": row.get("entry_location_type"),
                "age": row.get("entry_direction_signal_age"),
                "outcome": row.get("outcome"),
                "net_pnl": row.get("net_pnl"),
                "market_plan_alignment": row.get("entry_market_plan_alignment"),
                "missing_gates": _gate_names(row, passed=False),
                "reasons": row.get("what_if_block_reasons"),
            }
            for row in blocked
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    baseline = payload["baseline"]
    after_filter = payload["after_filter"]
    blocked = payload["blocked"]
    delta = payload["delta"]
    lines = [
        "# Futures Entry Quality What-If",
        "",
        f"Generated: `{payload['generated_at_utc']} UTC`",
        f"Dates: `{', '.join(payload['dates'])}`",
        "",
        "## Filter",
        "",
        f"- `side`: `{payload['filter']['side']}`",
        f"- `block_timing`: `{', '.join(payload['filter']['block_timing']) or 'none'}`",
        f"- `block_side_location`: `{', '.join(payload['filter']['block_side_location']) or 'none'}`",
        f"- `block_market_plan_alignment`: `{', '.join(payload['filter']['block_market_plan_alignment']) or 'none'}`",
        f"- `block_missing_gates`: `{', '.join(payload['filter']['block_missing_gates']) or 'none'}`",
        f"- `require_all_missing_gates`: `{payload['filter']['require_all_missing_gates']}`",
        f"- `max_signal_age`: `{payload['filter']['max_signal_age']}`",
        f"- `max_abs_ema50_atr`: `{payload['filter']['max_abs_ema50_atr']}`",
        f"- `max_abs_vwap_atr`: `{payload['filter']['max_abs_vwap_atr']}`",
        f"- `conjunction_timing`: `{', '.join(payload['filter']['conjunction_timing']) or 'none'}`",
        f"- `conjunction_market_plan_alignment`: `{', '.join(payload['filter']['conjunction_market_plan_alignment']) or 'none'}`",
        "",
        "## Result",
        "",
        f"- Baseline: trades=`{baseline['trades']}`, win_rate=`{baseline['win_rate']}%`, net_pnl=`{baseline['net_pnl']}`",
        f"- After filter: trades=`{after_filter['trades']}`, win_rate=`{after_filter['win_rate']}%`, net_pnl=`{after_filter['net_pnl']}`",
        f"- Blocked: trades=`{blocked['trades']}`, net_pnl=`{blocked['net_pnl']}`",
        f"- Delta: trades=`{delta['trades']}`, win_rate=`{delta['win_rate']}%`, net_pnl=`{delta['net_pnl']}`",
        "",
        "## Block Reasons",
        "",
    ]
    for reason, count in payload["block_reason_counts"].items():
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(["", "## Blocked Positions", ""])
    for row in payload["blocked_positions"]:
        lines.append(
            f"- `{row['position_id']}` `{row['side']}` timing=`{row['timing']}` location=`{row['location']}` age=`{row['age']}` outcome=`{row['outcome']}` pnl=`{row['net_pnl']}` reasons=`{', '.join(row['reasons'])}`"
        )
    validation = payload["validation"]
    lines.extend(
        [
            "",
            "## Chronological Validation",
            "",
            f"- Test starts: `{validation.get('test_start')}`",
            f"- Train improvement: `{validation.get('train', {}).get('net_pnl_improvement')}`",
            f"- Test improvement: `{validation.get('test', {}).get('net_pnl_improvement')}`",
            "",
            "### Seven-day Buckets",
            "",
        ]
    )
    for row in validation.get("weekly", []):
        lines.append(
            f"- `{row['date_from']}` to `{row['date_to']}`: "
            f"blocked=`{row['blocked']['trades']}`, "
            f"blocked_pnl=`{row['blocked']['net_pnl']}`, "
            f"improvement=`{row['net_pnl_improvement']}`"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Futures entry-quality what-if research.")
    parser.add_argument("--dates", nargs="+", required=True, help="Audit dates, e.g. 2026-04-26 2026-04-27")
    parser.add_argument("--side", choices=["LONG", "SHORT"], default=None)
    parser.add_argument(
        "--block-timing",
        nargs="*",
        default=["EXHAUSTED_MOVE", "LATE_EXTENSION"],
        help="Entry timing buckets to block.",
    )
    parser.add_argument(
        "--block-side-location",
        nargs="*",
        default=[],
        help="Side/location pairs to block, e.g. LONG:EXTENDED_INTO_RESISTANCE.",
    )
    parser.add_argument("--block-market-plan-alignment", nargs="*", default=[])
    parser.add_argument("--block-missing-gates", nargs="*", default=[])
    parser.add_argument("--require-all-missing-gates", action="store_true")
    parser.add_argument("--max-signal-age", type=int, default=None)
    parser.add_argument("--max-abs-ema50-atr", type=float, default=None)
    parser.add_argument("--max-abs-vwap-atr", type=float, default=None)
    parser.add_argument(
        "--conjunction-timing",
        nargs="*",
        default=[],
        help="Timing values for an AND rule with the other conjunction filters.",
    )
    parser.add_argument(
        "--conjunction-market-plan-alignment",
        nargs="*",
        default=[],
        help="Market-plan alignment values for an AND rule with the other conjunction filters.",
    )
    parser.add_argument("--data-root", type=Path, default=FUTURES_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()

    payload = build_report(
        dates=args.dates,
        side=str(args.side).upper() if args.side else None,
        block_timing={str(value).upper() for value in args.block_timing},
        block_side_location=_parse_side_location_filter(args.block_side_location),
        block_market_plan_alignment={
            str(value).upper() for value in args.block_market_plan_alignment
        },
        block_missing_gates={str(value).upper() for value in args.block_missing_gates},
        require_all_missing_gates=bool(args.require_all_missing_gates),
        max_signal_age=args.max_signal_age,
        max_abs_ema50_atr=args.max_abs_ema50_atr,
        max_abs_vwap_atr=args.max_abs_vwap_atr,
        conjunction_timing={
            str(value).upper() for value in args.conjunction_timing
        },
        conjunction_market_plan_alignment={
            str(value).upper()
            for value in args.conjunction_market_plan_alignment
        },
        data_root=args.data_root.expanduser().resolve(),
    )
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"futures_entry_quality_what_if_{stamp}.json"
    md_path = output_root / f"futures_entry_quality_what_if_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"[OK] JSON: {json_path}")
    print(f"[OK] Markdown: {md_path}")
    print(
        "[SUMMARY] "
        f"baseline={payload['baseline']['net_pnl']} "
        f"after={payload['after_filter']['net_pnl']} "
        f"delta={payload['delta']['net_pnl']} "
        f"blocked={payload['blocked']['trades']}"
    )


if __name__ == "__main__":
    main()
