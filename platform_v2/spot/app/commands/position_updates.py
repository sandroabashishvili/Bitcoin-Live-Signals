"""File: position_updates.py
Folder: platform_v2/spot/app/commands
Created date: 2026-03-25
Last updated date: 2026-03-28
Author: Codex
Purpose: Minimal V2 entrypoint for refreshing current open positions.
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
from platform_v2.spot.services.account.position_batch_update_service import PositionBatchUpdateService


def _json_default(value: object) -> object:
    """Convert enums into JSON-safe values."""

    if isinstance(value, Enum):
        return value.value
    return value


def main() -> int:
    """Run one minimal V2 open-position update cycle."""

    parser = argparse.ArgumentParser(description="Run one SmartSignalHub V2 position update cycle.")
    parser.add_argument("--date", dest="date_iso", default=None)
    parser.add_argument("--lookback-days", type=int, default=settings.DEFAULT_LOOKBACK_DAYS)
    args = parser.parse_args()

    date_iso = args.date_iso or datetime.now(tz=timezone.utc).date().isoformat()
    updated_positions = PositionBatchUpdateService().run(
        date_iso=date_iso,
        lookback_days=args.lookback_days,
    )

    print(json.dumps([asdict(position) for position in updated_positions], default=_json_default, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
