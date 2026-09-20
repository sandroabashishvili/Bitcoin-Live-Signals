from __future__ import annotations

from datetime import datetime, UTC


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def default_commit_message() -> str:
    return f"Publish V2 frontend - {utc_timestamp()}"

