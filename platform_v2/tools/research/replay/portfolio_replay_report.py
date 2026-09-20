"""Markdown and artifact writer for permission/state-aware replay."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


def _empty_side() -> dict[str, dict[str, float | int]]:
    def stats() -> dict[str, float | int]:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "avg_net_pnl": 0.0,
            "max_sequential_drawdown": 0.0,
        }

    return {
        "closed": stats(),
        "train": stats(),
        "test": stats(),
    }


def _header(report: dict[str, Any]) -> list[str]:
    lines = [
        "# Permission/State-Aware Portfolio Replay", "",
        f"Generated: `{report['generated_at_utc']} UTC`",
        f"Snapshot: `{report['snapshot']}`",
        f"Exit candles: `{report['exit_timeframe']}`", "",
        "## Method guardrails", "",
    ]
    if report.get("shadow_candidate_set_version"):
        lines[5:5] = [
            f"Candidate set: `{report['shadow_candidate_set_version']}`",
            f"Cutoff (exclusive): `{report.get('evaluation_start_ms_exclusive')}`",
            "",
        ]
    lines.extend(f"- {item}" for item in report["limitations"])
    return lines


def _fidelity(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Baseline fidelity checkpoint", "",
        "| Market | Actual closed | Actual net | Replay closed | Replay net | Entry timestamp matches |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    spot_baseline = report["spot"]["spot_baseline_v1"]
    spot_actual = report["actual_closed_performance"]["SPOT"]
    spot_validation = spot_baseline["baseline_validation"]
    spot_portfolio = spot_baseline["portfolio"]
    lines.append(
        f"| SPOT | {spot_actual['closed_positions']} | {spot_actual['net_pnl']} | "
        f"{spot_portfolio['closed_positions']} | {spot_portfolio['closed_stats']['net_pnl']} | "
        f"{spot_validation['exact_timestamp_matches']}/{spot_validation['actual']} |"
    )
    futures_baseline = report["futures"]["futures_long_baseline_v1__futures_short_baseline_v1"]
    futures_actual_closed = sum(report["actual_closed_performance"][side]["closed_positions"] for side in ("LONG", "SHORT"))
    futures_actual_net = round(sum(report["actual_closed_performance"][side]["net_pnl"] for side in ("LONG", "SHORT")), 2)
    futures_matches = sum(futures_baseline["baseline_validation"][side]["exact_timestamp_matches"] for side in ("LONG", "SHORT"))
    futures_actual_opened = sum(futures_baseline["baseline_validation"][side]["actual"] for side in ("LONG", "SHORT"))
    futures_portfolio = futures_baseline["portfolio"]
    lines.append(
        f"| FUTURES | {futures_actual_closed} | {futures_actual_net} | "
        f"{futures_portfolio['closed_positions']} | {futures_portfolio['closed_stats']['net_pnl']} | "
        f"{futures_matches}/{futures_actual_opened} |"
    )
    lines.extend(["", (
        "Spot force-close fidelity: "
        f"actual `{spot_actual.get('force_close_events', 0)}`, "
        f"replay `{spot_baseline.get('force_close_events', 0)}`."
    )])
    return lines


def _spot_table(report: dict[str, Any]) -> list[str]:
    lines = ["", "## SPOT", "",
        "| Profile | Signals | Opened | Closed net | Train net | Test net | Win rate | Actual | Exact matches |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for profile_id, row in report["spot"].items():
        portfolio = row["portfolio"]
        stats = portfolio["closed_stats"]
        validation = row["baseline_validation"]
        lines.append(
            f"| {profile_id} | {row['actionable_signals']} | {portfolio['opened_positions']} | "
            f"{stats['net_pnl']} | {portfolio['chronological_train']['net_pnl']} | "
            f"{portfolio['chronological_test']['net_pnl']} | {stats['win_rate']}% | {validation['actual']} | "
            f"{validation['exact_timestamp_matches']} |"
        )
    return lines


def _futures_table(report: dict[str, Any]) -> list[str]:
    lines = ["", "## FUTURES", "",
        "| Profile pair | Opened | Exit edits | Total net | LONG net | SHORT net | Train net | Test net | Win rate | Drawdown |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for profile_id, row in report["futures"].items():
        portfolio = row["portfolio"]
        stats = portfolio["closed_stats"]
        long_stats = portfolio["by_side"].get("LONG", {}).get("closed", {"net_pnl": 0.0})
        short_stats = portfolio["by_side"].get("SHORT", {}).get("closed", {"net_pnl": 0.0})
        lines.append(
            f"| {profile_id} | {portfolio['opened_positions']} | "
            f"{row.get('exit_policy_applied_count', 0)} | {stats['net_pnl']} | "
            f"{long_stats['net_pnl']} | {short_stats['net_pnl']} | {portfolio['chronological_train']['net_pnl']} | "
            f"{portfolio['chronological_test']['net_pnl']} | {stats['win_rate']}% | "
            f"{stats['max_sequential_drawdown']} |"
        )
    return lines


def _candidate_deltas(report: dict[str, Any]) -> list[str]:
    futures_baseline = report["futures"]["futures_long_baseline_v1__futures_short_baseline_v1"]
    baseline_by_side = futures_baseline["portfolio"].get("by_side", {})
    baseline_long = baseline_by_side.get("LONG", _empty_side())
    baseline_short = baseline_by_side.get("SHORT", _empty_side())
    lines = ["", "## Direction-specific candidate deltas", "",
        "| Profile pair | LONG total Δ | LONG train Δ | LONG test Δ | SHORT total Δ |",
        "|---|---:|---:|---:|---:|",
    ]
    for profile_id, row in report["futures"].items():
        by_side = row["portfolio"]["by_side"]
        long_side = by_side.get("LONG", _empty_side())
        short_side = by_side.get("SHORT", _empty_side())
        lines.append(
            f"| {profile_id} | "
            f"{round(long_side['closed']['net_pnl'] - baseline_long['closed']['net_pnl'], 2)} | "
            f"{round(long_side['train']['net_pnl'] - baseline_long['train']['net_pnl'], 2)} | "
            f"{round(long_side['test']['net_pnl'] - baseline_long['test']['net_pnl'], 2)} | "
            f"{round(short_side['closed']['net_pnl'] - baseline_short['closed']['net_pnl'], 2)} |"
        )
    return lines


def _stability(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Seven-day direction stability", "",
        "| Profile | Side | Buckets | Positive | Negative | Best net | Worst net |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for profile_id, row in report["futures"].items():
        long_id = str(row["long_profile"]["profile_id"])
        short_id = str(row["short_profile"]["profile_id"])
        sides: list[str] = []
        if profile_id == "futures_long_baseline_v1__futures_short_baseline_v1":
            sides = ["LONG", "SHORT"]
        else:
            if long_id != "futures_long_baseline_v1":
                sides.append("LONG")
            if short_id != "futures_short_baseline_v1":
                sides.append("SHORT")
        for side in sides:
            values = [
                float(bucket.get("by_side", {}).get(side, {}).get("net_pnl", 0.0))
                for bucket in row["portfolio"]["rolling_7d"]
                if side in bucket.get("by_side", {})
            ]
            positive = sum(value > 0 for value in values)
            negative = sum(value < 0 for value in values)
            lines.append(
                f"| {profile_id} | {side} | {len(values)} | {positive} | {negative} | "
                f"{round(max(values), 2) if values else 0.0} | {round(min(values), 2) if values else 0.0} |"
            )
    return lines


def _market_context(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Seven-day market context", "",
        "| Period | BTC return | Avg RSI | Avg ADX | Avg ATR growth | Avg ATR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("futures_market_context_7d", []):
        lines.append(
            f"| {row['start_date']} | {row['price_return_pct']}% | {row['avg_rsi']} | "
            f"{row['avg_adx']} | {row['avg_atr_growth_20']} | {row['avg_atr']} |"
        )
    return lines


def _outcome_audit(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Baseline SHORT admitted-outcome audit", "",
        "### Stable negative cohorts", "",
        "| Feature | Value | Trades | Net | Train | Test |",
        "|---|---|---:|---:|---:|---:|",
    ]
    short_audit = report.get("baseline_outcome_audit", {}).get("SHORT", {})
    for row in short_audit.get("stable_negative", [])[:10]:
        lines.append(
            f"| {row['feature']} | {row['value']} | {row['all']['trades']} | "
            f"{row['all']['net_pnl']} | {row['train']['net_pnl']} | {row['test']['net_pnl']} |"
        )
    lines.extend(["", "### Stable positive cohorts", "",
        "| Feature | Value | Trades | Net | Train | Test |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in short_audit.get("stable_positive", [])[:10]:
        lines.append(
            f"| {row['feature']} | {row['value']} | {row['all']['trades']} | "
            f"{row['all']['net_pnl']} | {row['train']['net_pnl']} | {row['test']['net_pnl']} |"
        )
    return lines


def _blockers(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Permission blocker counts", ""]
    for market in ("spot", "futures"):
        lines.extend([f"### {market.upper()}", ""])
        for profile_id, row in report[market].items():
            blockers = ", ".join(f"{key}={value}" for key, value in row["permission_blockers"].items())
            lines.append(f"- `{profile_id}`: {blockers or 'none'}")
        lines.append("")
    return lines


def markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    for section in (
        _header,
        _fidelity,
        _spot_table,
        _futures_table,
        _candidate_deltas,
        _stability,
        _market_context,
        _outcome_audit,
        _blockers,
    ):
        lines.extend(section(report))
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"portfolio_state_replay_{stamp}.json"
    markdown_path = output_root / f"portfolio_state_replay_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown(report), encoding="utf-8")
    return json_path, markdown_path
