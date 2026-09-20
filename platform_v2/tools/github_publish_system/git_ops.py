from __future__ import annotations

import subprocess
from pathlib import Path


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, text=True, capture_output=True)


def clone_if_missing(repo: Path, repo_url: str, branch: str, *, dry_run: bool) -> None:
    if repo.exists():
        return
    if dry_run:
        print(f"[dry-run] Would clone {repo_url} -> {repo}")
        return
    repo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--branch", branch, repo_url, str(repo)],
        check=True,
        text=True,
    )


def current_branch(repo: Path) -> str:
    return run(["git", "branch", "--show-current"], cwd=repo).stdout.strip()


def update_from_remote(repo: Path, branch: str) -> None:
    run(["git", "fetch", "origin"], cwd=repo)
    run(["git", "pull", "--rebase", "--autostash", "origin", branch], cwd=repo)


def has_changes(repo: Path) -> bool:
    result = run(["git", "status", "--porcelain"], cwd=repo)
    return bool(result.stdout.strip())


def commit_snapshot(repo: Path, message: str, *, amend: bool = False) -> None:
    run(["git", "add", "-A"], cwd=repo)
    if amend:
        run(["git", "commit", "--amend", "-m", message], cwd=repo)
    else:
        run(["git", "commit", "-m", message], cwd=repo)


def push_snapshot(repo: Path, branch: str, *, force: bool = False) -> None:
    if force:
        run(["git", "push", "--force-with-lease", "origin", branch], cwd=repo)
    else:
        run(["git", "push", "origin", branch], cwd=repo)
