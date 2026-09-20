"""Compact state-aware component-weight grid for Spot BUY."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT
from platform_v2.tools.research.replay.candidate_profiles import COMPONENTS, PROFILES
from platform_v2.tools.research.replay.component_weight_candidates import (
    scaled_weight_profile,
)
from platform_v2.tools.research.replay.portfolio_state_replay import build_report


DEFAULT_MULTIPLIERS = (0.5, 0.75, 1.25, 1.5)


def spot_profiles(
    *,
    multipliers: tuple[float, ...],
    components: tuple[str, ...] = COMPONENTS,
):
    baseline = PROFILES["spot_baseline_v1"]
    candidates = [
        scaled_weight_profile(
            baseline=baseline,
            component=component,
            multiplier=multiplier,
        )
        for component in components
        for multiplier in multipliers
    ]
    return (baseline, *candidates)


def _candidate_row(
    *,
    profile: dict[str, Any],
    payload: dict[str, Any],
    baseline_profile: dict[str, Any],
    baseline_portfolio: dict[str, Any],
) -> dict[str, Any]:
    portfolio = payload["portfolio"]
    changed_component = next(
        component
        for component in COMPONENTS
        if float(profile["weights"][component])
        != float(baseline_profile["weights"][component])
    )
    weekly_values = [
        float(bucket.get("all", {}).get("net_pnl", 0.0))
        for bucket in portfolio["rolling_7d"]
    ]
    baseline_total = float(baseline_portfolio["closed_stats"]["net_pnl"])
    baseline_train = float(baseline_portfolio["chronological_train"]["net_pnl"])
    baseline_test = float(baseline_portfolio["chronological_test"]["net_pnl"])
    row = {
        "profile_id": profile["profile_id"],
        "component": changed_component,
        "weight": profile["weights"][changed_component],
        "actionable_signals": payload["actionable_signals"],
        "force_close_events": int(payload.get("force_close_events", 0)),
        "opened_positions": portfolio["opened_positions"],
        "net_pnl": portfolio["closed_stats"]["net_pnl"],
        "train_net_pnl": portfolio["chronological_train"]["net_pnl"],
        "test_net_pnl": portfolio["chronological_test"]["net_pnl"],
        "max_sequential_drawdown": portfolio["closed_stats"][
            "max_sequential_drawdown"
        ],
        "total_delta": round(
            float(portfolio["closed_stats"]["net_pnl"]) - baseline_total,
            2,
        ),
        "train_delta": round(
            float(portfolio["chronological_train"]["net_pnl"]) - baseline_train,
            2,
        ),
        "test_delta": round(
            float(portfolio["chronological_test"]["net_pnl"]) - baseline_test,
            2,
        ),
        "positive_weeks": sum(value > 0 for value in weekly_values),
        "negative_weeks": sum(value < 0 for value in weekly_values),
    }
    row["stable_relative_improvement"] = all(
        float(row[key]) > 0 for key in ("total_delta", "train_delta", "test_delta")
    )
    return row


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    baseline_payload = report["spot"]["spot_baseline_v1"]
    baseline_profile = baseline_payload["profile"]
    baseline_portfolio = baseline_payload["portfolio"]
    rows = [
        _candidate_row(
            profile=payload["profile"],
            payload=payload,
            baseline_profile=baseline_profile,
            baseline_portfolio=baseline_portfolio,
        )
        for profile_id, payload in report["spot"].items()
        if profile_id != "spot_baseline_v1"
    ]
    rows.sort(
        key=lambda row: (
            not bool(row["stable_relative_improvement"]),
            -float(row["total_delta"]),
            float(row["max_sequential_drawdown"]),
        )
    )
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": report["snapshot"],
        "guardrail": (
            "One Spot component weight changes at a time; threshold, permissions, "
            "position size, and SL/TP remain baseline."
        ),
        "baseline": baseline_portfolio,
        "candidates": rows,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Spot BUY Weight Grid",
        "",
        f"Generated: `{report['generated_at_utc']} UTC`",
        "",
        report["guardrail"],
        "",
        (
            "| Component | Weight | Net | Total delta | Train delta | Test delta | "
            "Opened | Force close | Drawdown | Weeks +/- | Stable relative |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["candidates"]:
        lines.append(
            f"| {row['component']} | {row['weight']} | {row['net_pnl']} | "
            f"{row['total_delta']} | {row['train_delta']} | {row['test_delta']} | "
            f"{row['opened_positions']} | {row['force_close_events']} | "
            f"{row['max_sequential_drawdown']} | "
            f"{row['positive_weeks']}/{row['negative_weeks']} | "
            f"{'yes' if row['stable_relative_improvement'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"spot_weight_grid_{stamp}.json"
    markdown_path = output_root / f"spot_weight_grid_{stamp}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a state-aware Spot weight grid.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--multipliers", nargs="+", type=float, default=DEFAULT_MULTIPLIERS)
    parser.add_argument("--components", nargs="+", choices=COMPONENTS, default=COMPONENTS)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    args = parser.parse_args()
    profiles = spot_profiles(
        multipliers=tuple(args.multipliers),
        components=tuple(args.components),
    )
    full = build_report(
        args.snapshot,
        spot_profiles=profiles,
        futures_profile_pairs=(
            (
                PROFILES["futures_long_baseline_v1"],
                PROFILES["futures_short_baseline_v1"],
            ),
        ),
    )
    compact = compact_report(full)
    for path in write_report(compact, args.output_root.expanduser().resolve()):
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
