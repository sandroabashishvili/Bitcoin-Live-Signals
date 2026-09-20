"""Compact state-aware component-weight grid for one Futures direction."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT
from platform_v2.tools.research.replay.candidate_profiles import COMPONENTS, PROFILES, CandidateProfile
from platform_v2.tools.research.replay.component_weight_candidates import (
    scaled_weight_profile,
)
from platform_v2.tools.research.replay.portfolio_state_replay import build_report


DEFAULT_MULTIPLIERS = (0.5, 0.75, 1.25, 1.5)


def profile_pairs(
    *,
    side: str,
    multipliers: tuple[float, ...],
    components: tuple[str, ...] = COMPONENTS,
) -> tuple[tuple[CandidateProfile, CandidateProfile], ...]:
    long_baseline = PROFILES["futures_long_baseline_v1"]
    short_baseline = PROFILES["futures_short_baseline_v1"]
    pairs: list[tuple[CandidateProfile, CandidateProfile]] = [(long_baseline, short_baseline)]
    baseline = long_baseline if side == "LONG" else short_baseline
    for component in components:
        for multiplier in multipliers:
            candidate = scaled_weight_profile(
                baseline=baseline,
                component=component,
                multiplier=multiplier,
            )
            pairs.append(
                (candidate, short_baseline) if side == "LONG" else (long_baseline, candidate)
            )
    return tuple(pairs)


def _candidate_row(
    *,
    pair_id: str,
    payload: dict[str, Any],
    side: str,
    baseline_weights: dict[str, float],
    baseline_side: dict[str, Any],
) -> dict[str, Any]:
    profile = payload["long_profile"] if side == "LONG" else payload["short_profile"]
    portfolio = payload["portfolio"]
    side_stats = portfolio["by_side"].get(side, {})
    closed = side_stats.get("closed", {})
    train = side_stats.get("train", {})
    test = side_stats.get("test", {})
    changed_component = next(
        name
        for name in COMPONENTS
        if float(profile["weights"][name]) != float(baseline_weights[name])
    )
    weekly_values = [
        float(bucket.get("by_side", {}).get(side, {}).get("net_pnl", 0.0))
        for bucket in portfolio["rolling_7d"]
        if side in bucket.get("by_side", {})
    ]
    row = {
        "pair_id": pair_id,
        "profile_id": profile["profile_id"],
        "component": changed_component,
        "weight": profile["weights"][changed_component],
        "opened_positions": portfolio["opened_positions"],
        "portfolio_net_pnl": portfolio["closed_stats"]["net_pnl"],
        "portfolio_train_net_pnl": portfolio["chronological_train"]["net_pnl"],
        "portfolio_test_net_pnl": portfolio["chronological_test"]["net_pnl"],
        "max_sequential_drawdown": portfolio["closed_stats"][
            "max_sequential_drawdown"
        ],
        "side_trades": closed.get("trades", 0),
        "side_net_pnl": closed.get("net_pnl", 0.0),
        "side_train_net_pnl": train.get("net_pnl", 0.0),
        "side_test_net_pnl": test.get("net_pnl", 0.0),
        "side_total_delta": round(
            float(closed.get("net_pnl", 0.0))
            - float(baseline_side["closed"]["net_pnl"]),
            2,
        ),
        "side_train_delta": round(
            float(train.get("net_pnl", 0.0))
            - float(baseline_side["train"]["net_pnl"]),
            2,
        ),
        "side_test_delta": round(
            float(test.get("net_pnl", 0.0))
            - float(baseline_side["test"]["net_pnl"]),
            2,
        ),
        "positive_weeks": sum(value > 0 for value in weekly_values),
        "negative_weeks": sum(value < 0 for value in weekly_values),
    }
    row["stable_relative_improvement"] = all(
        float(row[key]) > 0
        for key in ("side_total_delta", "side_train_delta", "side_test_delta")
    )
    return row


def compact_report(
    *,
    report: dict[str, Any],
    side: str,
) -> dict[str, Any]:
    baseline_id = "futures_long_baseline_v1__futures_short_baseline_v1"
    baseline_payload = report["futures"][baseline_id]
    baseline = baseline_payload["portfolio"]
    baseline_side = baseline["by_side"][side]
    baseline_profile = (
        baseline_payload["long_profile"]
        if side == "LONG"
        else baseline_payload["short_profile"]
    )
    rows: list[dict[str, Any]] = []
    for pair_id, payload in report["futures"].items():
        if pair_id == baseline_id:
            continue
        rows.append(
            _candidate_row(
                pair_id=pair_id,
                payload=payload,
                side=side,
                baseline_weights=baseline_profile["weights"],
                baseline_side=baseline_side,
            )
        )
    rows.sort(
        key=lambda row: (
            not bool(row["stable_relative_improvement"]),
            -float(row["side_total_delta"]),
            float(row["max_sequential_drawdown"]),
        )
    )
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": report["snapshot"],
        "side": side,
        "guardrail": (
            "One component weight changes at a time; threshold, permissions, "
            "position size, and SL/TP remain baseline."
        ),
        "baseline": {
            "portfolio": baseline["closed_stats"],
            "train": baseline["chronological_train"],
            "test": baseline["chronological_test"],
            "side": baseline_side,
        },
        "candidates": rows,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Futures {report['side']} Weight Grid", "",
        f"Generated: `{report['generated_at_utc']} UTC`", "",
        report["guardrail"], "",
        (
            "| Component | Weight | Side net | Total delta | Train delta | "
            "Test delta | Portfolio net | Drawdown | Weeks +/- | Stable relative |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["candidates"]:
        lines.append(
            f"| {row['component']} | {row['weight']} | {row['side_net_pnl']} | "
            f"{row['side_total_delta']} | {row['side_train_delta']} | {row['side_test_delta']} | "
            f"{row['portfolio_net_pnl']} | {row['max_sequential_drawdown']} | "
            f"{row['positive_weeks']}/{row['negative_weeks']} | "
            f"{'yes' if row['stable_relative_improvement'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"futures_weight_grid_{report['side'].lower()}_{stamp}.json"
    markdown_path = output_root / f"futures_weight_grid_{report['side'].lower()}_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a state-aware Futures component-weight grid.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--side", choices=("LONG", "SHORT"), default="SHORT")
    parser.add_argument("--multipliers", nargs="+", type=float, default=DEFAULT_MULTIPLIERS)
    parser.add_argument("--components", nargs="+", choices=COMPONENTS, default=COMPONENTS)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    args = parser.parse_args()
    pairs = profile_pairs(
        side=args.side,
        multipliers=tuple(args.multipliers),
        components=tuple(args.components),
    )
    full = build_report(args.snapshot, futures_profile_pairs=pairs)
    compact = compact_report(report=full, side=args.side)
    for path in write_report(compact, args.output_root.expanduser().resolve()):
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
