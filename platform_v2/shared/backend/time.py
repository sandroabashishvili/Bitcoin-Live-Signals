"""Shared UTC time helpers for backend services."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now_ms() -> int:
    """Return the current UTC timestamp in milliseconds."""

    return int(datetime.now(tz=UTC).timestamp() * 1000)
