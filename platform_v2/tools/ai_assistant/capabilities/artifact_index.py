"""Artifact index for SmartSignalHub assistant capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_v2.tools.ai_assistant.runtime_readers import PLATFORM_ROOT, REPO_ROOT

from .contracts import CapabilityAnswer


@dataclass(frozen=True)
class ArtifactArea:
    name: str
    path: Path
    purpose: str
    patterns: tuple[str, ...] = ("*",)


ARTIFACT_AREAS: tuple[ArtifactArea, ...] = (
    ArtifactArea("ai_assistant_history", PLATFORM_ROOT / "runtime" / "artifacts" / "ai_assistant", "browser/CLI chat history", ("*.jsonl",)),
    ArtifactArea("diagnostics", PLATFORM_ROOT / "runtime" / "artifacts" / "diagnostics", "diagnostics reports", ("*.json", "*.md")),
    ArtifactArea("research_replay", PLATFORM_ROOT / "runtime" / "artifacts" / "research" / "replay", "what-if/replay research reports", ("*.json", "*.md")),
    ArtifactArea("video_reels", PLATFORM_ROOT / "runtime" / "artifacts" / "video_reels", "generated video reel artifacts", ("*.mp4", "*.srt", "*.json", "*.md")),
    ArtifactArea("futures_signals", PLATFORM_ROOT / "runtime" / "futures" / "data" / "futures_signals", "Futures signal ledger", ("*.json",)),
    ArtifactArea("futures_denied_entries", PLATFORM_ROOT / "runtime" / "futures" / "data" / "futures_denied_entries", "Futures denied entry ledger", ("*.json",)),
    ArtifactArea("futures_positions", PLATFORM_ROOT / "runtime" / "futures" / "data" / "futures_positions", "Futures position ledger", ("*.json",)),
    ArtifactArea("futures_position_events", PLATFORM_ROOT / "runtime" / "futures" / "data" / "futures_position_events", "Futures position lifecycle events", ("*.json",)),
    ArtifactArea("futures_trade_audits", PLATFORM_ROOT / "runtime" / "futures" / "data" / "futures_trade_entry_audits", "Futures trade entry audits", ("*.json",)),
    ArtifactArea("spot_signals", PLATFORM_ROOT / "runtime" / "spot" / "data" / "signals", "Spot signal ledger", ("*.json",)),
    ArtifactArea("backup_archives", REPO_ROOT.parent / "runtime_archives", "runtime reset/backup archives", ("*",)),
    ArtifactArea("tools_logs", PLATFORM_ROOT / "runtime" / "logs" / "tools", "tool runtime logs", ("*.log", "*.jsonl", "*.txt")),
)


def answer_artifact_index() -> CapabilityAnswer:
    lines = ["SmartSignalHub artifact index"]
    sources: list[str] = []
    for area in ARTIFACT_AREAS:
        files = _matching_files(area)
        latest = max(files, key=lambda path: path.stat().st_mtime) if files else None
        exists = area.path.exists()
        lines.append(
            f"- {area.name}: exists={exists}, files={len(files)}, latest={_display_path(latest) if latest else '--'}"
        )
        lines.append(f"  path={_display_path(area.path)}")
        lines.append(f"  purpose={area.purpose}")
        if exists:
            sources.append(str(area.path))
    return CapabilityAnswer("artifact_index", "\n".join(lines), tuple(sources))


def latest_files_by_area(limit: int = 3) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for area in ARTIFACT_AREAS:
        files = sorted(_matching_files(area), key=lambda path: path.stat().st_mtime, reverse=True)
        result[area.name] = files[:limit]
    return result


def _matching_files(area: ArtifactArea) -> list[Path]:
    if not area.path.exists():
        return []
    files: list[Path] = []
    for pattern in area.patterns:
        files.extend(path for path in area.path.glob(pattern) if path.is_file())
    return sorted(set(files))


def _display_path(path: Path | None) -> str:
    if path is None:
        return "--"
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
