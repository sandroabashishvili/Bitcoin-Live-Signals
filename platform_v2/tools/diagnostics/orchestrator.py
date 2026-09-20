"""Diagnostics runner entry."""

from __future__ import annotations

from platform_v2.tools.diagnostics.checks.ast_checks import ast_findings, circular_import_findings
from platform_v2.tools.diagnostics.checks.backend_architecture_checks import backend_architecture_findings
from platform_v2.tools.diagnostics.checks.dead_code_checks import dead_python_candidate_findings
from platform_v2.tools.diagnostics.checks.frontend_checks import frontend_findings
from platform_v2.tools.diagnostics.checks.futures_dashboard_checks import futures_dashboard_findings
from platform_v2.tools.diagnostics.checks.payload_checks import frontend_payload_findings
from platform_v2.tools.diagnostics.checks.html_hook_checks import unused_html_hook_findings
from platform_v2.tools.diagnostics.checks.seo_checks import seo_findings
from platform_v2.tools.diagnostics.checks.semantic_ownership_checks import semantic_ownership_findings
from platform_v2.tools.diagnostics.checks.sqlite_runtime_checks import sqlite_runtime_parity_findings
from platform_v2.tools.diagnostics.checks.runtime_layout_checks import runtime_layout_findings
from platform_v2.tools.diagnostics.checks.runtime_duplication_checks import runtime_cross_family_duplication_findings
from platform_v2.tools.diagnostics.checks.futures_runtime_checks import (
    futures_runtime_integrity_findings,
    futures_runtime_schema_findings,
    futures_runtime_structure_findings,
)
from platform_v2.tools.diagnostics.checks.hedge_runtime_checks import (
    hedge_runtime_integrity_findings,
    hedge_runtime_schema_findings,
    hedge_runtime_structure_findings,
)
from platform_v2.tools.diagnostics.checks.runtime_checks import (
    runtime_integrity_findings,
    runtime_schema_findings,
    runtime_structure_findings,
    top_level_structure_findings,
)
from platform_v2.tools.diagnostics.checks.strategy_contract_checks import (
    spot_entry_location_contract_findings,
)
from platform_v2.tools.diagnostics.core.reports import summarize_findings, write_report_files
from platform_v2.tools.diagnostics.core.shared import compile_findings, repo_python_files


DEFAULT_PROFILE = "operational"
FULL_PROFILE = "full"
SUPPORTED_PROFILES = (DEFAULT_PROFILE, FULL_PROFILE)

_OPERATIONAL_SUPPRESSED_ISSUES = {
    "ambiguous_top_level_dir",
    "broad_except",
    "complex_function",
    "dead_css_candidate",
    "dead_python_candidate",
    "debug_marker",
    "empty_top_level_dir",
    "hardcoded_config_candidate",
    "missing_sitemap_coverage",
    "orphan_explanation_entry",
    "orphan_module_candidate",
    "oversized_file",
    "oversized_frontend_css",
    "oversized_frontend_html",
    "oversized_function",
    "overlapping_ui_roots",
    "print_heavy_module",
    "shared_helper_overgrowth",
    "silent_fallback_except",
    "too_many_top_level_defs",
    "unused_import",
    "unused_private_helper",
}


def _validate_profile(profile: str) -> str:
    normalized = (profile or DEFAULT_PROFILE).strip().lower()
    if normalized not in SUPPORTED_PROFILES:
        raise ValueError(f"unsupported diagnostics profile: {profile}")
    return normalized


def _filter_for_profile(findings, *, profile: str):
    if profile == FULL_PROFILE:
        return findings
    return [item for item in findings if item.issue not in _OPERATIONAL_SUPPRESSED_ISSUES]


def run(*, profile: str = DEFAULT_PROFILE) -> int:
    active_profile = _validate_profile(profile)
    paths = repo_python_files()
    findings = compile_findings(paths)

    if active_profile == FULL_PROFILE:
        findings.extend(ast_findings(paths))
        findings.extend(backend_architecture_findings(paths))
        findings.extend(dead_python_candidate_findings(paths))
        findings.extend(circular_import_findings(paths))

    findings.extend(runtime_structure_findings())
    findings.extend(runtime_schema_findings())
    findings.extend(runtime_integrity_findings())
    findings.extend(futures_runtime_structure_findings())
    findings.extend(futures_runtime_schema_findings())
    findings.extend(futures_runtime_integrity_findings())
    findings.extend(hedge_runtime_structure_findings())
    findings.extend(hedge_runtime_schema_findings())
    findings.extend(hedge_runtime_integrity_findings())
    findings.extend(spot_entry_location_contract_findings())
    findings.extend(top_level_structure_findings())
    findings.extend(runtime_layout_findings())
    findings.extend(runtime_cross_family_duplication_findings())
    findings.extend(frontend_findings())
    findings.extend(futures_dashboard_findings())
    findings.extend(frontend_payload_findings())
    findings.extend(unused_html_hook_findings())
    findings.extend(seo_findings())
    findings.extend(semantic_ownership_findings())
    findings.extend(sqlite_runtime_parity_findings())
    findings = _filter_for_profile(findings, profile=active_profile)

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda item: (severity_order.get(item.severity, 9), item.path, item.issue, item.detail))

    summary = summarize_findings(findings, profile=active_profile)
    json_path, md_path = write_report_files(summary)

    print(f"[OK] JSON report: {json_path.relative_to(json_path.parents[4])}")
    print(f"[OK] Markdown report: {md_path.relative_to(md_path.parents[4])}")
    print(f"[OK] Findings: {summary['findings_total']}")
    return 0
