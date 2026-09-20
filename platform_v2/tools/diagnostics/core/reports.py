"""File: reports.py
Folder: platform_v2/tools/diagnostics/core
Created date: 2026-04-18
Last updated date: 2026-06-04
Author: Codex
Purpose: Write whole-platform diagnostics summaries and report files.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from platform_v2.tools.diagnostics.core.config import SCAN_ROOTS, V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, FindingDict, SummaryDict


def summarize_findings(findings: list[FileFinding], *, profile: str) -> SummaryDict:
    by_severity = Counter(finding.severity for finding in findings)
    by_issue = Counter(finding.issue for finding in findings)
    finding_dicts = [FindingDict(**asdict(finding)) for finding in findings]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile": profile,
        "roots": list(SCAN_ROOTS),
        "findings_total": len(findings),
        "severity_counts": dict(by_severity),
        "issue_counts": dict(by_issue),
        "findings": finding_dicts,
        "assistant_summary": _assistant_summary(finding_dicts, profile=profile),
    }


def _assistant_summary(findings: list[FindingDict], *, profile: str) -> dict[str, Any]:
    by_path = Counter(finding["path"] for finding in findings)
    by_issue = Counter(finding["issue"] for finding in findings)
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    sorted_findings = sorted(
        findings,
        key=lambda finding: (
            severity_rank.get(finding["severity"], 9),
            finding["path"],
            finding["issue"],
            finding["detail"],
        ),
    )
    next_actions = _recommended_next_actions(findings=findings, profile=profile)
    return {
        "profile": profile,
        "status": "clean" if not findings else "findings",
        "top_actionable_findings": sorted_findings[:10],
        "top_issue_counts": dict(by_issue.most_common(10)),
        "top_path_counts": dict(by_path.most_common(10)),
        "recommended_next_actions": next_actions,
        "reading_order": ["high", "medium", "low"],
    }


def _recommended_next_actions(*, findings: list[FindingDict], profile: str) -> list[str]:
    if not findings:
        return ["No diagnostics findings. Continue with regression/runtime checks before changing strategy code."]
    issues = Counter(finding["issue"] for finding in findings)
    actions: list[str] = []
    if issues.get("misplaced_runtime_artifact"):
        actions.append("Move or remove misplaced runtime artifacts before treating operational diagnostics as clean.")
    if issues.get("runtime_schema_error") or issues.get("runtime_missing_keys") or issues.get("runtime_impossible_state"):
        actions.append("Fix runtime schema/integrity findings before frontend or strategy tuning.")
    if issues.get("missing_sitemap_coverage"):
        actions.append("Regenerate sitemap after news/public-site generation.")
    if profile == "full" and (issues.get("oversized_file") or issues.get("oversized_function") or issues.get("complex_function")):
        actions.append("Use full-profile size/complexity findings as refactor candidates, not immediate runtime blockers.")
    if profile == "full" and issues.get("silent_fallback_except"):
        actions.append("Review remaining real silent_fallback_except findings first; safe_silent_fallback rows are low-risk parse/read fallbacks.")
    if profile == "full" and issues.get("safe_silent_fallback"):
        actions.append("Treat safe_silent_fallback as tracked noise unless the related parser/reader becomes user-facing or trading-critical.")
    return actions or ["Review findings in severity order: high, then medium, then low."]


def write_report_files(summary: SummaryDict) -> tuple[Path, Path]:
    output_dir = V2_ROOT / "runtime" / "artifacts" / "diagnostics"
    output_dir.mkdir(parents=True, exist_ok=True)
    date_iso = datetime.now().date().isoformat()
    profile = str(summary.get("profile", "operational") or "operational").strip().lower()
    profile_suffix = "" if profile == "operational" else f"_{profile}"
    json_path = output_dir / f"v2_code_diagnostics{profile_suffix}_{date_iso}.json"
    md_path = output_dir / f"v2_code_diagnostics{profile_suffix}_{date_iso}.md"

    json_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    lines = [
        "# V2 Code Diagnostics",
        "",
        f"- Generated: `{summary['generated_at']}`",
        f"- Profile: `{summary.get('profile', 'operational')}`",
        f"- Findings: `{summary['findings_total']}`",
        "",
        "## Severity Counts",
    ]
    for severity, count in sorted((summary["severity_counts"] or {}).items()):
        lines.append(f"- `{severity}`: `{count}`")

    assistant_summary = summary.get("assistant_summary") or {}
    if assistant_summary:
        lines.extend(["", "## Assistant Summary", ""])
        lines.append(f"- Status: `{assistant_summary.get('status', '--')}`")
        lines.append("- Recommended next actions:")
        for action in assistant_summary.get("recommended_next_actions", []):
            lines.append(f"  - {action}")
        lines.append("- Top issue counts:")
        for issue, count in (assistant_summary.get("top_issue_counts") or {}).items():
            lines.append(f"  - `{issue}`: `{count}`")
        lines.append("- Top path counts:")
        for path, count in (assistant_summary.get("top_path_counts") or {}).items():
            lines.append(f"  - `{path}`: `{count}`")

    lines.extend(["", "## Findings", ""])
    findings = summary["findings"]
    if not findings:
        lines.append("- No findings.")
    else:
        for finding in findings:
            lines.append(
                f"- `{finding['severity']}` `{finding['issue']}` "
                f"[{finding['path']}](/home/sandro/SmartSignalHub/{finding['path']}): {finding['detail']}"
            )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
