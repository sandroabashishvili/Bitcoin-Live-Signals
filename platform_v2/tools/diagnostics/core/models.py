"""Shared diagnostics data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict


@dataclass
class FileFinding:
    path: str
    issue: str
    detail: str
    severity: str


class FindingDict(TypedDict):
    path: str
    issue: str
    detail: str
    severity: str


class SummaryDict(TypedDict):
    generated_at: str
    profile: str
    roots: list[str]
    findings_total: int
    severity_counts: dict[str, int]
    issue_counts: dict[str, int]
    findings: list[FindingDict]
    assistant_summary: NotRequired[dict[str, Any]]


def add_finding(findings: list[FileFinding], path: str, issue: str, detail: str, severity: str) -> None:
    findings.append(FileFinding(path=path, issue=issue, detail=detail, severity=severity))
