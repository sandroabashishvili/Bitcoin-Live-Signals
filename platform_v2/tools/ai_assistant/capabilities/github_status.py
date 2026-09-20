"""GitHub status capability with local git fallback."""

from __future__ import annotations

import shutil
import subprocess

from platform_v2.tools.ai_assistant.runtime_readers import REPO_ROOT

from .contracts import CapabilityAnswer


def answer_github_status() -> CapabilityAnswer:
    remote = _git(["remote", "-v"])
    branch = _git(["branch", "--show-current"])
    upstream = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    gh_available = shutil.which("gh") is not None

    lines = [
        "GitHub status capability",
        f"Local branch: {branch or '--'}",
        f"Upstream: {upstream or '--'}",
        f"gh CLI available: {gh_available}",
    ]
    if remote:
        lines.append("Git remotes:")
        lines.extend(f"- {line}" for line in remote.splitlines()[:6])
    else:
        lines.append("Git remotes: none found")
    lines.extend(
        [
            "Live GitHub checks are not wired yet.",
            "To answer PR/workflow/release questions reliably, this capability needs read-only gh/API integration.",
        ]
    )
    return CapabilityAnswer("github_status", "\n".join(lines), (str(REPO_ROOT),))


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
