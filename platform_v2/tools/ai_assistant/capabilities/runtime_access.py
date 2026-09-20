"""Runtime root coverage summary for the assistant."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_v2.tools.ai_assistant.runtime_readers import PLATFORM_ROOT

from .contracts import CapabilityAnswer


@dataclass(frozen=True)
class RuntimeRoot:
    name: str
    path: Path
    purpose: str


RUNTIME_ROOTS: tuple[RuntimeRoot, ...] = (
    RuntimeRoot("platform_runtime", PLATFORM_ROOT / "runtime", "shared/system artifacts, assistant history, diagnostics, tool logs"),
    RuntimeRoot("futures_runtime", PLATFORM_ROOT / "runtime" / "futures", "Futures live/simulation runtime ledgers and state"),
    RuntimeRoot("spot_runtime", PLATFORM_ROOT / "runtime" / "spot", "Spot live/simulation runtime ledgers and state"),
    RuntimeRoot("hedge_runtime", PLATFORM_ROOT / "runtime" / "hedge", "Hedge replay/runtime ledgers and state"),
)


def answer_runtime_access() -> CapabilityAnswer:
    lines = [
        "Runtime access coverage",
        "Raw filesystem access: available for all three runtime roots inside this workspace.",
        "Semantic coverage: the assistant can answer reliably when a deterministic reader/capability is wired for that data family.",
    ]
    sources: list[str] = []
    for root in RUNTIME_ROOTS:
        exists = root.path.exists()
        files = _files(root.path)
        lines.append(f"- {root.name}: exists={exists}, files={len(files)}")
        lines.append(f"  path={root.path}")
        lines.append(f"  purpose={root.purpose}")
        if exists:
            sources.append(str(root.path))
            family_lines = _data_family_lines(root.path)
            if family_lines:
                lines.extend(f"  {line}" for line in family_lines)
            latest = _latest_file(files)
            lines.append(f"  latest_file={latest if latest else '--'}")

    lines.extend(
        [
            "Current reliable runtime readers include: signals, metrics, daily summaries, cycle/runtime health, Futures positions, Futures denied entries, Futures position events, Futures trade audits, diagnostics, tool logs, and assistant artifacts.",
            "Important limitation: raw access does not automatically mean strategy-grade interpretation. New ledger families still need a small reader before the assistant should make conclusions from them.",
        ]
    )
    return CapabilityAnswer("runtime_access", "\n".join(lines), tuple(sources))


def _files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _data_family_lines(root: Path) -> list[str]:
    data_dir = root / "data"
    if not data_dir.exists():
        return []
    lines = ["data families:"]
    for child in sorted(path for path in data_dir.iterdir() if path.is_dir()):
        count = len([path for path in child.rglob("*.json") if path.is_file()])
        lines.append(f"  - {child.name}: json_files={count}")
    return lines


def _latest_file(files: list[Path]) -> str | None:
    if not files:
        return None
    return str(max(files, key=lambda path: path.stat().st_mtime))
