"""Reconstruct current component scores on historical signal timestamps.

This is a report-only first-stage replay. It rebuilds point-in-time Spot,
Futures LONG, and Futures SHORT component scores from frozen indicator and
orderflow history, then evaluates remove-one-component filters on trades that
were actually executed. It does not invent outcomes for entries that were not
historically opened; full portfolio simulation is a later stage.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from platform_v2.futures.config import settings as futures_settings
from platform_v2.futures.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository as FuturesIndicatorRepository,
)
from platform_v2.futures.domain.models.orderbook_snapshot import (
    OrderbookSnapshot as FuturesOrderbookSnapshot,
)
from platform_v2.futures.services.signal.futures_component_score_service import (
    FuturesComponentScoreService,
)
from platform_v2.futures.services.signal.futures_mtf_context_service import (
    MultiTimeframeContextService as FuturesMtfService,
)
from platform_v2.spot.config import settings as spot_settings
from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository as SpotIndicatorRepository,
)
from platform_v2.spot.domain.models.orderbook_snapshot import (
    OrderbookSnapshot as SpotOrderbookSnapshot,
)
from platform_v2.spot.services.signal.mtf_context_service import (
    MultiTimeframeContextService as SpotMtfService,
)
from platform_v2.tools.research.replay.legacy_spot_signal import (
    SignalDecisionService as SpotSignalService,
)
from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots


COMPONENTS = ("mtf", "regime", "trend", "momentum", "orderbook", "structure")
TIMEFRAMES = ("5m", "15m", "4h")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_family(folder: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not folder.is_dir():
        return rows
    for path in sorted(folder.glob("*.json")):
        payload = _load_json(path)
        if isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _timestamp_ms(value: Any, *, end_of_second: bool = False) -> int | None:
    if isinstance(value, (int, float)):
        parsed = int(value)
        return parsed if parsed > 0 else None
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        parsed = int(text)
        return parsed if parsed > 0 else None
    try:
        parsed_dt = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None
    return int(parsed_dt.timestamp() * 1000) + (999 if end_of_second else 0)


def _row_timestamp(row: dict[str, Any], *, end_of_second: bool = False) -> int | None:
    for key in ("timestamp_ms", "close_time_ms", "timestamp", "close_time"):
        value = _timestamp_ms(row.get(key), end_of_second=end_of_second)
        if value is not None:
            return value
    for key in ("datetime", "timestamp_text", "close_time_readable", "time_readable"):
        value = _timestamp_ms(row.get(key), end_of_second=end_of_second)
        if value is not None:
            return value
    return None


class _AsOfIndex:
    def __init__(self, values: list[tuple[int, Any]]) -> None:
        ordered = sorted(values, key=lambda item: item[0])
        self.timestamps = [item[0] for item in ordered]
        self.values = [item[1] for item in ordered]

    def at(self, timestamp_ms: int, *, tolerance_ms: int = 0) -> Any | None:
        index = bisect_right(self.timestamps, timestamp_ms + tolerance_ms) - 1
        return self.values[index] if index >= 0 else None

    def __len__(self) -> int:
        return len(self.values)


def _indicator_index(
    path: Path,
    *,
    symbol: str,
    timeframe: str,
    parser: Callable[..., Any],
    repair_macd_histogram: bool = False,
) -> _AsOfIndex:
    payload = _load_json(path)
    rows = payload if isinstance(payload, list) else []
    values: list[tuple[int, Any]] = []
    histogram_history: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed_row = row
        if repair_macd_histogram:
            macd = row.get("macd")
            macd_signal = row.get("macd_signal")
            try:
                if macd is not None and macd_signal is not None:
                    histogram_history.append(round(float(macd) - float(macd_signal), 5))
            except (TypeError, ValueError):
                pass
            parsed_row = {**row, "macd_histogram": histogram_history[-3:]}
        timestamp_ms = _row_timestamp(parsed_row, end_of_second=True)
        snapshot = parser(symbol=symbol, timeframe=timeframe, row=parsed_row)
        if timestamp_ms is not None and snapshot is not None:
            values.append((timestamp_ms, snapshot))
    return _AsOfIndex(values)


def _orderbook_index(path: Path, *, market: str) -> _AsOfIndex:
    payload = _load_json(path)
    rows = payload if isinstance(payload, list) else []
    model = FuturesOrderbookSnapshot if market == "futures" else SpotOrderbookSnapshot
    default_source = "binance_futures_aggtrades" if market == "futures" else "binance_aggtrades"
    values: list[tuple[int, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp_ms = _row_timestamp(row)
        if timestamp_ms is None:
            continue
        try:
            snapshot = model(
                symbol=str(row.get("symbol") or "BTCUSDT"),
                timeframe=str(row.get("timeframe") or "15m"),
                timestamp_text=str(row.get("timestamp_text") or row.get("datetime") or ""),
                buyers=_float(row.get("buyers")),
                sellers=_float(row.get("sellers")),
                dominance_ratio=_float(row.get("dominance_ratio")),
                imbalance=_float(row.get("imbalance")),
                momentum_classification=str(
                    row.get("momentum_classification") or row.get("classification") or "neutral"
                ),
                period_count=int(row.get("period_count") or 0),
                source=str(row.get("source") or default_source),
            )
        except (TypeError, ValueError):
            continue
        values.append((timestamp_ms, snapshot))
    return _AsOfIndex(values)


def _score(components: dict[str, float], weights: dict[str, float], omit: str | None = None) -> float:
    return round(
        sum(
            _float(components.get(name)) * _float(weights.get(name))
            for name in COMPONENTS
            if name != omit
        ),
        2,
    )


def _cycle_decision_times(folder: Path) -> dict[int, int]:
    result: dict[int, int] = {}
    for row in _load_family(folder):
        candle_timestamp = _timestamp_ms(row.get("cycle_note"), end_of_second=True)
        decision_timestamp = _timestamp_ms(row.get("datetime"))
        if candle_timestamp is not None and decision_timestamp is not None:
            result[candle_timestamp] = decision_timestamp
    return result


def _reconstruct_spot(
    spot_root: Path,
    *,
    repair_macd_histogram: bool = False,
) -> list[dict[str, Any]]:
    indicator_root = spot_root / "indicator_snapshots" / "BTCUSDT"
    indexes = {
        timeframe: _indicator_index(
            indicator_root / f"{timeframe}.json",
            symbol="BTCUSDT",
            timeframe=timeframe,
            parser=SpotIndicatorRepository._parse_snapshot_row,
            repair_macd_histogram=repair_macd_histogram,
        )
        for timeframe in TIMEFRAMES
    }
    orderbook = _orderbook_index(
        spot_root / "orderflow" / "BTCUSDT" / "15m.json",
        market="spot",
    )
    mtf_service = SpotMtfService()
    signal_service = SpotSignalService()
    decision_times = _cycle_decision_times(spot_root / "cycle_runs")
    results: list[dict[str, Any]] = []
    seen: set[int] = set()
    for signal in sorted(_load_family(spot_root / "signals"), key=lambda row: int(row.get("timestamp_ms") or 0)):
        timestamp_ms = int(signal.get("timestamp_ms") or 0)
        if timestamp_ms <= 0 or timestamp_ms in seen:
            continue
        seen.add(timestamp_ms)
        snapshots = {timeframe: indexes[timeframe].at(timestamp_ms) for timeframe in TIMEFRAMES}
        primary = snapshots.get("15m")
        if primary is None:
            continue
        mtf_signals, mtf_direction = mtf_service.build_signals(
            timeframe_snapshots=snapshots,
            primary_timeframe="15m",
        )
        context = SimpleNamespace(
            symbol="BTCUSDT",
            timeframe="15m",
            latest_snapshot=primary,
            latest_orderbook=orderbook.at(decision_times.get(timestamp_ms, timestamp_ms)),
            mtf_signals=mtf_signals,
            mtf_direction=mtf_direction,
        )
        components = signal_service._build_buy_component_scores(context)
        results.append(
            {
                "market": "spot",
                "timestamp_ms": timestamp_ms,
                "date": datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date().isoformat(),
                "side": "BUY",
                "components": {key: round(_float(value), 4) for key, value in components.items()},
                "score": _score(components, spot_settings.SIGNAL_COMPONENT_WEIGHTS),
                "persisted_score": _float(signal.get("score")),
                "persisted_components": signal.get("component_scores"),
            }
        )
    return results


def _reconstruct_futures(
    futures_root: Path,
    *,
    repair_macd_histogram: bool = False,
) -> list[dict[str, Any]]:
    indicator_root = futures_root / "indicator_snapshots_futures" / "BTCUSDT"
    indexes = {
        timeframe: _indicator_index(
            indicator_root / f"indicators_{timeframe}.json",
            symbol="BTCUSDT",
            timeframe=timeframe,
            parser=FuturesIndicatorRepository._parse_snapshot_row,
            repair_macd_histogram=repair_macd_histogram,
        )
        for timeframe in TIMEFRAMES
    }
    orderbook = _orderbook_index(
        futures_root / "orderflow_futures" / "BTCUSDT" / "orderflow_15m.json",
        market="futures",
    )
    mtf_service = FuturesMtfService()
    component_service = FuturesComponentScoreService()
    decision_times = _cycle_decision_times(futures_root / "futures_cycle_runs")
    results: list[dict[str, Any]] = []
    seen: set[int] = set()
    for signal in sorted(
        _load_family(futures_root / "futures_signals"),
        key=lambda row: int(row.get("timestamp_ms") or 0),
    ):
        timestamp_ms = int(signal.get("timestamp_ms") or 0)
        if timestamp_ms <= 0 or timestamp_ms in seen:
            continue
        seen.add(timestamp_ms)
        snapshots = {timeframe: indexes[timeframe].at(timestamp_ms) for timeframe in TIMEFRAMES}
        primary = snapshots.get("15m")
        if primary is None:
            continue
        mtf_signals, mtf_direction = mtf_service.build_signals(
            timeframe_snapshots=snapshots,
            primary_timeframe="15m",
        )
        context = SimpleNamespace(
            symbol="BTCUSDT",
            timeframe="15m",
            latest_snapshot=primary,
            latest_orderbook=orderbook.at(decision_times.get(timestamp_ms, timestamp_ms)),
            mtf_signals=mtf_signals,
            mtf_direction=mtf_direction,
        )
        persisted_components = signal.get("direction_component_scores")
        for side, components in (
            ("LONG", component_service.build_long_component_scores(context)),
            ("SHORT", component_service.build_short_component_scores(context)),
        ):
            persisted_side = (
                persisted_components.get(side.lower())
                if isinstance(persisted_components, dict)
                else None
            )
            results.append(
                {
                    "market": "futures",
                    "timestamp_ms": timestamp_ms,
                    "date": datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date().isoformat(),
                    "side": side,
                    "components": {key: round(_float(value), 4) for key, value in components.items()},
                    "score": _score(components, futures_settings.SIGNAL_COMPONENT_WEIGHTS),
                    "persisted_score": _float((signal.get("direction_scores") or {}).get(side.lower())),
                    "persisted_components": persisted_side,
                }
            )
    return results


def _opened_at_ms(value: Any) -> int | None:
    return _timestamp_ms(value, end_of_second=True)


def _trade_rows(
    roots: ResearchDataRoots,
    reconstructed: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    score_by_key = {
        (row["market"], int(row["timestamp_ms"]), row["side"]): row
        for row in reconstructed
    }
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    positions: dict[str, dict[str, Any]] = {}
    for position in _load_family(roots.spot / "positions"):
        position_id = str(position.get("position_id") or "")
        if position_id:
            positions[position_id] = position
    for position in positions.values():
        if str(position.get("status") or "").upper() != "CLOSED":
            continue
        opened_at = _opened_at_ms(position.get("opened_at"))
        replay = score_by_key.get(("spot", int(opened_at or 0), "BUY"))
        if replay is not None:
            groups["spot"].append({**replay, "position_id": position.get("position_id"), "net_pnl": _float(position.get("net_pnl"))})

    audits: dict[str, dict[str, Any]] = {}
    for audit in _load_family(roots.futures / "futures_trade_entry_audits"):
        position_id = str(audit.get("position_id") or "")
        if position_id:
            audits[position_id] = audit
    for audit in audits.values():
        side = str(audit.get("side") or "").upper()
        timestamp_ms = int(audit.get("entry_timestamp_ms") or 0)
        replay = score_by_key.get(("futures", timestamp_ms, side))
        if replay is not None:
            key = "futures_long" if side == "LONG" else "futures_short"
            groups[key].append({**replay, "position_id": audit.get("position_id"), "net_pnl": _float(audit.get("net_pnl"))})
    return dict(groups)


def _stats(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    trades = len(rows)
    net_pnl = round(sum(_float(row.get("net_pnl")) for row in rows), 2)
    wins = sum(1 for row in rows if _float(row.get("net_pnl")) > 0)
    return {
        "trades": trades,
        "wins": wins,
        "win_rate": round(wins / trades * 100.0, 2) if trades else 0.0,
        "net_pnl": net_pnl,
        "avg_net_pnl": round(net_pnl / trades, 4) if trades else 0.0,
    }


def _remove_one(rows: list[dict[str, Any]], *, weights: dict[str, float], threshold: float) -> dict[str, Any]:
    result: dict[str, Any] = {"baseline_executed": _stats(rows), "components": {}}
    dates = sorted({str(row.get("date") or "") for row in rows if row.get("date")})
    split_date = dates[min(max(1, len(dates) * 2 // 3), len(dates) - 1)] if len(dates) >= 2 else None
    for component in COMPONENTS:
        enriched = [
            {**row, "candidate_score": _score(row["components"], weights, omit=component)}
            for row in rows
        ]
        kept = [row for row in enriched if row["candidate_score"] >= threshold]
        removed = [row for row in enriched if row["candidate_score"] < threshold]
        train = [row for row in kept if split_date is None or str(row.get("date")) < split_date]
        test = [row for row in kept if split_date is not None and str(row.get("date")) >= split_date]
        result["components"][component] = {
            "kept": _stats(kept),
            "removed": _stats(removed),
            "train_kept": _stats(train),
            "test_kept": _stats(test),
        }
    result["test_start"] = split_date
    return result


def _single_weight_search(
    rows: list[dict[str, Any]],
    *,
    weights: dict[str, float],
    baseline_threshold: float,
) -> dict[str, Any]:
    dates = sorted({str(row.get("date") or "") for row in rows if row.get("date")})
    split_date = dates[min(max(1, len(dates) * 2 // 3), len(dates) - 1)] if len(dates) >= 2 else None
    multipliers = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5)
    thresholds = (8.0, 8.5, 9.0, 9.5, 10.0, 10.5)
    candidates: list[dict[str, Any]] = []
    for component in COMPONENTS:
        for multiplier in multipliers:
            candidate_weights = dict(weights)
            candidate_weights[component] = round(_float(weights.get(component)) * multiplier, 4)
            for threshold in thresholds:
                kept = [
                    row
                    for row in rows
                    if _score(row["components"], candidate_weights) >= threshold
                ]
                train = [
                    row
                    for row in kept
                    if split_date is None or str(row.get("date")) < split_date
                ]
                test = [
                    row
                    for row in kept
                    if split_date is not None and str(row.get("date")) >= split_date
                ]
                all_stats = _stats(kept)
                train_stats = _stats(train)
                test_stats = _stats(test)
                stable = bool(
                    train_stats["trades"] >= 5
                    and test_stats["trades"] >= 5
                    and train_stats["net_pnl"] > 0
                    and test_stats["net_pnl"] > 0
                )
                candidates.append(
                    {
                        "component": component,
                        "multiplier": multiplier,
                        "weight": candidate_weights[component],
                        "threshold": threshold,
                        "stable_positive": stable,
                        "all": all_stats,
                        "train": train_stats,
                        "test": test_stats,
                    }
                )
    ranked = sorted(
        candidates,
        key=lambda row: (
            not bool(row["stable_positive"]),
            -_float(row["test"]["avg_net_pnl"]),
            -_float(row["train"]["avg_net_pnl"]),
            -int(row["all"]["trades"]),
        ),
    )
    baseline_kept = [
        row for row in rows if _score(row["components"], weights) >= baseline_threshold
    ]
    return {
        "test_start": split_date,
        "baseline_current_filter": _stats(baseline_kept),
        "stable_positive_candidates": sum(1 for row in candidates if row["stable_positive"]),
        "top_candidates": ranked[:20],
    }


def _validation(reconstructed: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [row for row in reconstructed if isinstance(row.get("persisted_components"), dict)]
    exact_components = 0
    exact_scores = 0
    max_score_delta = 0.0
    for row in comparable:
        persisted = row["persisted_components"]
        if all(abs(_float(row["components"].get(name)) - _float(persisted.get(name))) < 1e-9 for name in COMPONENTS):
            exact_components += 1
        delta = abs(_float(row.get("score")) - _float(row.get("persisted_score")))
        max_score_delta = max(max_score_delta, delta)
        if delta < 1e-9:
            exact_scores += 1
    return {
        "comparable_rows": len(comparable),
        "exact_component_rows": exact_components,
        "exact_score_rows": exact_scores,
        "max_score_delta": round(max_score_delta, 6),
    }


def build_report(snapshot_root: Path) -> dict[str, Any]:
    roots = ResearchDataRoots.from_snapshot(snapshot_root)
    spot = _reconstruct_spot(roots.spot)
    futures = _reconstruct_futures(roots.futures)
    reconstructed = [*spot, *futures]
    trades = _trade_rows(roots, reconstructed)
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": str(snapshot_root.expanduser().resolve()),
        "method": "current_logic_point_in_time_component_reconstruction",
        "scope_warning": (
            "Remove-one results cover historically executed trades only. They measure which old "
            "winners and losers a candidate would retain, not PnL from newly created entries."
        ),
        "reconstruction": {
            "spot_rows": len(spot),
            "futures_direction_rows": len(futures),
            "validation": _validation(reconstructed),
        },
        "spot": _remove_one(
            trades.get("spot", []),
            weights=spot_settings.SIGNAL_COMPONENT_WEIGHTS,
            threshold=spot_settings.BUY_THRESHOLD,
        ),
        "futures_long": _remove_one(
            trades.get("futures_long", []),
            weights=futures_settings.SIGNAL_COMPONENT_WEIGHTS,
            threshold=futures_settings.BUY_THRESHOLD,
        ),
        "futures_short": _remove_one(
            trades.get("futures_short", []),
            weights=futures_settings.SIGNAL_COMPONENT_WEIGHTS,
            threshold=futures_settings.BUY_THRESHOLD,
        ),
        "single_weight_search": {
            "spot": _single_weight_search(
                trades.get("spot", []),
                weights=spot_settings.SIGNAL_COMPONENT_WEIGHTS,
                baseline_threshold=spot_settings.BUY_THRESHOLD,
            ),
            "futures_long": _single_weight_search(
                trades.get("futures_long", []),
                weights=futures_settings.SIGNAL_COMPONENT_WEIGHTS,
                baseline_threshold=futures_settings.BUY_THRESHOLD,
            ),
            "futures_short": _single_weight_search(
                trades.get("futures_short", []),
                weights=futures_settings.SIGNAL_COMPONENT_WEIGHTS,
                baseline_threshold=futures_settings.BUY_THRESHOLD,
            ),
        },
        "reconstructed_rows": reconstructed,
    }


def _markdown(report: dict[str, Any]) -> str:
    validation = report["reconstruction"]["validation"]
    lines = [
        "# Historical Component Replay",
        "",
        f"Generated: `{report['generated_at_utc']} UTC`",
        f"Snapshot: `{report['snapshot']}`",
        "",
        f"Reconstructed Spot rows: `{report['reconstruction']['spot_rows']}`",
        f"Reconstructed Futures direction rows: `{report['reconstruction']['futures_direction_rows']}`",
        f"Validation exact component rows: `{validation['exact_component_rows']}/{validation['comparable_rows']}`",
        f"Validation max score delta: `{validation['max_score_delta']}`",
        "",
        f"> {report['scope_warning']}",
        "",
    ]
    for key, title in (("spot", "SPOT"), ("futures_long", "FUTURES LONG"), ("futures_short", "FUTURES SHORT")):
        section = report[key]
        baseline = section["baseline_executed"]
        lines.extend([
            f"## {title}",
            "",
            f"Matched executed baseline: trades=`{baseline['trades']}`, win_rate=`{baseline['win_rate']}%`, net_pnl=`{baseline['net_pnl']}`",
            f"Test starts: `{section['test_start']}`",
            "",
            "| Removed component | Kept n | Kept PnL | Removed n | Removed PnL | Train kept PnL | Test kept PnL |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for component, values in section["components"].items():
            lines.append(
                f"| {component.upper()} | {values['kept']['trades']} | {values['kept']['net_pnl']} | "
                f"{values['removed']['trades']} | {values['removed']['net_pnl']} | "
                f"{values['train_kept']['net_pnl']} | {values['test_kept']['net_pnl']} |"
            )
        lines.append("")
        search = report["single_weight_search"][key]
        current_filter = search["baseline_current_filter"]
        lines.extend([
            "### Single-weight and threshold search",
            "",
            f"Current-logic retained cohort: trades=`{current_filter['trades']}`, net_pnl=`{current_filter['net_pnl']}`",
            f"Stable positive candidates: `{search['stable_positive_candidates']}`",
            "",
            "| Component | Multiplier | Weight | Threshold | Stable | Trades | PnL | Train PnL | Test PnL |",
            "|---|---:|---:|---:|---|---:|---:|---:|---:|",
        ])
        for candidate in search["top_candidates"][:10]:
            lines.append(
                f"| {str(candidate['component']).upper()} | {candidate['multiplier']} | "
                f"{candidate['weight']} | {candidate['threshold']} | "
                f"{'yes' if candidate['stable_positive'] else 'no'} | "
                f"{candidate['all']['trades']} | {candidate['all']['net_pnl']} | "
                f"{candidate['train']['net_pnl']} | {candidate['test']['net_pnl']} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"historical_component_replay_{stamp}.json"
    markdown_path = output_root / f"historical_component_replay_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruct historical component scores.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    args = parser.parse_args()
    report = build_report(args.snapshot)
    for path in write_report(report, args.output_root.expanduser().resolve()):
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
