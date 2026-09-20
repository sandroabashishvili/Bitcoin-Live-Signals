"""Structured runtime warning events for recoverable fallback paths."""

from __future__ import annotations

import json
import sys
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLATFORM_ROOT = Path(__file__).resolve().parents[1]
WARNING_LOG = PLATFORM_ROOT / "runtime" / "logs" / "runtime_warnings.jsonl"


def warn_runtime_fallback(
    *,
    scope: str,
    operation: str,
    error: BaseException,
    fallback: str,
    extra: dict[str, Any] | None = None,
) -> None:
    row = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": scope,
        "operation": operation,
        "error_type": type(error).__name__,
        "error": str(error),
        "fallback": fallback,
        "extra": extra or {},
    }
    with suppress(OSError):
        WARNING_LOG.parent.mkdir(parents=True, exist_ok=True)
        with WARNING_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(
        f"[runtime-warning] {scope}.{operation}: {type(error).__name__}: {error} | fallback={fallback}",
        file=sys.stderr,
        flush=True,
    )
