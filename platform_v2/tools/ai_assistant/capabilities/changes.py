"""Change-history capability backed by git read-only commands."""

from __future__ import annotations

import subprocess

from platform_v2.tools.ai_assistant.runtime_readers import REPO_ROOT

from .contracts import CapabilityAnswer


def answer_changes() -> CapabilityAnswer:
    status = _git(["status", "--short"])
    last_commit = _git(["log", "-1", "--pretty=format:%h %ad %s", "--date=short"])
    changed_lines = [line for line in status.splitlines() if line.strip()]
    modified = sum(1 for line in changed_lines if line.startswith(" M") or line.startswith("M "))
    added = sum(1 for line in changed_lines if line.startswith("??") or line.startswith("A "))
    deleted = sum(1 for line in changed_lines if "D" in line[:2])
    groups = _group_changes(changed_lines)

    lines = [
        "Latest project change snapshot",
        f"Last commit: {last_commit or '--'}",
        f"Dirty worktree files: {len(changed_lines)}",
        f"Modified: {modified}",
        f"Added/untracked: {added}",
        f"Deleted: {deleted}",
    ]
    if groups:
        lines.append("Change groups:")
        lines.extend(f"- {name}: {count}" for name, count in groups[:10])
    if changed_lines:
        lines.append("First changed paths:")
        lines.extend(f"- {line}" for line in changed_lines[:12])
    lines.append(f"Source: git status/log in {REPO_ROOT}")
    return CapabilityAnswer("changes", "\n".join(lines), (str(REPO_ROOT),))


def _git(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _group_changes(lines: list[str]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for line in lines:
        path = _path_from_status_line(line)
        group = _group_for_path(path)
        counts[group] = counts.get(group, 0) + 1
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def _path_from_status_line(line: str) -> str:
    if line.startswith("?? "):
        return _clean_status_path(line[3:])
    return _clean_status_path(line[2:])


def _clean_status_path(path: str) -> str:
    return path.strip().strip('"')


def _group_for_path(path: str) -> str:
    if path.startswith("platform_v2/futures/"):
        return "futures"
    if path.startswith("platform_v2/spot/"):
        return "spot"
    if path.startswith("platform_v2/public_site/"):
        return "public_site"
    if path.startswith("platform_v2/tools/"):
        return "tools"
    if path.startswith("platform_v2/docs/"):
        return "docs"
    if path.startswith("platform_v2/runtime/"):
        return "runtime"
    if path.startswith("platform_v2/shared/"):
        return "shared"
    if path.startswith("platform_v2/"):
        return "platform_v2_other"
    return path.split("/", 1)[0] if "/" in path else path or "unknown"
