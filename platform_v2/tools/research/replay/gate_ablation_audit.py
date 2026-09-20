"""Audit gate value on executed Spot and Futures trades from a frozen snapshot.

The report compares pass-versus-fail cohorts. It is intentionally report-only:
association in executed trades is useful evidence, but is not causal proof that
removing a component will reproduce the same trades or PnL.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots


GATE_NAMES = ("mtf", "regime", "momentum", "trend", "orderbook", "structure")


def _load_family_rows(folder: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not folder.is_dir():
        return rows
    for source in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _opened_at_ms(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    try:
        parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None
    return int(parsed.timestamp() * 1000) + 999


def _date_from_ms(value: Any) -> str:
    try:
        timestamp_ms = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if timestamp_ms <= 0:
        return ""
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date().isoformat()


def _stats(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    wins = sum(1 for row in rows if _safe_float(row.get("net_pnl")) > 0)
    net_pnl = round(sum(_safe_float(row.get("net_pnl")) for row in rows), 2)
    trades = len(rows)
    return {
        "trades": trades,
        "wins": wins,
        "win_rate": round(wins / trades * 100.0, 2) if trades else 0.0,
        "net_pnl": net_pnl,
        "avg_net_pnl": round(net_pnl / trades, 4) if trades else 0.0,
    }


def _validation_split(rows: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    dates = sorted({str(row.get("date") or "") for row in rows if row.get("date")})
    if len(dates) < 2:
        return None, rows, []
    test_index = min(max(1, len(dates) * 2 // 3), len(dates) - 1)
    test_start = dates[test_index]
    return (
        test_start,
        [row for row in rows if str(row.get("date") or "") < test_start],
        [row for row in rows if str(row.get("date") or "") >= test_start],
    )


def _gate_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for gate in GATE_NAMES:
        passed = [row for row in rows if bool((row.get("gates") or {}).get(gate))]
        failed = [row for row in rows if not bool((row.get("gates") or {}).get(gate))]
        pass_stats = _stats(passed)
        fail_stats = _stats(failed)
        result[gate] = {
            "passed": pass_stats,
            "failed": fail_stats,
            "avg_net_pnl_delta": round(
                float(pass_stats["avg_net_pnl"]) - float(fail_stats["avg_net_pnl"]), 4
            ),
            "win_rate_delta": round(
                float(pass_stats["win_rate"]) - float(fail_stats["win_rate"]), 2
            ),
        }
    return result


def _pass_count_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for count in range(len(GATE_NAMES) + 1):
        selected = [
            row
            for row in rows
            if sum(bool((row.get("gates") or {}).get(gate)) for gate in GATE_NAMES) == count
        ]
        if selected:
            result[str(count)] = _stats(selected)
    return result


def _combination_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        label = "+".join(
            gate for gate in GATE_NAMES if bool((row.get("gates") or {}).get(gate))
        ) or "NONE"
        groups[label].append(row)
    result = [
        {"combination": label, **_stats(values)}
        for label, values in groups.items()
    ]
    return sorted(
        result,
        key=lambda row: (-int(row["trades"]), -float(row["net_pnl"])),
    )


def _score_band_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bands = ((8.5, 9.5), (9.5, 10.5), (10.5, 11.5), (11.5, 12.5), (12.5, None))
    result: list[dict[str, Any]] = []
    for lower, upper in bands:
        selected = [
            row
            for row in rows
            if _safe_float(row.get("score")) >= lower
            and (upper is None or _safe_float(row.get("score")) < upper)
        ]
        result.append(
            {
                "from": lower,
                "to": upper,
                **_stats(selected),
            }
        )
    return result


def _segment(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    test_start, train, test = _validation_split(rows)
    return {
        "name": name,
        "baseline": _stats(rows),
        "by_gate": _gate_rows(rows),
        "by_pass_count": _pass_count_rows(rows),
        "by_score_band": _score_band_rows(rows),
        "combinations": _combination_rows(rows),
        "validation": {
            "test_start": test_start,
            "train": {"baseline": _stats(train), "by_gate": _gate_rows(train)},
            "test": {"baseline": _stats(test), "by_gate": _gate_rows(test)},
        },
    }


def _spot_trade_rows(spot_root: Path) -> list[dict[str, Any]]:
    signals = _load_family_rows(spot_root / "signals")
    signals_by_timestamp = {
        int(row.get("timestamp_ms") or 0): row
        for row in signals
        if int(row.get("timestamp_ms") or 0) > 0
    }
    positions_by_id: dict[str, dict[str, Any]] = {}
    for position in _load_family_rows(spot_root / "positions"):
        position_id = str(position.get("position_id") or "")
        if position_id:
            positions_by_id[position_id] = position

    rows: list[dict[str, Any]] = []
    for position in positions_by_id.values():
        if str(position.get("status") or "").upper() != "CLOSED":
            continue
        opened_at_ms = _opened_at_ms(position.get("opened_at"))
        if opened_at_ms is None:
            continue
        signal = signals_by_timestamp.get(opened_at_ms)
        if not signal:
            continue
        gates = signal.get("gates")
        rows.append(
            {
                "position_id": position.get("position_id"),
                "side": "BUY",
                "date": _date_from_ms(opened_at_ms),
                "score": _safe_float(signal.get("score")),
                "net_pnl": _safe_float(position.get("net_pnl")),
                "gates": gates if isinstance(gates, dict) else {},
            }
        )
    return rows


def _futures_trade_rows(futures_root: Path) -> list[dict[str, Any]]:
    audits_by_id: dict[str, dict[str, Any]] = {}
    for audit in _load_family_rows(futures_root / "futures_trade_entry_audits"):
        position_id = str(audit.get("position_id") or "")
        if position_id:
            audits_by_id[position_id] = audit

    rows: list[dict[str, Any]] = []
    for audit in audits_by_id.values():
        side = str(audit.get("side") or "").upper()
        signal_value = audit.get("entry_signal")
        signal = signal_value if isinstance(signal_value, dict) else {}
        gates_value = signal.get("direction_gates")
        direction_gates = gates_value if isinstance(gates_value, dict) else {}
        side_gates = direction_gates.get(side.lower())
        fallback_gates = signal.get("gates")
        gates = side_gates if isinstance(side_gates, dict) else fallback_gates
        entry_timestamp_ms = int(audit.get("entry_timestamp_ms") or 0)
        rows.append(
            {
                "position_id": audit.get("position_id"),
                "side": side,
                "date": _date_from_ms(entry_timestamp_ms),
                "score": _safe_float(signal.get("score")),
                "net_pnl": _safe_float(audit.get("net_pnl")),
                "gates": gates if isinstance(gates, dict) else {},
            }
        )
    return rows


def build_report(snapshot_root: Path) -> dict[str, Any]:
    roots = ResearchDataRoots.from_snapshot(snapshot_root)
    spot_rows = _spot_trade_rows(roots.spot)
    futures_rows = _futures_trade_rows(roots.futures)
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": str(snapshot_root.expanduser().resolve()),
        "method": "executed_trade_pass_vs_fail_association",
        "causality_warning": (
            "Gate pass/fail cohorts are observational. A true component removal requires replay "
            "from raw component scores and historical inputs."
        ),
        "raw_component_scores_available": False,
        "spot": _segment("SPOT", spot_rows),
        "futures": _segment("FUTURES", futures_rows),
        "futures_long": _segment(
            "FUTURES_LONG", [row for row in futures_rows if row.get("side") == "LONG"]
        ),
        "futures_short": _segment(
            "FUTURES_SHORT", [row for row in futures_rows if row.get("side") == "SHORT"]
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gate Ablation Audit",
        "",
        f"Generated: `{report['generated_at_utc']} UTC`",
        f"Snapshot: `{report['snapshot']}`",
        "",
        "This is pass-versus-fail association on executed trades, not causal proof.",
        "Raw per-component scores were not persisted, so true remove-one-component replay is not yet possible.",
        "",
    ]
    for key in ("spot", "futures", "futures_long", "futures_short"):
        section = report[key]
        baseline = section["baseline"]
        lines.extend(
            [
                f"## {section['name']}",
                "",
                f"Baseline: trades=`{baseline['trades']}`, win_rate=`{baseline['win_rate']}%`, net_pnl=`{baseline['net_pnl']}`",
                "",
                "| Gate | Pass n | Pass PnL | Fail n | Fail PnL | All delta | Train delta | Test delta |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for gate, row in section["by_gate"].items():
            train_row = section["validation"]["train"]["by_gate"][gate]
            test_row = section["validation"]["test"]["by_gate"][gate]
            lines.append(
                f"| {gate.upper()} | {row['passed']['trades']} | {row['passed']['net_pnl']} | "
                f"{row['failed']['trades']} | {row['failed']['net_pnl']} | {row['avg_net_pnl_delta']} | "
                f"{train_row['avg_net_pnl_delta']} | {test_row['avg_net_pnl_delta']} |"
            )
        lines.extend(["", "### Gate-count cohorts", ""])
        for count, stats in section["by_pass_count"].items():
            lines.append(
                f"- passed=`{count}`: trades=`{stats['trades']}`, win_rate=`{stats['win_rate']}%`, net_pnl=`{stats['net_pnl']}`"
            )
        lines.extend(["", "### Score bands", ""])
        for band in section["by_score_band"]:
            upper = band["to"] if band["to"] is not None else "plus"
            lines.append(
                f"- `{band['from']}` to `{upper}`: trades=`{band['trades']}`, "
                f"win_rate=`{band['win_rate']}%`, net_pnl=`{band['net_pnl']}`"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"gate_ablation_audit_{stamp}.json"
    markdown_path = output_root / f"gate_ablation_audit_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit gate pass/fail value on frozen executed trades.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    args = parser.parse_args()
    report = build_report(args.snapshot)
    paths = write_report(report, args.output_root.expanduser().resolve())
    for path in paths:
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
