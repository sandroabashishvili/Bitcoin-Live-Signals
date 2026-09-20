"""Post-processing helpers for AST scan results."""

from __future__ import annotations

from platform_v2.tools.diagnostics.checks.ast_scan_state import ScanState
from platform_v2.tools.diagnostics.core.config import (
    COMMENT_MARKERS,
    DEBUG_MARKERS,
    HIGH_FILE_LINES,
    MAX_OK_LINES,
    PRINT_HEAVY_THRESHOLD,
    SHARED_HELPER_OK_LINES,
)
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


def add_post_scan_findings(
    *,
    path_str: str,
    source: str,
    findings: list[FileFinding],
    state: ScanState,
) -> None:
    _add_unused_import_findings(path_str, findings, state)
    _add_unused_private_helper_findings(path_str, findings, state)
    _add_duplicate_top_level_findings(path_str, findings, state)
    _add_unused_module_constant_findings(path_str, findings, state)
    _add_file_shape_findings(path_str, source, findings, state.top_level_defs, state.print_calls)


def _add_unused_import_findings(path_str: str, findings: list[FileFinding], state: ScanState) -> None:
    for alias in sorted(name for name in state.imported if name not in state.used_names and name != "annotations" and not name.startswith("_")):
        add_finding(findings, path_str, "unused_import", f"{alias} -> {state.imported[alias]}", "low")


def _add_unused_private_helper_findings(path_str: str, findings: list[FileFinding], state: ScanState) -> None:
    for private_name in sorted(name for name in state.top_level_private_defs if name not in state.used_names):
        add_finding(findings, path_str, "unused_private_helper", private_name, "low")


def _add_duplicate_top_level_findings(path_str: str, findings: list[FileFinding], state: ScanState) -> None:
    for name, count in sorted(state.top_level_names.items()):
        if count > 1:
            add_finding(findings, path_str, "duplicate_top_level_def_name", f"{name} defined {count} times", "high")


def _add_unused_module_constant_findings(path_str: str, findings: list[FileFinding], state: ScanState) -> None:
    for constant_name in sorted(name for name in state.module_constants if name not in state.used_names):
        add_finding(findings, path_str, "unused_module_constant", constant_name, "low")


def _add_file_shape_findings(
    path_str: str,
    source: str,
    findings: list[FileFinding],
    top_level_defs: int,
    print_calls: int,
) -> None:
    line_count = source.count("\n") + 1
    if line_count > MAX_OK_LINES:
        severity = "high" if line_count > HIGH_FILE_LINES else "medium"
        add_finding(findings, path_str, "oversized_file", f"{line_count} lines", severity)
    if any(marker in path_str for marker in ("shared/frontend/", "shared/backend/")) and line_count > SHARED_HELPER_OK_LINES:
        add_finding(findings, path_str, "shared_helper_overgrowth", f"{line_count} lines", "medium")
    if print_calls > PRINT_HEAVY_THRESHOLD:
        add_finding(findings, path_str, "print_heavy_module", f"{print_calls} print() calls", "medium")
    if not path_str.endswith("tools/diagnostics/core/config.py"):
        lowered = source.lower()
        for marker in DEBUG_MARKERS:
            count = lowered.count(marker)
            if count:
                add_finding(findings, path_str, "debug_marker", f"{marker} -> {count}", "low")
        for marker in COMMENT_MARKERS:
            count = lowered.count(marker)
            if count:
                add_finding(findings, path_str, "comment_marker", f"{marker} -> {count}", "low")
    if top_level_defs > 12:
        add_finding(findings, path_str, "too_many_top_level_defs", f"{top_level_defs} top-level defs", "medium")
