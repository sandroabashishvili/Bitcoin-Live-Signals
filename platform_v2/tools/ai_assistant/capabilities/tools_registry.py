"""Read-only registry of internal SmartSignalHub tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_v2.tools.ai_assistant.runtime_readers import PLATFORM_ROOT

from .contracts import CapabilityAnswer


@dataclass(frozen=True)
class ToolSpec:
    name: str
    module: str
    folder: Path
    purpose: str
    mode: str
    artifacts: tuple[Path, ...] = ()
    logs: tuple[Path, ...] = ()


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("analytics_system", "platform_v2.tools.analytics_system", PLATFORM_ROOT / "tools" / "analytics_system", "generate Spot/Futures analytics reports and indicator snapshots", "read_safe_or_confirm_to_run", (PLATFORM_ROOT / "runtime" / "futures" / "data", PLATFORM_ROOT / "runtime" / "spot" / "data")),
    ToolSpec("backup_system", "platform_v2.tools.backup_system", PLATFORM_ROOT / "tools" / "backup_system", "create project/runtime backups", "confirm_required", (PLATFORM_ROOT.parent.parent / "runtime_archives",)),
    ToolSpec("diagnostics", "platform_v2.tools.diagnostics", PLATFORM_ROOT / "tools" / "diagnostics", "scan project health and write diagnostics reports", "read_safe_or_confirm_to_run", (PLATFORM_ROOT / "runtime" / "artifacts" / "diagnostics",)),
    ToolSpec("github_publish_system", "platform_v2.tools.github_publish_system", PLATFORM_ROOT / "tools" / "github_publish_system", "publish/sync project to GitHub", "confirm_required", logs=(PLATFORM_ROOT / "runtime" / "logs" / "tools",)),
    ToolSpec("news_generation_system", "platform_v2.tools.news_generation_system", PLATFORM_ROOT / "tools" / "news_generation_system", "generate local/public news content", "confirm_required", logs=(PLATFORM_ROOT / "runtime" / "logs" / "tools",)),
    ToolSpec("research", "platform_v2.tools.research", PLATFORM_ROOT / "tools" / "research", "what-if/replay research tools", "read_safe_or_confirm_to_run", (PLATFORM_ROOT / "runtime" / "artifacts" / "research",)),
    ToolSpec("runtime_reset_system", "platform_v2.tools.runtime_reset_system", PLATFORM_ROOT / "tools" / "runtime_reset_system", "archive and reset Spot/Futures runtime state", "confirm_required", (PLATFORM_ROOT.parent.parent / "runtime_archives",)),
    ToolSpec("runtime_start_system", "platform_v2.tools.runtime_start_system", PLATFORM_ROOT / "tools" / "runtime_start_system", "start Spot and Futures runtime loops", "confirm_required"),
    ToolSpec("sitemap_system", "platform_v2.tools.sitemap_system", PLATFORM_ROOT / "tools" / "sitemap_system", "generate sitemap assets", "confirm_required"),
    ToolSpec("telegram_bot_system", "platform_v2.tools.telegram_bot_system", PLATFORM_ROOT / "tools" / "telegram_bot_system", "Telegram notification/command transport", "confirm_required"),
    ToolSpec("video_reels", "platform_v2.tools.video_reels", PLATFORM_ROOT / "tools" / "video_reels", "video reel artifact pipeline", "confirm_required", (PLATFORM_ROOT / "runtime" / "artifacts" / "video_reels",)),
)


def answer_tools_registry() -> CapabilityAnswer:
    lines = ["SmartSignalHub internal tools registry"]
    sources: list[str] = []
    for tool in TOOLS:
        exists = tool.folder.exists()
        lines.append(f"- {tool.name}: exists={exists}, mode={tool.mode}")
        lines.append(f"  module={tool.module}")
        lines.append(f"  purpose={tool.purpose}")
        lines.append(f"  folder={tool.folder}")
        if tool.artifacts:
            lines.append("  artifacts=" + ", ".join(str(path) for path in tool.artifacts))
        if tool.logs:
            lines.append("  logs=" + ", ".join(str(path) for path in tool.logs))
        if exists:
            sources.append(str(tool.folder))
    return CapabilityAnswer("tools_registry", "\n".join(lines), tuple(sources))
