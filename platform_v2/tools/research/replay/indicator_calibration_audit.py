"""Audit indicator bands against historical executed-trade outcomes.

The audit is point-in-time and report-only. Indicator snapshots are aligned to
the entry candle close while orderflow is aligned to the actual cycle runtime.
Associations on executed trades are evidence for calibration work, not causal
proof or a replacement for full portfolio replay.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from math import inf
from pathlib import Path
from typing import Any

from platform_v2.futures.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository as FuturesIndicatorRepository,
)
from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository as SpotIndicatorRepository,
)
from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots
from platform_v2.tools.research.replay.historical_component_replay import (
    _AsOfIndex,
    _cycle_decision_times,
    _float,
    _indicator_index,
    _orderbook_index,
    _reconstruct_futures,
    _reconstruct_spot,
    _trade_rows,
)


NUMERIC_BINS: dict[str, tuple[float, ...]] = {
    "rsi": (0, 30, 40, 50, 58, 65, 70, 100),
    "adx": (0, 15, 18, 20, 25, 30, 40, inf),
    "directional_di_delta": (-inf, -8, 0, 8, 20, inf),
    "adx_slope": (-inf, -2, -0.5, 0, 0.5, 2, inf),
    "atr_growth_20": (-inf, -0.2, -0.05, 0.05, 0.2, 0.5, inf),
    "directional_ema50_slope_atr": (-inf, -0.25, -0.05, 0, 0.05, 0.25, inf),
    "directional_ema50_distance_atr": (-inf, -2, -1, -0.4, 0, 0.8, 1.5, 3, inf),
    "directional_vwap_distance_atr": (-inf, -3, -1.5, -0.4, 0, 0.8, 1.5, 3, inf),
    "directional_macd_spread_atr": (-inf, -0.5, -0.2, 0, 0.2, 0.5, inf),
    "entry_from_swing_atr": (-inf, 0, 1, 1.5, 2.5, 4, 6, inf),
    "room_to_opposite_swing_atr": (-inf, 0, 0.5, 1, 1.5, 3, 6, inf),
    "directional_orderflow_ratio": (0, 0.7, 0.9, 1, 1.1, 1.3, 1.8, 3, inf),
    "directional_orderflow_imbalance": (-1, -0.5, -0.25, -0.05, 0, 0.05, 0.25, 0.5, 1.01),
}

CATEGORICAL_FEATURES = (
    "atr_spike",
    "price_vs_ema50",
    "ema_stack",
    "di_alignment",
    "macd_alignment",
    "bounce_confirmed",
)


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _ratio(numerator: Any, denominator: Any) -> float | None:
    top = _optional_float(numerator)
    bottom = _optional_float(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    return top / bottom


def _directional_delta(long_value: Any, short_value: Any, *, side: str) -> float | None:
    long_number = _optional_float(long_value)
    short_number = _optional_float(short_value)
    if long_number is None or short_number is None:
        return None
    return long_number - short_number if side in {"BUY", "LONG"} else short_number - long_number


def _directional_distance(price: Any, reference: Any, atr: Any, *, side: str) -> float | None:
    price_number = _optional_float(price)
    reference_number = _optional_float(reference)
    atr_number = _optional_float(atr)
    if price_number is None or reference_number is None or atr_number is None or atr_number <= 0:
        return None
    value = (price_number - reference_number) / atr_number
    return value if side in {"BUY", "LONG"} else -value


def _directional_slope(slope: Any, atr: Any, *, side: str) -> float | None:
    slope_number = _optional_float(slope)
    atr_number = _optional_float(atr)
    if slope_number is None or atr_number is None or atr_number <= 0:
        return None
    value = slope_number / atr_number
    return value if side in {"BUY", "LONG"} else -value


def _feature_row(trade: dict[str, Any], snapshot: Any, orderbook: Any) -> dict[str, Any]:
    side = str(trade["side"])
    is_long = side in {"BUY", "LONG"}
    atr = snapshot.atr
    if is_long:
        entry_from_swing = _ratio(snapshot.price - snapshot.swing_low, atr) if snapshot.swing_low is not None else None
        room_to_swing = _ratio(snapshot.swing_high - snapshot.price, atr) if snapshot.swing_high is not None else None
        directional_buyers = getattr(orderbook, "buyers", None)
        directional_sellers = getattr(orderbook, "sellers", None)
        directional_imbalance = getattr(orderbook, "imbalance", None)
    else:
        entry_from_swing = _ratio(snapshot.swing_high - snapshot.price, atr) if snapshot.swing_high is not None else None
        room_to_swing = _ratio(snapshot.price - snapshot.swing_low, atr) if snapshot.swing_low is not None else None
        directional_buyers = getattr(orderbook, "sellers", None)
        directional_sellers = getattr(orderbook, "buyers", None)
        raw_imbalance = _optional_float(getattr(orderbook, "imbalance", None))
        directional_imbalance = -raw_imbalance if raw_imbalance is not None else None

    ema50 = _optional_float(snapshot.ema50)
    ema200 = _optional_float(snapshot.ema200)
    price = _optional_float(snapshot.price)
    macd = _optional_float(snapshot.macd)
    macd_signal = _optional_float(snapshot.macd_signal)
    plus_di = _optional_float(snapshot.plus_di)
    minus_di = _optional_float(snapshot.minus_di)
    return {
        **trade,
        "features": {
            "rsi": _optional_float(snapshot.rsi),
            "adx": _optional_float(snapshot.adx),
            "directional_di_delta": _directional_delta(plus_di, minus_di, side=side),
            "adx_slope": _optional_float(snapshot.adx_slope),
            "atr_growth_20": _optional_float(snapshot.atr_growth_20),
            "directional_ema50_slope_atr": _directional_slope(snapshot.ema50_slope, atr, side=side),
            "directional_ema50_distance_atr": _directional_distance(price, ema50, atr, side=side),
            "directional_vwap_distance_atr": _directional_distance(price, snapshot.vwap, atr, side=side),
            "directional_macd_spread_atr": _directional_delta(macd, macd_signal, side=side) / atr
            if _directional_delta(macd, macd_signal, side=side) is not None and atr
            else None,
            "entry_from_swing_atr": entry_from_swing,
            "room_to_opposite_swing_atr": room_to_swing,
            "directional_orderflow_ratio": _ratio(directional_buyers, directional_sellers),
            "directional_orderflow_imbalance": directional_imbalance,
            "atr_spike": "true" if bool(snapshot.atr_spike) else "false",
            "price_vs_ema50": (
                "aligned"
                if price is not None and ema50 is not None and ((price > ema50) if is_long else (price < ema50))
                else "opposed"
            ),
            "ema_stack": (
                "aligned"
                if ema50 is not None and ema200 is not None and ((ema50 > ema200) if is_long else (ema50 < ema200))
                else "opposed"
            ),
            "di_alignment": (
                "aligned"
                if plus_di is not None and minus_di is not None and ((plus_di > minus_di) if is_long else (minus_di > plus_di))
                else "opposed"
            ),
            "macd_alignment": (
                "aligned"
                if macd is not None and macd_signal is not None and ((macd >= macd_signal) if is_long else (macd <= macd_signal))
                else "opposed"
            ),
            "bounce_confirmed": "true" if bool(snapshot.bounce_confirmed) else "false",
        },
    }


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


def _split_date(rows: list[dict[str, Any]]) -> str | None:
    dates = sorted({str(row.get("date") or "") for row in rows if row.get("date")})
    if len(dates) < 2:
        return None
    return dates[min(max(1, len(dates) * 2 // 3), len(dates) - 1)]


def _cohort_stats(rows: list[dict[str, Any]], split_date: str | None) -> dict[str, Any]:
    train = [row for row in rows if split_date is None or str(row.get("date")) < split_date]
    test = [row for row in rows if split_date is not None and str(row.get("date")) >= split_date]
    all_stats = _stats(rows)
    train_stats = _stats(train)
    test_stats = _stats(test)
    stable = "insufficient"
    if train_stats["trades"] >= 3 and test_stats["trades"] >= 3:
        if train_stats["net_pnl"] > 0 and test_stats["net_pnl"] > 0:
            stable = "positive"
        elif train_stats["net_pnl"] < 0 and test_stats["net_pnl"] < 0:
            stable = "negative"
        else:
            stable = "mixed"
    return {"all": all_stats, "train": train_stats, "test": test_stats, "stability": stable}


def _band_label(lower: float, upper: float) -> str:
    lower_text = "-inf" if lower == -inf else f"{lower:g}"
    upper_text = "inf" if upper == inf else f"{upper:g}"
    return f"[{lower_text}, {upper_text})"


def _numeric_feature(rows: list[dict[str, Any]], feature: str, edges: tuple[float, ...], split_date: str | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for lower, upper in zip(edges, edges[1:]):
        selected = [
            row
            for row in rows
            if (value := _optional_float((row.get("features") or {}).get(feature))) is not None
            and lower <= value < upper
        ]
        if selected:
            result.append({"band": _band_label(lower, upper), "from": lower, "to": upper, **_cohort_stats(selected, split_date)})
    return result


def _categorical_feature(rows: list[dict[str, Any]], feature: str, split_date: str | None) -> list[dict[str, Any]]:
    values = sorted({str((row.get("features") or {}).get(feature)) for row in rows if (row.get("features") or {}).get(feature) is not None})
    return [
        {
            "value": value,
            **_cohort_stats([row for row in rows if str((row.get("features") or {}).get(feature)) == value], split_date),
        }
        for value in values
    ]


def _segment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_date = _split_date(rows)
    numeric = {
        feature: _numeric_feature(rows, feature, edges, split_date)
        for feature, edges in NUMERIC_BINS.items()
    }
    categorical = {
        feature: _categorical_feature(rows, feature, split_date)
        for feature in CATEGORICAL_FEATURES
    }
    stable_positive: list[dict[str, Any]] = []
    stable_negative: list[dict[str, Any]] = []
    for feature, bands in {**numeric, **categorical}.items():
        for band in bands:
            item = {
                "feature": feature,
                "band": band.get("band", band.get("value")),
                **band,
            }
            if band["stability"] == "positive":
                stable_positive.append(item)
            elif band["stability"] == "negative":
                stable_negative.append(item)
    stable_positive.sort(key=lambda row: (-_float(row["all"]["avg_net_pnl"]), -int(row["all"]["trades"])))
    stable_negative.sort(key=lambda row: (_float(row["all"]["avg_net_pnl"]), -int(row["all"]["trades"])))
    return {
        "baseline": _stats(rows),
        "test_start": split_date,
        "numeric": numeric,
        "categorical": categorical,
        "stable_positive": stable_positive,
        "stable_negative": stable_negative,
    }


def _build_feature_rows(roots: ResearchDataRoots) -> dict[str, list[dict[str, Any]]]:
    reconstructed = [*_reconstruct_spot(roots.spot), *_reconstruct_futures(roots.futures)]
    trades = _trade_rows(roots, reconstructed)
    spot_index = _indicator_index(
        roots.spot / "indicator_snapshots" / "BTCUSDT" / "15m.json",
        symbol="BTCUSDT",
        timeframe="15m",
        parser=SpotIndicatorRepository._parse_snapshot_row,
    )
    futures_index = _indicator_index(
        roots.futures / "indicator_snapshots_futures" / "BTCUSDT" / "indicators_15m.json",
        symbol="BTCUSDT",
        timeframe="15m",
        parser=FuturesIndicatorRepository._parse_snapshot_row,
    )
    spot_orderbook = _orderbook_index(
        roots.spot / "orderflow" / "BTCUSDT" / "15m.json",
        market="spot",
    )
    futures_orderbook = _orderbook_index(
        roots.futures / "orderflow_futures" / "BTCUSDT" / "orderflow_15m.json",
        market="futures",
    )
    spot_decisions = _cycle_decision_times(roots.spot / "cycle_runs")
    futures_decisions = _cycle_decision_times(roots.futures / "futures_cycle_runs")
    result: dict[str, list[dict[str, Any]]] = {}
    for name, rows in trades.items():
        is_spot = name == "spot"
        indicator_index: _AsOfIndex = spot_index if is_spot else futures_index
        orderbook_index: _AsOfIndex = spot_orderbook if is_spot else futures_orderbook
        decision_times = spot_decisions if is_spot else futures_decisions
        enriched: list[dict[str, Any]] = []
        for trade in rows:
            timestamp_ms = int(trade["timestamp_ms"])
            snapshot = indicator_index.at(timestamp_ms)
            orderbook = orderbook_index.at(decision_times.get(timestamp_ms, timestamp_ms))
            if snapshot is not None:
                enriched.append(_feature_row(trade, snapshot, orderbook))
        result[name] = enriched
    return result


def build_report(snapshot_root: Path) -> dict[str, Any]:
    roots = ResearchDataRoots.from_snapshot(snapshot_root)
    rows = _build_feature_rows(roots)
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": str(snapshot_root.expanduser().resolve()),
        "method": "point_in_time_indicator_band_outcome_association",
        "warning": "Executed-trade association is not causal proof. Confirm candidates with full replay.",
        "spot": _segment(rows.get("spot", [])),
        "futures_long": _segment(rows.get("futures_long", [])),
        "futures_short": _segment(rows.get("futures_short", [])),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Indicator Calibration Audit",
        "",
        f"Generated: `{report['generated_at_utc']} UTC`",
        f"Snapshot: `{report['snapshot']}`",
        "",
        f"> {report['warning']}",
        "",
    ]
    for key, title in (("spot", "SPOT BUY"), ("futures_long", "FUTURES LONG"), ("futures_short", "FUTURES SHORT")):
        section = report[key]
        baseline = section["baseline"]
        lines.extend([
            f"## {title}",
            "",
            f"Baseline: trades=`{baseline['trades']}`, win_rate=`{baseline['win_rate']}%`, net_pnl=`{baseline['net_pnl']}`",
            f"Test starts: `{section['test_start']}`",
            "",
            "### Stable negative bands",
            "",
            "| Feature | Band | Trades | PnL | Avg | Train PnL | Test PnL |",
            "|---|---|---:|---:|---:|---:|---:|",
        ])
        for row in section["stable_negative"][:15]:
            lines.append(
                f"| {row['feature']} | {row['band']} | {row['all']['trades']} | {row['all']['net_pnl']} | "
                f"{row['all']['avg_net_pnl']} | {row['train']['net_pnl']} | {row['test']['net_pnl']} |"
            )
        lines.extend([
            "",
            "### Stable positive bands",
            "",
            "| Feature | Band | Trades | PnL | Avg | Train PnL | Test PnL |",
            "|---|---|---:|---:|---:|---:|---:|",
        ])
        for row in section["stable_positive"][:15]:
            lines.append(
                f"| {row['feature']} | {row['band']} | {row['all']['trades']} | {row['all']['net_pnl']} | "
                f"{row['all']['avg_net_pnl']} | {row['train']['net_pnl']} | {row['test']['net_pnl']} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"indicator_calibration_audit_{stamp}.json"
    markdown_path = output_root / f"indicator_calibration_audit_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit indicator bands against trade outcomes.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    args = parser.parse_args()
    report = build_report(args.snapshot)
    for path in write_report(report, args.output_root.expanduser().resolve()):
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
