"""File: main_cycle.py
Folder: platform_v2/spot/app/commands
Created date: 2026-03-25
Last updated date: 2026-03-28
Author: Codex
Purpose: Run one minimal end-to-end V2 cycle.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from platform_v2.spot.config import settings
from platform_v2.spot.services.ops.main_cycle_service import MainCycleService


def _json_default(value: object) -> object:
    """Convert non-JSON-native values into safe output."""

    if isinstance(value, Enum):
        return value.value
    return str(value)


def _build_summary_line(result) -> str:
    """Build a short human-readable summary for one cycle."""

    signal_result = result.signal_result
    signal = signal_result.signal if signal_result else None
    order_result = signal_result.order_result if signal_result else None
    position = signal_result.position if signal_result else None

    status = "SKIPPED" if result.skipped else "OK"
    signal_side = getattr(signal.side, "value", None) if signal else "—"
    score = getattr(signal, "score", None)
    threshold = getattr(signal, "threshold", None)
    order_status = getattr(order_result, "status", None)
    order_status_text = getattr(order_status, "value", None) if order_status else "—"
    position_status = getattr(position.status, "value", None) if position else "—"
    score_text = (
        f"{score:.2f}/{threshold:.1f}"
        if isinstance(score, (int, float)) and isinstance(threshold, (int, float))
        else "—"
    )
    cycle_text = f"{settings.DEFAULT_SYMBOL} {settings.DEFAULT_TIMEFRAME}"
    marker_text = f"{result.cycle_state}:{result.cycle_note or '—'}"
    execution_text = f"order={order_status_text} position={position_status}"
    updates_text = f"updated={len(result.updated_positions)}"
    summary_name = result.daily_summary_path.name if result.daily_summary_path else "—"

    parts = [
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]",
        cycle_text,
        f"status={status}",
        f"cycle={marker_text}",
        f"signal={signal_side or '—'} score={score_text}",
        execution_text,
        updates_text,
        f"summary={summary_name}",
    ]
    if result.skip_reason:
        parts.append(f"skip={result.skip_reason}")
    return " | ".join(parts)


def main() -> int:
    """Run one closed-candle V2 cycle."""

    parser = argparse.ArgumentParser(description="Run one SmartSignalHub V2 main cycle.")
    parser.add_argument("--symbol", default=settings.DEFAULT_SYMBOL)
    parser.add_argument("--timeframe", default=settings.DEFAULT_TIMEFRAME)
    parser.add_argument("--date", dest="date_iso", default=None)
    parser.add_argument("--position-size", type=float, default=settings.DEFAULT_POSITION_SIZE)
    parser.add_argument("--starting-balance", type=float, default=settings.DEFAULT_STARTING_BALANCE)
    parser.add_argument("--fetch-limit", type=int, default=settings.DEFAULT_FETCH_LIMIT)
    parser.add_argument("--json", action="store_true", help="Print the full JSON result instead of a short summary.")
    args = parser.parse_args()

    date_iso = args.date_iso or datetime.now(tz=timezone.utc).date().isoformat()
    result = MainCycleService().run(
        symbol=args.symbol,
        timeframe=args.timeframe,
        date_iso=date_iso,
        position_size=args.position_size,
        starting_balance=args.starting_balance,
        fetch_limit=args.fetch_limit,
    )

    if args.json:
        print(json.dumps(asdict(result), default=_json_default, indent=2))
    else:
        print(_build_summary_line(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
