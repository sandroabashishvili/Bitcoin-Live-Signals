"""Replay candidate signals candle-by-candle to theoretical TP/SL outcomes.

This stage covers every historical signal timestamp, including candidate
entries that were not actually opened. Signals are evaluated independently;
portfolio slot, cooldown, proximity, and overlapping-capital constraints are
reserved for the subsequent portfolio replay.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from platform_v2.futures.config import settings as futures_settings
from platform_v2.futures.domain.models.signal import SignalSide as FuturesSignalSide
from platform_v2.futures.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository as FuturesIndicatorRepository,
)
from platform_v2.futures.services.trading.futures_sl_tp_service import (
    StopLossTakeProfitService as FuturesSlTpService,
)
from platform_v2.spot.config import settings as spot_settings
from platform_v2.spot.domain.models.signal import SignalSide as SpotSignalSide
from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository as SpotIndicatorRepository,
)
from platform_v2.spot.services.trading.sl_tp_service import (
    StopLossTakeProfitService as SpotSlTpService,
)
from platform_v2.spot.services.trading.setup_confidence import normalized_setup_confidence
from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots
from platform_v2.tools.research.replay.candidate_profiles import PROFILES, CandidateProfile
from platform_v2.tools.research.replay.historical_component_replay import (
    _float,
    _indicator_index,
    _load_json,
    _reconstruct_futures,
    _reconstruct_spot,
    _row_timestamp,
)


def _candle_rows(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    rows = payload if isinstance(payload, list) else []
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp_ms = _row_timestamp(row, end_of_second=True)
        if timestamp_ms is None:
            continue
        result.append(
            {
                "timestamp_ms": timestamp_ms,
                "high": _float(row.get("high")),
                "low": _float(row.get("low")),
                "close": _float(row.get("close")),
            }
        )
    return sorted(result, key=lambda row: int(row["timestamp_ms"]))


def _outcome(
    *,
    candles: list[dict[str, Any]],
    candle_timestamps: list[int],
    entry_timestamp_ms: int,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    notional: float,
    entry_fee_rate: float,
    exit_fee_rate: float,
) -> dict[str, Any] | None:
    start = bisect_right(candle_timestamps, entry_timestamp_ms)
    if start >= len(candles) or entry <= 0 or notional <= 0:
        return None
    quantity = notional / entry
    exit_price = candles[-1]["close"]
    exit_timestamp_ms = int(candles[-1]["timestamp_ms"])
    resolution = "DATA_END"
    for candle in candles[start:]:
        high = _float(candle.get("high"))
        low = _float(candle.get("low"))
        if side in {"BUY", "LONG"}:
            stop_hit = low <= stop_loss
            target_hit = high >= take_profit
        else:
            stop_hit = high >= stop_loss
            target_hit = low <= take_profit
        if stop_hit and target_hit:
            exit_price = stop_loss
            resolution = "SL_AMBIGUOUS_CANDLE"
        elif stop_hit:
            exit_price = stop_loss
            resolution = "SL"
        elif target_hit:
            exit_price = take_profit
            resolution = "TP"
        else:
            continue
        exit_timestamp_ms = int(candle["timestamp_ms"])
        break
    direction = 1.0 if side in {"BUY", "LONG"} else -1.0
    gross_pnl = (exit_price - entry) * quantity * direction
    entry_fee = notional * entry_fee_rate
    exit_fee = quantity * exit_price * exit_fee_rate
    return {
        "entry_timestamp_ms": entry_timestamp_ms,
        "exit_timestamp_ms": exit_timestamp_ms,
        "side": side,
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "exit": round(exit_price, 2),
        "resolution": resolution,
        "gross_pnl": round(gross_pnl, 4),
        "fees": round(entry_fee + exit_fee, 4),
        "net_pnl": round(gross_pnl - entry_fee - exit_fee, 4),
    }


def _stats(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(outcomes, key=lambda row: (int(row["exit_timestamp_ms"]), int(row["entry_timestamp_ms"])))
    net_pnl = round(sum(_float(row.get("net_pnl")) for row in ordered), 2)
    wins = sum(1 for row in ordered if _float(row.get("net_pnl")) > 0)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for row in ordered:
        equity += _float(row.get("net_pnl"))
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    resolutions: dict[str, int] = {}
    for row in ordered:
        key = str(row.get("resolution") or "UNKNOWN")
        resolutions[key] = resolutions.get(key, 0) + 1
    return {
        "trades": len(ordered),
        "wins": wins,
        "win_rate": round(wins / len(ordered) * 100.0, 2) if ordered else 0.0,
        "net_pnl": net_pnl,
        "avg_net_pnl": round(net_pnl / len(ordered), 4) if ordered else 0.0,
        "max_sequential_drawdown": round(max_drawdown, 2),
        "resolutions": resolutions,
    }


def _spot_replay(
    roots: ResearchDataRoots,
    *,
    repair_macd_histogram: bool,
) -> dict[str, Any]:
    rows = _reconstruct_spot(
        roots.spot,
        repair_macd_histogram=repair_macd_histogram,
    )
    snapshots = _indicator_index(
        roots.spot / "indicator_snapshots" / "BTCUSDT" / "15m.json",
        symbol="BTCUSDT",
        timeframe="15m",
        parser=SpotIndicatorRepository._parse_snapshot_row,
        repair_macd_histogram=repair_macd_histogram,
    )
    candles = _candle_rows(roots.spot / "candles" / "BTCUSDT" / "15m.json")
    candle_timestamps = [int(row["timestamp_ms"]) for row in candles]
    sl_tp = SpotSlTpService()
    reports: dict[str, Any] = {}
    for profile_id in ("spot_baseline_v1", "spot_orderbook_zero_v1"):
        profile = PROFILES[profile_id]
        outcomes: list[dict[str, Any]] = []
        actionable = 0
        for row in rows:
            score = profile.score(row["components"])
            if score < profile.threshold:
                continue
            actionable += 1
            timestamp_ms = int(row["timestamp_ms"])
            snapshot = snapshots.at(timestamp_ms)
            if snapshot is None:
                continue
            setup = sl_tp.build_theoretical_setup(
                side=SpotSignalSide.BUY,
                entry_price=float(snapshot.price),
                snapshot=snapshot,
                confidence=normalized_setup_confidence(score),
            )
            if setup is None:
                continue
            outcome = _outcome(
                candles=candles,
                candle_timestamps=candle_timestamps,
                entry_timestamp_ms=timestamp_ms,
                side="BUY",
                entry=float(snapshot.price),
                stop_loss=float(setup.stop_loss),
                take_profit=float(setup.take_profit),
                notional=float(spot_settings.DEFAULT_POSITION_SIZE),
                entry_fee_rate=float(spot_settings.ENTRY_FEE_PCT),
                exit_fee_rate=float(spot_settings.EXIT_FEE_PCT),
            )
            if outcome is not None:
                outcomes.append({**outcome, "score": score})
        reports[profile_id] = {
            "profile": profile.__dict__,
            "evaluated_signal_rows": len(rows),
            "actionable_signals": actionable,
            "outcome_stats": _stats(outcomes),
        }
    return reports


def _futures_profile_pairs() -> tuple[tuple[CandidateProfile, CandidateProfile], ...]:
    long_baseline = PROFILES["futures_long_baseline_v1"]
    short_baseline = PROFILES["futures_short_baseline_v1"]
    return (
        (long_baseline, short_baseline),
        (PROFILES["futures_long_mtf_half_v1"], short_baseline),
        (long_baseline, PROFILES["futures_short_momentum_zero_v1"]),
        (long_baseline, PROFILES["futures_short_trend_half_t95_v1"]),
        (long_baseline, PROFILES["futures_short_structure_half_t10_v1"]),
    )


def _futures_replay(
    roots: ResearchDataRoots,
    *,
    repair_macd_histogram: bool,
) -> dict[str, Any]:
    reconstructed = _reconstruct_futures(
        roots.futures,
        repair_macd_histogram=repair_macd_histogram,
    )
    by_timestamp: dict[int, dict[str, dict[str, Any]]] = {}
    for row in reconstructed:
        by_timestamp.setdefault(int(row["timestamp_ms"]), {})[str(row["side"])] = row
    snapshots = _indicator_index(
        roots.futures / "indicator_snapshots_futures" / "BTCUSDT" / "indicators_15m.json",
        symbol="BTCUSDT",
        timeframe="15m",
        parser=FuturesIndicatorRepository._parse_snapshot_row,
        repair_macd_histogram=repair_macd_histogram,
    )
    candles = _candle_rows(
        roots.futures / "candles_futures" / "BTCUSDT" / "candles_15m.json"
    )
    candle_timestamps = [int(row["timestamp_ms"]) for row in candles]
    sl_tp = FuturesSlTpService()
    reports: dict[str, Any] = {}
    for long_profile, short_profile in _futures_profile_pairs():
        pair_id = f"{long_profile.profile_id}__{short_profile.profile_id}"
        outcomes: list[dict[str, Any]] = []
        actionable = 0
        selected_counts = {"LONG": 0, "SHORT": 0}
        for timestamp_ms, directions in sorted(by_timestamp.items()):
            long_row = directions.get("LONG")
            short_row = directions.get("SHORT")
            if long_row is None or short_row is None:
                continue
            long_score = long_profile.score(long_row["components"])
            short_score = short_profile.score(short_row["components"])
            long_actionable = long_score >= long_profile.threshold
            short_actionable = short_score >= short_profile.threshold
            if long_actionable and (not short_actionable or long_score >= short_score):
                side = "LONG"
                score = long_score
            elif short_actionable and short_score > long_score:
                side = "SHORT"
                score = short_score
            else:
                continue
            actionable += 1
            selected_counts[side] += 1
            snapshot = snapshots.at(timestamp_ms)
            if snapshot is None:
                continue
            signal_side = FuturesSignalSide.BUY if side == "LONG" else FuturesSignalSide.SELL
            setup = sl_tp.build_theoretical_setup(
                side=signal_side,
                entry_price=float(snapshot.price),
                snapshot=snapshot,
                confidence=min(1.0, max(0.0, score / 14.6)),
            )
            if setup is None:
                continue
            outcome = _outcome(
                candles=candles,
                candle_timestamps=candle_timestamps,
                entry_timestamp_ms=timestamp_ms,
                side=side,
                entry=float(snapshot.price),
                stop_loss=float(setup.stop_loss),
                take_profit=float(setup.take_profit),
                notional=float(futures_settings.DEFAULT_ORDER_SIZE_USDT * futures_settings.DEFAULT_LEVERAGE),
                entry_fee_rate=float(futures_settings.TAKER_FEE_PCT),
                exit_fee_rate=float(futures_settings.MAKER_FEE_PCT),
            )
            if outcome is not None:
                outcomes.append({**outcome, "score": score})
        reports[pair_id] = {
            "long_profile": long_profile.__dict__,
            "short_profile": short_profile.__dict__,
            "evaluated_timestamps": len(by_timestamp),
            "actionable_signals": actionable,
            "selected_counts": selected_counts,
            "outcome_stats": _stats(outcomes),
        }
    return reports


def build_report(
    snapshot_root: Path,
    *,
    repair_macd_histogram: bool = False,
) -> dict[str, Any]:
    roots = ResearchDataRoots.from_snapshot(snapshot_root)
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": str(snapshot_root.expanduser().resolve()),
        "method": "independent_signal_candle_tp_sl_replay",
        "macd_histogram_repaired": repair_macd_histogram,
        "warning": (
            "Signals are independent theoretical setups. Net PnL and sequential drawdown do not yet "
            "apply portfolio slots, cooldown, proximity, or overlapping capital constraints."
        ),
        "spot": _spot_replay(roots, repair_macd_histogram=repair_macd_histogram),
        "futures": _futures_replay(roots, repair_macd_histogram=repair_macd_histogram),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Candidate Signal Outcome Replay",
        "",
        f"Generated: `{report['generated_at_utc']} UTC`",
        f"Snapshot: `{report['snapshot']}`",
        f"MACD histogram repaired: `{report['macd_histogram_repaired']}`",
        "",
        f"> {report['warning']}",
        "",
        "## SPOT",
        "",
        "| Profile | Signals | Trades | Win rate | Net PnL | Avg | Drawdown |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for profile_id, row in report["spot"].items():
        stats = row["outcome_stats"]
        lines.append(
            f"| {profile_id} | {row['actionable_signals']} | {stats['trades']} | {stats['win_rate']}% | "
            f"{stats['net_pnl']} | {stats['avg_net_pnl']} | {stats['max_sequential_drawdown']} |"
        )
    lines.extend([
        "",
        "## FUTURES",
        "",
        "| Profile pair | Signals | LONG | SHORT | Trades | Win rate | Net PnL | Avg | Drawdown |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for profile_id, row in report["futures"].items():
        stats = row["outcome_stats"]
        lines.append(
            f"| {profile_id} | {row['actionable_signals']} | {row['selected_counts']['LONG']} | "
            f"{row['selected_counts']['SHORT']} | {stats['trades']} | {stats['win_rate']}% | "
            f"{stats['net_pnl']} | {stats['avg_net_pnl']} | {stats['max_sequential_drawdown']} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"candidate_signal_outcome_replay_{stamp}.json"
    markdown_path = output_root / f"candidate_signal_outcome_replay_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay candidate signals to candle outcomes.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    parser.add_argument("--repair-macd-histogram", action="store_true")
    args = parser.parse_args()
    report = build_report(
        args.snapshot,
        repair_macd_histogram=bool(args.repair_macd_histogram),
    )
    for path in write_report(report, args.output_root.expanduser().resolve()):
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
