"""File: signal_only_replay.py
Folder: platform_v2/tools/research/replay
Created date: 2026-03-30
Last updated date: 2026-03-30
Author: Codex
Purpose: Run a first signal-only historical replay for V2 using persisted candles, snapshots, and orderflow.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.indicator_snapshot import IndicatorSnapshot
from platform_v2.spot.domain.models.market_context import MarketContext
from platform_v2.spot.domain.models.orderbook_snapshot import OrderbookSnapshot
from platform_v2.spot.infrastructure.market_data.candle_repository import JsonCandleRepository
from platform_v2.spot.infrastructure.market_data.indicator_snapshot_repository import (
    JsonIndicatorSnapshotRepository,
)
from platform_v2.spot.services.signal.mtf_context_service import MultiTimeframeContextService
from platform_v2.tools.research.replay.legacy_spot_signal import SignalDecisionService
from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots


SPOT_DATA_ROOT = ResearchDataRoots.live().spot
REPLAY_OUTPUT_ROOT = CANONICAL_OUTPUT_ROOT


def _parse_utc_text(value: str) -> datetime:
    return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def _load_orderbook_rows(orderflow_path: Path) -> list[tuple[datetime, OrderbookSnapshot]]:
    if not orderflow_path.exists():
        return []

    raw_rows = json.loads(orderflow_path.read_text(encoding="utf-8"))
    if not isinstance(raw_rows, list):
        return []

    rows: list[tuple[datetime, OrderbookSnapshot]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        timestamp_text = str(row.get("timestamp_text") or "")
        if not timestamp_text:
            continue
        rows.append(
            (
                _parse_utc_text(timestamp_text),
                OrderbookSnapshot(
                    symbol=str(row.get("symbol") or settings.DEFAULT_SYMBOL),
                    timeframe=str(row.get("timeframe") or settings.DEFAULT_TIMEFRAME),
                    timestamp_text=timestamp_text,
                    buyers=float(row.get("buyers", 0.0) or 0.0),
                    sellers=float(row.get("sellers", 0.0) or 0.0),
                    dominance_ratio=float(row.get("dominance_ratio", 0.0) or 0.0),
                    imbalance=float(row.get("imbalance", 0.0) or 0.0),
                    momentum_classification=str(row.get("momentum_classification") or "neutral"),
                    period_count=int(row.get("period_count", 0) or 0),
                    source=str(row.get("source") or "binance_aggtrades"),
                ),
            )
        )
    return rows


def _pick_latest_at_or_before[T](rows: list[tuple[datetime, T]], current_dt: datetime) -> T | None:
    latest: T | None = None
    for row_dt, payload in rows:
        if row_dt <= current_dt:
            latest = payload
        else:
            break
    return latest


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _row_gates(row: dict[str, Any]) -> dict[str, Any]:
    gates = row.get("gates")
    return gates if isinstance(gates, dict) else {}


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buy_rows = [row for row in rows if row.get("side") == "BUY"]
    no_signal_rows = [row for row in rows if row.get("side") == "NO_SIGNAL"]
    score_passed_no_signal = [
        row for row in no_signal_rows if _safe_float(row.get("score")) >= _safe_float(row.get("threshold"))
    ]
    buy_with_mtf_false = [row for row in buy_rows if not bool(_row_gates(row).get("mtf"))]
    buy_with_orderbook_false = [
        row for row in buy_rows if not bool(_row_gates(row).get("orderbook"))
    ]
    buy_with_trend_false = [row for row in buy_rows if not bool(_row_gates(row).get("trend"))]
    date_counts: dict[str, int] = {}
    for row in rows:
        date_iso = str(row.get("datetime_utc", ""))[:10]
        if not date_iso:
            continue
        date_counts[date_iso] = date_counts.get(date_iso, 0) + 1

    def _gate_fail_counts(filtered_rows: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in filtered_rows:
            gates = _row_gates(row)
            for gate_name, passed in gates.items():
                if not bool(passed):
                    key = str(gate_name)
                    counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    return {
        "rows": len(rows),
        "coverage_start": rows[0]["datetime_utc"] if rows else None,
        "coverage_end": rows[-1]["datetime_utc"] if rows else None,
        "date_counts": dict(sorted(date_counts.items())),
        "buy_signals": len(buy_rows),
        "no_signal_rows": len(no_signal_rows),
        "score_passed_no_signal": len(score_passed_no_signal),
        "buy_with_mtf_false": len(buy_with_mtf_false),
        "buy_with_orderbook_false": len(buy_with_orderbook_false),
        "buy_with_trend_false": len(buy_with_trend_false),
        "score_passed_no_signal_failed_gates": _gate_fail_counts(score_passed_no_signal),
        "sample_buy_with_mtf_false": buy_with_mtf_false[:10],
        "sample_score_passed_no_signal": score_passed_no_signal[:10],
    }


def _build_markdown_report(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    if not isinstance(summary, dict):
        summary = {}
    date_counts = summary.get("date_counts", {})

    lines = [
        "# Signal-Only Replay Report",
        "",
        f"Updated: `{payload['generated_at_utc']}`",
        "Status: `Generated`",
        "",
        "## Summary",
        "",
        f"- `rows`: `{summary.get('rows', 0)}`",
        f"- `coverage_start`: `{summary.get('coverage_start', '—')}`",
        f"- `coverage_end`: `{summary.get('coverage_end', '—')}`",
        f"- `buy_signals`: `{summary.get('buy_signals', 0)}`",
        f"- `no_signal_rows`: `{summary.get('no_signal_rows', 0)}`",
        f"- `score_passed_no_signal`: `{summary.get('score_passed_no_signal', 0)}`",
        f"- `buy_with_mtf_false`: `{summary.get('buy_with_mtf_false', 0)}`",
        f"- `buy_with_orderbook_false`: `{summary.get('buy_with_orderbook_false', 0)}`",
        f"- `buy_with_trend_false`: `{summary.get('buy_with_trend_false', 0)}`",
        "",
        "## Date Coverage",
        "",
    ]

    if isinstance(date_counts, dict):
        for date_iso, count in date_counts.items():
            lines.append(f"- `{date_iso}`: `{count}` rows")

    lines.extend(
        [
            "",
        "## Score-Passed No-Signal Failed Gates",
        "",
        ]
    )

    failed_gates = summary.get("score_passed_no_signal_failed_gates", {})
    if isinstance(failed_gates, dict):
        for gate_name, count in failed_gates.items():
            lines.append(f"- `{gate_name}`: `{count}`")

    lines.extend(
        [
            "",
            "## Sample Section A",
            "",
            "These are example `BUY` rows where the final signal was `BUY`, but `mtf=false`.",
            "",
        ]
    )
    sample_buy = summary.get("sample_buy_with_mtf_false", [])
    if isinstance(sample_buy, list):
        for row in sample_buy[:8]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- `{row['datetime_utc']}` score=`{row['score']}` gates=`{row['gates']}` mtf=`{row['mtf_signals']}`"
            )

    lines.extend(
        [
            "",
            "## Sample Section B",
            "",
            "These are example `NO_SIGNAL` rows where `score >= threshold`, but one or more gates still blocked the trade.",
            "",
        ]
    )
    sample_blocked = summary.get("sample_score_passed_no_signal", [])
    if isinstance(sample_blocked, list):
        for row in sample_blocked[:8]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- `{row['datetime_utc']}` score=`{row['score']}` gates=`{row['gates']}` mtf=`{row['mtf_signals']}`"
            )

    return "\n".join(lines) + "\n"


def _build_text_log(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    if not isinstance(summary, dict):
        summary = {}
    lines = [
        f"generated_at={payload['generated_at_utc']}",
        f"rows={summary.get('rows', 0)}",
        f"coverage_start={summary.get('coverage_start', '—')}",
        f"coverage_end={summary.get('coverage_end', '—')}",
        f"buy_signals={summary.get('buy_signals', 0)}",
        f"no_signal_rows={summary.get('no_signal_rows', 0)}",
        f"score_passed_no_signal={summary.get('score_passed_no_signal', 0)}",
        f"buy_with_mtf_false={summary.get('buy_with_mtf_false', 0)}",
        f"buy_with_orderbook_false={summary.get('buy_with_orderbook_false', 0)}",
        f"buy_with_trend_false={summary.get('buy_with_trend_false', 0)}",
    ]
    return "\n".join(lines) + "\n"


def build_signal_only_replay(
    *,
    symbol: str = settings.DEFAULT_SYMBOL,
    timeframe: str = settings.DEFAULT_TIMEFRAME,
    candle_limit: int = settings.DEFAULT_CANDLE_LIMIT,
    data_root: Path = SPOT_DATA_ROOT,
    output_root: Path = REPLAY_OUTPUT_ROOT,
) -> dict[str, object]:
    candle_repository = JsonCandleRepository(candles_root=data_root / "candles")
    snapshot_repository = JsonIndicatorSnapshotRepository(
        indicator_root=data_root / "indicator_snapshots"
    )
    mtf_context_service = MultiTimeframeContextService()
    signal_decision_service = SignalDecisionService()

    primary_candles = candle_repository.get_closed_candles(
        symbol=symbol,
        timeframe=timeframe,
        limit=None,
    )
    if not primary_candles:
        raise RuntimeError("No primary candles available for replay.")

    snapshots_by_tf: dict[str, list[tuple[datetime, IndicatorSnapshot]]] = {}
    for tf in settings.DEFAULT_CANDLE_TIMEFRAMES:
        snapshots = snapshot_repository.get_snapshots(symbol=symbol, timeframe=tf, limit=None)
        snapshots_by_tf[tf] = [(_parse_utc_text(snapshot.timestamp_text), snapshot) for snapshot in snapshots]

    orderbook_rows = _load_orderbook_rows(data_root / "orderflow" / symbol / f"{timeframe}.json")

    replay_rows: list[dict[str, object]] = []
    for current_idx, current_candle in enumerate(primary_candles):
        current_dt = datetime.fromtimestamp((current_candle.close_time_ms + 1) / 1000, tz=UTC)

        timeframe_snapshots: dict[str, IndicatorSnapshot | None] = {
            tf: _pick_latest_at_or_before(snapshots_by_tf[tf], current_dt)
            for tf in settings.DEFAULT_CANDLE_TIMEFRAMES
        }
        latest_snapshot = timeframe_snapshots.get(timeframe)
        if latest_snapshot is None:
            continue

        start_idx = max(0, current_idx - candle_limit + 1)
        recent_candles = tuple(primary_candles[start_idx : current_idx + 1])
        latest_orderbook = _pick_latest_at_or_before(orderbook_rows, current_dt)
        mtf_signals, mtf_direction = mtf_context_service.build_signals(
            timeframe_snapshots=timeframe_snapshots,
            primary_timeframe=timeframe,
        )
        context = MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            latest_snapshot=latest_snapshot,
            latest_orderbook=latest_orderbook,
            recent_candles=recent_candles,
            mtf_signals=mtf_signals,
            mtf_direction=mtf_direction,
        )
        signal = signal_decision_service.build_signal(
            context,
            timestamp_ms=current_candle.close_time_ms,
        )
        replay_rows.append(
            {
                "datetime_utc": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "close_time_ms": current_candle.close_time_ms,
                "side": signal.side.value,
                "score": signal.score,
                "threshold": signal.threshold,
                "gates": {
                    "mtf": signal.gates.mtf,
                    "regime": signal.gates.regime,
                    "momentum": signal.gates.momentum,
                    "trend": signal.gates.trend,
                    "orderbook": signal.gates.orderbook,
                    "structure": signal.gates.structure,
                },
                "mtf_signals": signal.mtf_signals,
                "mtf_direction": signal.mtf_direction,
                "snapshot_price": signal.snapshot_price,
                "theoretical_setup": None
                if signal.theoretical_setup is None
                else {
                    "entry_price": signal.theoretical_setup.entry_price,
                    "stop_loss": signal.theoretical_setup.stop_loss,
                    "take_profit": signal.theoretical_setup.take_profit,
                    "rr_ratio": signal.theoretical_setup.rr_ratio,
                    "mode": signal.theoretical_setup.mode,
                },
            }
        )

    generated_at = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / f"signal_only_replay_{stamp}.json"
    summary = _summarize_rows(replay_rows)
    payload = {
        "generated_at_utc": generated_at,
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": replay_rows,
        "summary": summary,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = output_path.with_suffix(".md")
    log_path = output_path.with_suffix(".log")
    md_path.write_text(_build_markdown_report(payload), encoding="utf-8")
    log_path.write_text(_build_text_log(payload), encoding="utf-8")
    return {
        "output_path": str(output_path),
        "markdown_path": str(md_path),
        "log_path": str(log_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a read-only Spot signal replay.")
    parser.add_argument("--data-root", type=Path, default=SPOT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=REPLAY_OUTPUT_ROOT)
    parser.add_argument("--symbol", default=settings.DEFAULT_SYMBOL)
    parser.add_argument("--timeframe", default=settings.DEFAULT_TIMEFRAME)
    parser.add_argument("--candle-limit", type=int, default=settings.DEFAULT_CANDLE_LIMIT)
    args = parser.parse_args()
    result = build_signal_only_replay(
        symbol=args.symbol,
        timeframe=args.timeframe,
        candle_limit=args.candle_limit,
        data_root=args.data_root.expanduser().resolve(),
        output_root=args.output_root.expanduser().resolve(),
    )
    print(f"[OK] Replay output: {result['output_path']}")
    print(f"[OK] Replay markdown: {result['markdown_path']}")
    print(f"[OK] Replay log: {result['log_path']}")
    print(f"[OK] Summary: {result['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
