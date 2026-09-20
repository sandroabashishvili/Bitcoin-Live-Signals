"""Diagnostics and project inventory capability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platform_v2.tools.ai_assistant.formatters import format_diagnostics
from platform_v2.tools.ai_assistant.runtime_readers import REPO_ROOT, latest_diagnostics_report

from .contracts import CapabilityAnswer


IGNORED_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules"}


def answer_diagnostics(question: str = "") -> CapabilityAnswer:
    profile = "full" if "full" in question.casefold() else None
    result = latest_diagnostics_report(profile=profile)
    row = result.row or {}
    raw_findings = row.get("findings")
    findings = raw_findings if isinstance(raw_findings, list) else []
    assistant_summary = row.get("assistant_summary")
    summary = assistant_summary if isinstance(assistant_summary, dict) else {}
    lines = [
        "Diagnostics report",
        f"Generated: {_value(row.get('generated_at'))}",
        f"Profile: {_value(row.get('profile'))}",
        f"Findings total: {_value(row.get('findings_total', len(findings)))}",
        f"Severity counts: {_value(row.get('severity_counts'))}",
        f"Issue counts: {_value(row.get('issue_counts'))}",
    ]
    if result.source:
        lines.append(f"Report: {result.source}")
    if summary:
        lines.extend(_assistant_summary_lines(summary))
    lines.append(format_diagnostics(result))
    if findings:
        lines.append("First findings:")
        for finding in findings[:5]:
            lines.append(f"- {_finding_summary(finding)}")
        lines.append("Next action: inspect listed files and rerun diagnostics after fixes.")
    else:
        lines.append("Verdict: latest diagnostics report has no findings.")
    return CapabilityAnswer("diagnostics", "\n".join(lines), (result.source,) if result.source else ())


def _assistant_summary_lines(summary: dict[str, Any]) -> list[str]:
    lines = ["Assistant summary:"]
    lines.append(f"- Status: {_value(summary.get('status'))}")
    next_actions = summary.get("recommended_next_actions")
    if isinstance(next_actions, list) and next_actions:
        lines.append("- Recommended next actions:")
        lines.extend(f"  - {_value(action)}" for action in next_actions[:5])
    top_issues = summary.get("top_issue_counts")
    if isinstance(top_issues, dict) and top_issues:
        lines.append("- Top issue counts:")
        lines.extend(f"  - {issue}: {count}" for issue, count in list(top_issues.items())[:8])
    top_paths = summary.get("top_path_counts")
    if isinstance(top_paths, dict) and top_paths:
        lines.append("- Top path counts:")
        lines.extend(f"  - {path}: {count}" for path, count in list(top_paths.items())[:8])
    actionable = summary.get("top_actionable_findings")
    if isinstance(actionable, list) and actionable:
        lines.append("- Top actionable findings:")
        for finding in actionable[:5]:
            lines.append(f"  - {_finding_summary(finding)}")
    return lines


def answer_file_inventory() -> CapabilityAnswer:
    total_files = 0
    python_files = 0
    docs_files = 0
    runtime_files = 0
    top_level_counts: dict[str, int] = {}

    for path in _iter_project_files(REPO_ROOT):
        total_files += 1
        suffix = path.suffix.casefold()
        if suffix == ".py":
            python_files += 1
        if suffix in (".md", ".txt", ".rst"):
            docs_files += 1
        if "/runtime/" in path.as_posix():
            runtime_files += 1
        rel_parts = path.relative_to(REPO_ROOT).parts
        top = rel_parts[0] if rel_parts else "."
        top_level_counts[top] = top_level_counts.get(top, 0) + 1

    text = "\n".join(
        [
            "Project file inventory",
            f"Total files: {total_files}",
            f"Python files: {python_files}",
            f"Docs/text files: {docs_files}",
            f"Runtime-related files: {runtime_files}",
            "Top-level breakdown:",
            *[
                f"- {name}: {count}"
                for name, count in sorted(top_level_counts.items(), key=lambda item: item[1], reverse=True)[:12]
            ],
            f"Root: {REPO_ROOT}",
        ]
    )
    return CapabilityAnswer("diagnostics", text, (str(REPO_ROOT),))


def _iter_project_files(root: Path):
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def _finding_summary(finding: Any) -> str:
    if not isinstance(finding, dict):
        return str(finding)
    severity = finding.get("severity") or finding.get("level") or "--"
    issue = finding.get("issue") or finding.get("type") or finding.get("message") or "--"
    path = finding.get("path") or finding.get("file") or "--"
    return f"{severity}: {issue} ({path})"


def _value(value: Any) -> str:
    return "--" if value in (None, "") else str(value)
