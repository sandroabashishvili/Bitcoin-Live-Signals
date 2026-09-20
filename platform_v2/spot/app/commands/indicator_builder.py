"""File: indicator_builder.py
Folder: platform_v2/spot/app/commands
Created date: 2026-03-25
Last updated date: 2026-03-28
Author: Codex
Purpose: Build V2 indicator snapshots from V2 candle storage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from platform_v2.spot.config import settings
from platform_v2.spot.services.analytics.indicator_builder_service import IndicatorBuilderService


def main() -> int:
    """Run one indicator build pass into V2 storage."""

    parser = argparse.ArgumentParser(description="Build SmartSignalHub V2 indicator snapshots.")
    parser.add_argument("--symbol", default=settings.DEFAULT_SYMBOL)
    parser.add_argument(
        "--timeframes",
        nargs="*",
        default=list(settings.DEFAULT_CANDLE_TIMEFRAMES),
    )
    args = parser.parse_args()

    written_paths = IndicatorBuilderService().build_many(
        symbol=args.symbol,
        timeframes=tuple(args.timeframes),
    )
    print(json.dumps([str(path) for path in written_paths], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
