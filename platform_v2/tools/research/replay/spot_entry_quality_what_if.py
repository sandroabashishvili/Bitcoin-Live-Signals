"""File: spot_entry_quality_what_if.py
Folder: platform_v2/tools/research/replay
Created date: 2026-05-25
Last updated date: 2026-06-02
Author: Codex
Purpose: What-if research for Spot BUY entry-location filters.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .entry_location import ResearchEntryLocationClassifier
from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots


SPOT_DATA_ROOT = ResearchDataRoots.live().spot
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


def _load_positions(dates: list[str], *, data_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date_iso in dates:
        path = data_root / "positions" / f"positions_{date_iso}.json"
        for row in _load_json_list(path):
            if str(row.get("status") or "").upper() == "OPEN":
                continue
            if row.get("net_pnl") is None:
                continue
            enriched = dict(row)
            enriched["_source_date"] = date_iso
            rows.append(enriched)
    rows.sort(key=lambda row: str(row.get("opened_at") or ""))
    return rows


def _load_signal_lookup(dates: list[str], *, data_root: Path) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for date_iso in dates:
        path = data_root / "signals" / f"signals_{date_iso}.json"
        for row in _load_json_list(path):
            timestamp_text = _timestamp_text(row.get("timestamp_ms"))
            if timestamp_text:
                lookup[timestamp_text] = row
    return lookup


def _load_snapshots(*, data_root: Path, snapshot_path: Path | None = None) -> list[dict[str, Any]]:
    path = snapshot_path or (data_root / "indicator_snapshots" / "BTCUSDT" / "15m.json")
    rows = _load_json_list(path)
    rows.sort(key=lambda row: str(row.get("datetime") or ""))
    return rows


def _timestamp_text(value: Any) -> str:
    try:
        timestamp_ms = int(value)
    except (TypeError, ValueError):
        return ""
    if timestamp_ms <= 0:
        return ""
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")


def _snapshot_for_entry(*, snapshots: list[dict[str, Any]], opened_at: str) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for snapshot in snapshots:
        snapshot_time = str(snapshot.get("datetime") or "")
        if snapshot_time and snapshot_time <= opened_at:
            selected = snapshot
            continue
        break
    return selected


def _entry_price(row: dict[str, Any]) -> float:
    execution = row.get("execution")
    if isinstance(execution, dict):
        return _safe_float(execution.get("entry_price"))
    return 0.0


def _position_size(row: dict[str, Any]) -> float:
    execution = row.get("execution")
    if isinstance(execution, dict):
        return _safe_float(execution.get("position_size"))
    return 0.0


def _with_entry_context(
    rows: list[dict[str, Any]],
    *,
    snapshots: list[dict[str, Any]],
    signal_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        opened_at = str(row.get("opened_at") or "")
        snapshot = _snapshot_for_entry(snapshots=snapshots, opened_at=opened_at)
        signal = signal_lookup.get(opened_at, {})
        gates = signal.get("gates") if isinstance(signal.get("gates"), dict) else {}
        passed_gates = [str(name).upper() for name, passed in gates.items() if bool(passed)]
        missing_gates = [str(name).upper() for name, passed in gates.items() if not bool(passed)]
        location = ResearchEntryLocationClassifier.classify(
            side="BUY",
            entry_price=_entry_price(row),
            snapshot=snapshot,
        )
        next_row = dict(row)
        next_row["entry_location_type"] = location.get("type")
        next_row["entry_location"] = location
        next_row["entry_snapshot_time"] = snapshot.get("datetime")
        next_row["entry_signal"] = signal
        next_row["passed_gates"] = passed_gates
        next_row["missing_gates"] = missing_gates
        next_row["gate_combo"] = "+".join(passed_gates) if passed_gates else "NO_GATES"
        next_row["missing_gate_combo"] = "+".join(missing_gates) if missing_gates else "NO_MISSING_GATES"
        enriched.append(next_row)
    return enriched


def _trade_stats(rows: list[dict[str, Any]], *, include_groups: bool = True) -> dict[str, Any]:
    total = len(rows)
    wins = sum(1 for row in rows if _safe_float(row.get("net_pnl")) > 0)
    net = round(sum(_safe_float(row.get("net_pnl")) for row in rows), 2)
    total_position_size = round(sum(_position_size(row) for row in rows), 2)
    outcomes = Counter(str(row.get("exit_reason") or "UNKNOWN") for row in rows)
    by_location: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_gate_combo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_location_gate_combo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        location = str(row.get("entry_location_type") or "UNKNOWN")
        gate_combo = str(row.get("gate_combo") or "NO_GATES")
        by_location[location].append(row)
        by_gate_combo[gate_combo].append(row)
        by_location_gate_combo[f"{location}|{gate_combo}"].append(row)
    result: dict[str, Any] = {
        "trades": total,
        "wins": wins,
        "win_rate": round((wins / total) * 100.0, 2) if total else 0.0,
        "net_pnl": net,
        "avg_net_pnl": round(net / total, 4) if total else 0.0,
        "total_position_size": total_position_size,
        "net_pnl_pct_of_position": round((net / total_position_size) * 100.0, 4)
        if total_position_size
        else 0.0,
        "avg_net_pnl_pct_of_position": round((net / total_position_size) * 100.0 / total, 4)
        if total_position_size and total
        else 0.0,
        "outcomes": dict(sorted(outcomes.items())),
    }
    if include_groups:
        result["by_location"] = {
            key: _trade_stats(value, include_groups=False)
            for key, value in sorted(by_location.items())
        }
        result["by_gate_combo"] = {
            key: _trade_stats(value, include_groups=False)
            for key, value in sorted(by_gate_combo.items())
        }
        result["by_location_gate_combo"] = {
            key: _trade_stats(value, include_groups=False)
            for key, value in sorted(by_location_gate_combo.items())
        }
    return result


def _missing_gate_filter_matches(
    row: dict[str, Any],
    *,
    block_missing_gates: set[str],
    require_all_missing_gates: bool,
) -> bool:
    if not block_missing_gates:
        return True
    missing_gates = {
        str(value).upper()
        for value in row.get("missing_gates", [])
        if str(value).strip()
    }
    if require_all_missing_gates:
        return block_missing_gates.issubset(missing_gates)
    return bool(block_missing_gates.intersection(missing_gates))


def build_report(
    *,
    dates: list[str],
    block_location: set[str],
    block_missing_gates: set[str],
    require_all_missing_gates: bool,
    data_root: Path = SPOT_DATA_ROOT,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    snapshots = _load_snapshots(data_root=data_root, snapshot_path=snapshot_path)
    signal_lookup = _load_signal_lookup(dates, data_root=data_root)
    rows = _with_entry_context(
        _load_positions(dates, data_root=data_root),
        snapshots=snapshots,
        signal_lookup=signal_lookup,
    )
    blocked: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()

    for row in rows:
        location = str(row.get("entry_location_type") or "UNKNOWN").upper()
        filter_active = bool(block_location or block_missing_gates)
        location_matches = not block_location or location in block_location
        if filter_active and location_matches and _missing_gate_filter_matches(
            row,
            block_missing_gates=block_missing_gates,
            require_all_missing_gates=require_all_missing_gates,
        ):
            next_row = dict(row)
            reasons = [f"location:{location}"] if block_location else []
            if block_missing_gates:
                gate_mode = "all" if require_all_missing_gates else "any"
                missing_label = "+".join(sorted(block_missing_gates))
                reasons.append(f"missing_gates:{gate_mode}:{missing_label}")
            next_row["what_if_block_reasons"] = reasons
            blocked.append(next_row)
            for reason in reasons:
                reason_counts[reason] += 1
        else:
            kept.append(row)

    baseline = _trade_stats(rows)
    after_filter = _trade_stats(kept)
    blocked_stats = _trade_stats(blocked)
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "dates": dates,
        "filter": {
            "block_location": sorted(block_location),
            "block_missing_gates": sorted(block_missing_gates),
            "require_all_missing_gates": require_all_missing_gates,
        },
        "baseline": baseline,
        "after_filter": after_filter,
        "blocked": blocked_stats,
        "delta": {
            "trades": after_filter["trades"] - baseline["trades"],
            "net_pnl": round(after_filter["net_pnl"] - baseline["net_pnl"], 2),
            "net_pnl_pct_of_position": round(
                after_filter["net_pnl_pct_of_position"] - baseline["net_pnl_pct_of_position"],
                4,
            ),
            "win_rate": round(after_filter["win_rate"] - baseline["win_rate"], 2),
        },
        "block_reason_counts": dict(reason_counts.most_common()),
        "blocked_positions": [
            {
                "position_id": row.get("position_id"),
                "date": row.get("_source_date"),
                "opened_at": row.get("opened_at"),
                "entry_snapshot_time": row.get("entry_snapshot_time"),
                "location": row.get("entry_location_type"),
                "gate_combo": row.get("gate_combo"),
                "missing_gate_combo": row.get("missing_gate_combo"),
                "outcome": row.get("exit_reason"),
                "net_pnl": row.get("net_pnl"),
                "position_size": _position_size(row),
                "net_pnl_pct_of_position": round(
                    (_safe_float(row.get("net_pnl")) / _position_size(row)) * 100.0,
                    4,
                )
                if _position_size(row)
                else 0.0,
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
        "# Spot Entry Quality What-If",
        "",
        f"Generated: `{payload['generated_at_utc']} UTC`",
        f"Dates: `{', '.join(payload['dates'])}`",
        "",
        "## Filter",
        "",
        f"- `block_location`: `{', '.join(payload['filter']['block_location']) or 'none'}`",
        f"- `block_missing_gates`: `{', '.join(payload['filter']['block_missing_gates']) or 'none'}`",
        f"- `require_all_missing_gates`: `{payload['filter']['require_all_missing_gates']}`",
        "",
        "## Result",
        "",
        f"- Baseline: trades=`{baseline['trades']}`, win_rate=`{baseline['win_rate']}%`, net_pnl=`{baseline['net_pnl']}`, net_pct=`{baseline['net_pnl_pct_of_position']}%`",
        f"- After filter: trades=`{after_filter['trades']}`, win_rate=`{after_filter['win_rate']}%`, net_pnl=`{after_filter['net_pnl']}`, net_pct=`{after_filter['net_pnl_pct_of_position']}%`",
        f"- Blocked: trades=`{blocked['trades']}`, net_pnl=`{blocked['net_pnl']}`, net_pct=`{blocked['net_pnl_pct_of_position']}%`",
        f"- Delta: trades=`{delta['trades']}`, win_rate=`{delta['win_rate']}%`, net_pnl=`{delta['net_pnl']}`, net_pct=`{delta['net_pnl_pct_of_position']}%`",
        "",
        "## Location Breakdown",
        "",
    ]
    for location, stats in baseline.get("by_location", {}).items():
        lines.append(
            f"- `{location}`: trades=`{stats['trades']}`, win_rate=`{stats['win_rate']}%`, net_pnl=`{stats['net_pnl']}`, net_pct=`{stats['net_pnl_pct_of_position']}%`"
        )
    lines.extend(["", "## Gate Combo Breakdown", ""])
    for combo, stats in baseline.get("by_gate_combo", {}).items():
        lines.append(
            f"- `{combo}`: trades=`{stats['trades']}`, win_rate=`{stats['win_rate']}%`, net_pnl=`{stats['net_pnl']}`, net_pct=`{stats['net_pnl_pct_of_position']}%`"
        )
    lines.extend(["", "## Location + Gate Combo Breakdown", ""])
    for combo, stats in baseline.get("by_location_gate_combo", {}).items():
        lines.append(
            f"- `{combo}`: trades=`{stats['trades']}`, win_rate=`{stats['win_rate']}%`, net_pnl=`{stats['net_pnl']}`, net_pct=`{stats['net_pnl_pct_of_position']}%`"
        )
    lines.extend(["", "## Block Reasons", ""])
    for reason, count in payload["block_reason_counts"].items():
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(["", "## Blocked Positions", ""])
    for row in payload["blocked_positions"]:
        lines.append(
            f"- `{row['position_id']}` opened=`{row['opened_at']}` location=`{row['location']}` gates=`{row['gate_combo']}` missing=`{row['missing_gate_combo']}` outcome=`{row['outcome']}` pnl=`{row['net_pnl']}` pct=`{row['net_pnl_pct_of_position']}%` reasons=`{', '.join(row['reasons'])}`"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Spot entry-location what-if research.")
    parser.add_argument("--dates", nargs="+", required=True, help="Position dates, e.g. 2026-05-14 2026-05-15")
    parser.add_argument(
        "--block-location",
        nargs="*",
        default=["EXTENDED_INTO_RESISTANCE"],
        help="Spot BUY entry-location buckets to block.",
    )
    parser.add_argument(
        "--block-missing-gates",
        nargs="*",
        default=[],
        help="Only block matching locations when any listed gate is missing.",
    )
    parser.add_argument(
        "--require-all-missing-gates",
        action="store_true",
        help="Require every --block-missing-gates item to be missing before blocking.",
    )
    parser.add_argument("--data-root", type=Path, default=SPOT_DATA_ROOT)
    parser.add_argument(
        "--snapshot-path",
        type=Path,
        default=None,
        help="Optional full-history 15m indicator file built outside the frozen input snapshot.",
    )
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()

    payload = build_report(
        dates=args.dates,
        block_location={str(value).upper() for value in args.block_location},
        block_missing_gates={str(value).upper() for value in args.block_missing_gates},
        require_all_missing_gates=bool(args.require_all_missing_gates),
        data_root=args.data_root.expanduser().resolve(),
        snapshot_path=args.snapshot_path.expanduser().resolve() if args.snapshot_path else None,
    )
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"spot_entry_quality_what_if_{stamp}.json"
    md_path = output_root / f"spot_entry_quality_what_if_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"[OK] JSON: {json_path}")
    print(f"[OK] Markdown: {md_path}")
    print(
        "[SUMMARY] "
        f"baseline={payload['baseline']['net_pnl']} "
        f"after={payload['after_filter']['net_pnl']} "
        f"delta={payload['delta']['net_pnl']} "
        f"delta_pct={payload['delta']['net_pnl_pct_of_position']}% "
        f"blocked={payload['blocked']['trades']}"
    )


if __name__ == "__main__":
    main()
