"""File: signal_pipeline.py
Folder: platform_v2/spot/app/commands
Created date: 2026-03-25
Last updated date: 2026-03-28
Author: Codex
Purpose: Minimal V2 entrypoint for one local signal-permission run.
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
from platform_v2.spot.services.permission.signal_permission_runtime_service import SignalPermissionRuntimeService


def _json_default(value: object) -> object:
    """Convert enums and dataclasses into JSON-safe values."""

    if isinstance(value, Enum):
        return value.value
    return value


def main() -> int:
    """Run one minimal V2 signal-permission pipeline cycle."""

    parser = argparse.ArgumentParser(description="Run one SmartSignalHub V2 signal cycle.")
    parser.add_argument("--symbol", default=settings.DEFAULT_SYMBOL)
    parser.add_argument("--timeframe", default=settings.DEFAULT_TIMEFRAME)
    parser.add_argument("--date", dest="date_iso", default=None)
    parser.add_argument("--position-size", type=float, default=settings.DEFAULT_POSITION_SIZE)
    parser.add_argument("--starting-balance", type=float, default=settings.DEFAULT_STARTING_BALANCE)
    args = parser.parse_args()

    date_iso = args.date_iso or datetime.now(tz=timezone.utc).date().isoformat()

    result = SignalPermissionRuntimeService().run_for_symbol(
        symbol=args.symbol,
        timeframe=args.timeframe,
        date_iso=date_iso,
        position_size=args.position_size,
        starting_balance=args.starting_balance,
    )

    print(json.dumps(asdict(result), default=_json_default, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
