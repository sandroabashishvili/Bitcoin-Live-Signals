"""Cross-module contracts that static file checks cannot infer reliably."""

from __future__ import annotations

import json
from pathlib import Path

from platform_v2.spot.storage.paths import indicator_snapshot_file_path
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


_SPOT_ENTRY_LOCATION_KEYS = (
    "atr",
    "ema9",
    "ema50",
    "vwap",
    "rsi",
    "swing_high",
    "swing_low",
)


def spot_entry_location_contract_findings(snapshot_path: Path | None = None) -> list[FileFinding]:
    path = snapshot_path or indicator_snapshot_file_path("BTCUSDT", "15m")
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list) or not payload or not isinstance(payload[-1], dict):
        return []

    missing = [key for key in _SPOT_ENTRY_LOCATION_KEYS if key not in payload[-1]]
    findings: list[FileFinding] = []
    if missing:
        add_finding(
            findings,
            "platform_v2/runtime/spot/data/indicator_snapshots/BTCUSDT/15m.json",
            "strategy_input_contract_missing_keys",
            "SpotEntryLocationClassifier inputs missing: " + ", ".join(missing),
            "medium",
        )
    return findings
