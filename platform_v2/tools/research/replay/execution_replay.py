"""File: execution_replay.py
Folder: platform_v2/tools/research/replay
Created date: 2026-03-30
Last updated date: 2026-03-30
Author: Codex
Purpose: Run a first theoretical execution replay on top of signal-only replay outputs.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.position import PositionRecord, PositionStatus
from platform_v2.spot.domain.models.signal import GateSnapshot, SignalDecision, SignalSide, TheoreticalSetup
from platform_v2.spot.infrastructure.market_data.candle_repository import JsonCandleRepository
from platform_v2.spot.services.account.fee_service import FeeService
from platform_v2.spot.services.permission.permission_decision_service import PermissionDecisionService
from platform_v2.spot.services.account.position_update_service import PositionUpdateService
from platform_v2.spot.services.trading.execution_setup_service import ExecutionSetupService
from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots


SPOT_DATA_ROOT = ResearchDataRoots.live().spot
REPLAY_OUTPUT_ROOT = CANONICAL_OUTPUT_ROOT
REPLAY_COOLDOWN_SECONDS = 2 * 60 * 60
REPLAY_WEAK_OPEN_POSITION_PCT = -0.003


def _latest_signal_only_replay_path(replay_root: Path) -> Path:
    candidates = sorted(replay_root.glob("signal_only_replay_*.json"), reverse=True)
    if not candidates:
        raise RuntimeError("No signal-only replay output found.")
    return candidates[0]


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_signal(row: dict[str, object]) -> SignalDecision:
    gates_dict = row.get("gates") if isinstance(row.get("gates"), dict) else {}
    mtf_signals = row.get("mtf_signals") if isinstance(row.get("mtf_signals"), dict) else {}
    theoretical_setup_row = (
        row.get("theoretical_setup") if isinstance(row.get("theoretical_setup"), dict) else None
    )
    return SignalDecision(
        timestamp_ms=int(row.get("close_time_ms", 0) or 0),
        symbol=settings.DEFAULT_SYMBOL,
        timeframe=settings.DEFAULT_TIMEFRAME,
        side=SignalSide(str(row.get("side", "NO_SIGNAL"))),
        snapshot_price=float(row.get("snapshot_price", 0.0) or 0.0),
        score=float(row.get("score", 0.0) or 0.0),
        threshold=float(row.get("threshold", 0.0) or 0.0),
        gates=GateSnapshot(
            mtf=bool(gates_dict.get("mtf", False)),
            regime=bool(gates_dict.get("regime", False)),
            momentum=bool(gates_dict.get("momentum", False)),
            trend=bool(gates_dict.get("trend", False)),
            orderbook=bool(gates_dict.get("orderbook", False)),
            structure=bool(gates_dict.get("structure", False)),
        ),
        mtf_signals={str(key): str(value) for key, value in mtf_signals.items()},
        mtf_direction=str(row.get("mtf_direction", "NO_SIGNAL")),
        reasons=(),
        theoretical_setup=None
        if theoretical_setup_row is None
        else TheoreticalSetup(
            entry_price=float(theoretical_setup_row.get("entry_price", 0.0) or 0.0),
            stop_loss=float(theoretical_setup_row.get("stop_loss", 0.0) or 0.0),
            take_profit=float(theoretical_setup_row.get("take_profit", 0.0) or 0.0),
            rr_ratio=float(theoretical_setup_row.get("rr_ratio", 0.0) or 0.0),
            mode=str(theoretical_setup_row.get("mode", "unknown")),
        ),
    )


def _build_open_position(signal: SignalDecision, opened_at: str) -> PositionRecord:
    execution_setup = ExecutionSetupService().build_setup(
        signal,
        live_entry_price=signal.snapshot_price,
        position_size=settings.DEFAULT_POSITION_SIZE,
        market_context=None,
    )
    return PositionRecord(
        position_id=uuid4().hex,
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        side=signal.side,
        status=PositionStatus.OPEN,
        execution=execution_setup,
        opened_at=opened_at,
    )


def _close_position_at_end(position: PositionRecord, candles_by_close_time: dict[int, object], close_times: list[int]) -> PositionRecord:
    update_service = PositionUpdateService()
    last_close_time = close_times[-1]
    last_candle = candles_by_close_time[last_close_time]
    return update_service.force_close(
        position,
        close_price=last_candle.close_price,
        closed_at=str(last_close_time),
        reason_text="end_of_sample",
    )


def _position_to_row(current: PositionRecord) -> dict[str, object]:
    return {
        "position_id": current.position_id,
        "opened_at_ms": int(current.opened_at),
        "closed_at": current.closed_at,
        "entry_price": current.execution.entry_price,
        "stop_loss": current.execution.stop_loss,
        "take_profit": current.execution.take_profit,
        "rr_ratio": current.execution.rr_ratio,
        "mode": current.execution.mode,
        "status": current.status.value,
        "exit_reason": current.exit_reason.value,
        "exit_price": current.exit_price,
        "net_pnl": current.net_pnl,
        "was_force_closed": current.was_force_closed,
    }


def _update_open_positions(
    open_positions: list[PositionRecord],
    *,
    candle,
) -> tuple[list[PositionRecord], list[PositionRecord]]:
    update_service = PositionUpdateService()
    still_open: list[PositionRecord] = []
    newly_closed: list[PositionRecord] = []
    for position in open_positions:
        updated = update_service.update_from_candle(position, candle)
        if updated.is_closed:
            newly_closed.append(updated)
        else:
            still_open.append(updated)
    return still_open, newly_closed


def _build_denial_reason_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("reason", "unknown"))
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _has_weak_open_position(open_positions: list[PositionRecord]) -> bool:
    for position in open_positions:
        notional = position.execution.position_size
        unrealized = float(position.unrealized_pnl or 0.0)
        unrealized_pct = (unrealized / notional) if notional > 0 else 0.0
        if unrealized_pct <= REPLAY_WEAK_OPEN_POSITION_PCT:
            return True
    return False


def _build_markdown_report(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    if not isinstance(summary, dict):
        summary = {}
    sample = payload.get("sample_trades", [])
    denial_reason_counts = summary.get("denial_reason_counts", {})
    sample_denied_entries = payload.get("sample_denied_entries", [])
    lines = [
        "# Execution Replay Report",
        "",
        f"Updated: `{payload['generated_at_utc']}`",
        "Status: `Generated`",
        "",
        "## Summary",
        "",
        f"- `source_signal_replay`: `{payload.get('source_signal_replay', '—')}`",
        f"- `cooldown_seconds`: `{summary.get('cooldown_seconds', 0)}`",
        f"- `weak_open_position_pct`: `{summary.get('weak_open_position_pct', 0)}`",
        f"- `buy_trades`: `{summary.get('buy_trades', 0)}`",
        f"- `denied_entries`: `{summary.get('denied_entries', 0)}`",
        f"- `closed_trades`: `{summary.get('closed_trades', 0)}`",
        f"- `open_trades`: `{summary.get('open_trades', 0)}`",
        f"- `tp_hits`: `{summary.get('tp_hits', 0)}`",
        f"- `sl_hits`: `{summary.get('sl_hits', 0)}`",
        f"- `force_closed`: `{summary.get('force_closed', 0)}`",
        f"- `win_rate_pct`: `{summary.get('win_rate_pct', 0)}`",
        f"- `total_net_pnl`: `{summary.get('total_net_pnl', 0)}`",
        f"- `avg_net_pnl`: `{summary.get('avg_net_pnl', 0)}`",
        "",
        "## Denial Breakdown",
        "",
        "These are replay `BUY` rows that did not become positions because the permission layer blocked them.",
        "",
    ]
    if isinstance(denial_reason_counts, dict) and denial_reason_counts:
        for reason, count in denial_reason_counts.items():
            lines.append(f"- `{reason}`: `{count}`")
    else:
        lines.append("- `none`")
    lines.extend(
        [
            "",
            "## Sample Denied Entries",
            "",
        ]
    )
    if isinstance(sample_denied_entries, list) and sample_denied_entries:
        for row in sample_denied_entries[:10]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- time=`{row.get('datetime_utc', '—')}` reason=`{row.get('reason', 'unknown')}` entry=`{row.get('entry_price', '—')}` open_positions=`{row.get('open_positions_count', '—')}` available_balance=`{row.get('available_balance', '—')}`"
            )
    else:
        lines.append("- `none`")
    lines.extend(
        [
            "",
            "## Sample Trades",
            "",
            "These are example theoretical trades built from replay `BUY` rows and then closed by TP, SL, or end-of-sample force close.",
            "",
        ]
    )
    if isinstance(sample, list):
        for row in sample[:10]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- open=`{row['opened_at_ms']}` entry=`{row['entry_price']}` tp=`{row['take_profit']}` sl=`{row['stop_loss']}` exit=`{row['exit_reason']}` pnl=`{row['net_pnl']}`"
            )
    return "\n".join(lines) + "\n"


def _build_text_log(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    if not isinstance(summary, dict):
        summary = {}
    lines = [
        f"generated_at={payload['generated_at_utc']}",
        f"source_signal_replay={payload.get('source_signal_replay', '—')}",
        f"cooldown_seconds={summary.get('cooldown_seconds', 0)}",
        f"weak_open_position_pct={summary.get('weak_open_position_pct', 0)}",
        f"buy_trades={summary.get('buy_trades', 0)}",
        f"denied_entries={summary.get('denied_entries', 0)}",
        f"closed_trades={summary.get('closed_trades', 0)}",
        f"open_trades={summary.get('open_trades', 0)}",
        f"tp_hits={summary.get('tp_hits', 0)}",
        f"sl_hits={summary.get('sl_hits', 0)}",
        f"force_closed={summary.get('force_closed', 0)}",
        f"win_rate_pct={summary.get('win_rate_pct', 0)}",
        f"total_net_pnl={summary.get('total_net_pnl', 0)}",
        f"avg_net_pnl={summary.get('avg_net_pnl', 0)}",
    ]
    denial_reason_counts = summary.get("denial_reason_counts", {})
    if isinstance(denial_reason_counts, dict):
        for reason, count in denial_reason_counts.items():
            lines.append(f"denial_{reason}={count}")
    return "\n".join(lines) + "\n"


def _load_replay_rows(replay_root: Path) -> tuple[Path, list[dict[str, object]]]:
    signal_replay_path = _latest_signal_only_replay_path(replay_root)
    replay_payload = _load_json(signal_replay_path)
    if not isinstance(replay_payload, dict):
        raise RuntimeError("Signal replay payload is invalid.")
    rows = replay_payload.get("rows")
    if not isinstance(rows, list):
        raise RuntimeError("Signal replay rows missing.")
    valid_rows = [row for row in rows if isinstance(row, dict)]
    return signal_replay_path, valid_rows


def _load_candle_index(data_root: Path) -> tuple[dict[int, object], list[int]]:
    candle_repository = JsonCandleRepository(candles_root=data_root / "candles")
    primary_candles = candle_repository.get_closed_candles(
        symbol=settings.DEFAULT_SYMBOL,
        timeframe=settings.DEFAULT_TIMEFRAME,
        limit=None,
    )
    candles_by_close_time = {candle.close_time_ms: candle for candle in primary_candles}
    close_times = sorted(candles_by_close_time)
    return candles_by_close_time, close_times


def _evaluate_buy_permission(
    *,
    signal: SignalDecision,
    row: dict[str, object],
    close_time_ms: int,
    open_positions: list[PositionRecord],
    closed_positions: list[PositionRecord],
    permission_service: PermissionDecisionService,
) -> tuple[bool, dict[str, object] | None]:
    current_open_exposure = sum(position.execution.position_size for position in open_positions)
    open_entry_fees = FeeService.open_entry_fees_total(open_positions)
    total_net_pnl_so_far = sum(float(position.net_pnl or 0.0) for position in closed_positions)
    available_balance = settings.DEFAULT_STARTING_BALANCE + total_net_pnl_so_far - current_open_exposure - open_entry_fees
    last_entry_price = open_positions[-1].execution.entry_price if open_positions else None
    latest_opened_at_ms = max((int(position.opened_at) for position in open_positions), default=None)
    cooldown_active = latest_opened_at_ms is not None and close_time_ms < (latest_opened_at_ms + REPLAY_COOLDOWN_SECONDS * 1000)
    weak_open_position_active = _has_weak_open_position(open_positions)
    duplicate_active = any(
        abs(position.execution.entry_price - signal.snapshot_price) < 0.0001 for position in open_positions
    )

    permission = permission_service.evaluate(
        signal,
        live_entry_price=signal.snapshot_price,
        available_balance=available_balance,
        current_open_exposure=current_open_exposure,
        open_positions_count=len(open_positions),
        last_entry_price=last_entry_price,
        manual_block=False,
        cooldown_active=cooldown_active,
        duplicate_active=duplicate_active,
        weak_open_position_active=weak_open_position_active,
        proximity_pct=settings.DEFAULT_PROXIMITY_PCT,
        timestamp_text=str(row.get("datetime_utc")),
    )
    if permission.is_allowed:
        return True, None
    return False, {
        "datetime_utc": row.get("datetime_utc"),
        "entry_price": signal.snapshot_price,
        "reason": permission.reason,
        "open_positions_count": len(open_positions),
        "available_balance": available_balance,
        "current_open_exposure": current_open_exposure,
        "weak_open_position_active": weak_open_position_active,
    }


def _build_summary_rows(
    *,
    trade_rows: list[dict[str, object]],
    denied_rows: list[dict[str, object]],
) -> dict[str, object]:
    tp_hits = sum(1 for row in trade_rows if row["exit_reason"] == "tp_hit")
    sl_hits = sum(1 for row in trade_rows if row["exit_reason"] == "sl_hit")
    force_closed = sum(1 for row in trade_rows if row["exit_reason"] == "force_close")
    wins = sum(1 for row in trade_rows if float(row.get("net_pnl") or 0.0) > 0)
    total_net_pnl = round(sum(float(row.get("net_pnl") or 0.0) for row in trade_rows), 4)
    avg_net_pnl = round((total_net_pnl / len(trade_rows)) if trade_rows else 0.0, 4)
    win_rate_pct = round((wins / len(trade_rows) * 100.0) if trade_rows else 0.0, 2)
    return {
        "buy_trades": len(trade_rows),
        "denied_entries": len(denied_rows),
        "cooldown_seconds": REPLAY_COOLDOWN_SECONDS,
        "weak_open_position_pct": REPLAY_WEAK_OPEN_POSITION_PCT,
        "closed_trades": len(trade_rows),
        "open_trades": 0,
        "tp_hits": tp_hits,
        "sl_hits": sl_hits,
        "force_closed": force_closed,
        "win_rate_pct": win_rate_pct,
        "total_net_pnl": total_net_pnl,
        "avg_net_pnl": avg_net_pnl,
        "denial_reason_counts": _build_denial_reason_counts(denied_rows),
    }


def _write_replay_outputs(payload: dict[str, object], output_root: Path) -> tuple[Path, Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    output_path = output_root / f"execution_replay_{stamp}.json"
    md_path = output_path.with_suffix(".md")
    log_path = output_path.with_suffix(".log")
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_markdown_report(payload), encoding="utf-8")
    log_path.write_text(_build_text_log(payload), encoding="utf-8")
    return output_path, md_path, log_path


def build_execution_replay(
    *,
    data_root: Path = SPOT_DATA_ROOT,
    replay_root: Path = REPLAY_OUTPUT_ROOT,
    output_root: Path = REPLAY_OUTPUT_ROOT,
) -> dict[str, object]:
    signal_replay_path, rows = _load_replay_rows(replay_root)
    candles_by_close_time, close_times = _load_candle_index(data_root)

    permission_service = PermissionDecisionService()
    denied_rows: list[dict[str, object]] = []
    open_positions: list[PositionRecord] = []
    closed_positions: list[PositionRecord] = []

    for row in rows:
        close_time_ms = int(row.get("close_time_ms", 0) or 0)
        candle = candles_by_close_time.get(close_time_ms)
        if candle is not None:
            open_positions, newly_closed = _update_open_positions(open_positions, candle=candle)
            closed_positions.extend(newly_closed)

        if row.get("side") != "BUY":
            continue

        signal = _build_signal(row)
        is_allowed, denial_row = _evaluate_buy_permission(
            signal=signal,
            row=row,
            close_time_ms=close_time_ms,
            open_positions=open_positions,
            closed_positions=closed_positions,
            permission_service=permission_service,
        )
        if not is_allowed:
            if denial_row is not None:
                denied_rows.append(denial_row)
            continue

        position = _build_open_position(signal, opened_at=str(signal.timestamp_ms))
        open_positions.append(position)

    closed_positions.extend(
        _close_position_at_end(position, candles_by_close_time, close_times) for position in open_positions
    )
    trade_rows = [_position_to_row(position) for position in closed_positions]
    summary = _build_summary_rows(trade_rows=trade_rows, denied_rows=denied_rows)
    payload = {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "source_signal_replay": str(signal_replay_path),
        "summary": summary,
        "trades": trade_rows,
        "sample_trades": trade_rows[:12],
        "denied_entries": denied_rows,
        "sample_denied_entries": denied_rows[:12],
    }
    output_path, md_path, log_path = _write_replay_outputs(payload, output_root)
    return {
        "output_path": str(output_path),
        "markdown_path": str(md_path),
        "log_path": str(log_path),
        "summary": payload["summary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run theoretical execution on a signal replay.")
    parser.add_argument("--data-root", type=Path, default=SPOT_DATA_ROOT)
    parser.add_argument("--replay-root", type=Path, default=REPLAY_OUTPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=REPLAY_OUTPUT_ROOT)
    args = parser.parse_args()
    result = build_execution_replay(
        data_root=args.data_root.expanduser().resolve(),
        replay_root=args.replay_root.expanduser().resolve(),
        output_root=args.output_root.expanduser().resolve(),
    )
    print(f"[OK] Execution replay output: {result['output_path']}")
    print(f"[OK] Execution replay markdown: {result['markdown_path']}")
    print(f"[OK] Execution replay log: {result['log_path']}")
    print(f"[OK] Summary: {result['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
