"""Tool status capability for internal SmartSignalHub tools."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .artifact_index import latest_files_by_area
from .contracts import CapabilityAnswer
from .tools_registry import TOOLS


def answer_tools_status() -> CapabilityAnswer:
    latest_by_area = latest_files_by_area(limit=2)
    lines = ["SmartSignalHub tools status"]
    sources: list[str] = []
    for tool in TOOLS:
        py_files = list(tool.folder.glob("*.py")) if tool.folder.exists() else []
        artifact_hits = _latest_for_tool(tool.name, latest_by_area)
        lines.append(f"- {tool.name}: folder_exists={tool.folder.exists()}, python_files={len(py_files)}, mode={tool.mode}")
        if artifact_hits:
            lines.append("  latest_artifacts=" + ", ".join(_short(path) for path in artifact_hits))
        elif tool.artifacts:
            lines.append("  latest_artifacts=none found")
        if tool.logs:
            log_files = _log_files(tool.logs, tool.name)
            lines.append("  logs=" + (", ".join(_short(path) for path in log_files[:3]) if log_files else "none found"))
            for summary in _log_summaries(log_files[:2]):
                lines.append(f"  {summary}")
        if tool.folder.exists():
            sources.append(str(tool.folder))
    return CapabilityAnswer("tools_status", "\n".join(lines), tuple(sources))


def _latest_for_tool(tool_name: str, latest_by_area: dict[str, list[Path]]) -> list[Path]:
    if tool_name == "diagnostics":
        return latest_by_area.get("diagnostics", [])
    if tool_name == "research":
        return latest_by_area.get("research_replay", [])
    if tool_name == "video_reels":
        return latest_by_area.get("video_reels", [])
    if tool_name in {"backup_system", "runtime_reset_system"}:
        return latest_by_area.get("backup_archives", [])
    return []


def _short(path: Path) -> str:
    return str(path)


def _log_files(paths: tuple[Path, ...], tool_name: str) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                child
                for child in path.glob("*.log")
                if child.is_file() and tool_name.casefold() in child.name.casefold()
            )
    return sorted(set(files), key=lambda item: item.stat().st_mtime, reverse=True)


def _log_summaries(paths: list[Path]) -> list[str]:
    summaries: list[str] = []
    for path in paths:
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        error_lines = _interesting_log_lines(path)
        if error_lines:
            summaries.append(f"log_summary={_short(path)} modified={modified} errors={'; '.join(error_lines[-2:])}")
        else:
            summaries.append(f"log_summary={_short(path)} modified={modified} errors=none found")
    return summaries


def _interesting_log_lines(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ["unreadable"]
    tokens = ("error", "failed", "traceback", "exception")
    matches = [line.strip() for line in lines[-200:] if any(token in line.casefold() for token in tokens)]
    return [line[:220] for line in matches if line]
