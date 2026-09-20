"""Safe tool-runner boundary for the assistant.

This module intentionally does not execute commands yet. It documents the
confirmation boundary so the browser assistant cannot reset, publish, or start
long-running systems by accident.
"""

from __future__ import annotations

from .contracts import CapabilityAnswer
from .tools_registry import TOOLS


def answer_tool_runner_policy() -> CapabilityAnswer:
    lines = [
        "SmartSignalHub tool runner policy",
        "Current mode: read-only.",
        "Assistant can inspect tool status/artifacts, but it does not execute backup/reset/start/publish commands from chat yet.",
        "Future action mode must require explicit confirmation and write an action audit log.",
        "Confirm-required tools:",
    ]
    for tool in TOOLS:
        lines.append(f"- {tool.name}: {tool.mode}")
    return CapabilityAnswer("tool_runner", "\n".join(lines))
