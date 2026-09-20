"""Runtime log helpers for the news generation tool."""

from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, TextIO
import os
import sys


PLATFORM_ROOT = Path(__file__).resolve().parents[2]
TOOL_LOG_DIR = PLATFORM_ROOT / "runtime" / "logs" / "tools"
MISPLACED_LOG = PLATFORM_ROOT / "tools" / "news_generation_system.log"


class Tee:
    def __init__(self, *streams: TextIO) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for stream in self._streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


@contextmanager
def tee_tool_output(filename: str) -> Iterator[Path]:
    TOOL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = TOOL_LOG_DIR / filename
    stdout_target = _fd_target(1)
    stderr_target = _fd_target(2)
    with path.open("a", encoding="utf-8") as log_handle:
        stdout_streams = (log_handle,) if stdout_target == MISPLACED_LOG else (sys.stdout, log_handle)
        stderr_streams = (log_handle,) if stderr_target == MISPLACED_LOG else (sys.stderr, log_handle)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log_handle.write(f"\n[{timestamp}] start\n")
        try:
            with redirect_stdout(Tee(*stdout_streams)), redirect_stderr(Tee(*stderr_streams)):
                yield path
        finally:
            log_handle.write(f"[{timestamp}] end\n")
            if stdout_target == MISPLACED_LOG or stderr_target == MISPLACED_LOG:
                MISPLACED_LOG.unlink(missing_ok=True)


def _fd_target(fd: int) -> Path | None:
    try:
        return Path(os.readlink(f"/proc/self/fd/{fd}")).resolve()
    except OSError:
        return None
