"""Node-level AST scan rules."""

from __future__ import annotations

import ast
from pathlib import Path

from platform_v2.tools.diagnostics.checks.ast_scan_postprocess import add_post_scan_findings
from platform_v2.tools.diagnostics.checks.ast_scan_rule_utils import (
    config_drift_ann_assignment,
    config_drift_assignment,
    duplicate_class_method_names,
    except_is_silent_fallback,
    low_risk_silent_fallback_reason,
    safe_silent_fallback_context,
)
from platform_v2.tools.diagnostics.checks.ast_scan_state import ScanState
from platform_v2.tools.diagnostics.core.config import (
    COMPLEXITY_THRESHOLD,
    HIGH_COMPLEXITY_THRESHOLD,
    HIGH_FUNCTION_LINES,
    MAX_OK_FUNCTION_LINES,
)
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding
from platform_v2.tools.diagnostics.core.shared import complexity_score, function_length


def scan_tree_nodes(
    *,
    path: Path,
    path_str: str,
    top_level_dir: str,
    source: str,
    tree: ast.AST,
    findings: list[FileFinding],
    state: ScanState,
) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            state.used_names.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            state.used_names.add(node.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            state.print_calls += 1
        elif isinstance(node, ast.ExceptHandler):
            _scan_except_handler(path, path_str, node, findings)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _scan_function_node(path_str, node, findings)
        elif isinstance(node, ast.ClassDef):
            _scan_class_node(path_str, node, findings)
        elif isinstance(node, ast.Assign):
            _scan_assignment_node(path_str, top_level_dir, node, findings)
        elif isinstance(node, ast.AnnAssign):
            _scan_ann_assignment_node(path_str, top_level_dir, node, findings)

    add_post_scan_findings(path_str=path_str, source=source, findings=findings, state=state)


def _scan_except_handler(path: Path, path_str: str, node: ast.ExceptHandler, findings: list[FileFinding]) -> None:
    if node.type is None:
        add_finding(findings, path_str, "broad_except", "bare except", "medium")
    elif isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}:
        add_finding(findings, path_str, "broad_except", node.type.id, "medium")
    if not except_is_silent_fallback(node) or safe_silent_fallback_context(path, node):
        return
    low_risk_reason = low_risk_silent_fallback_reason(path, node)
    if low_risk_reason:
        add_finding(findings, path_str, "safe_silent_fallback", low_risk_reason, "low")
        return
    add_finding(findings, path_str, "silent_fallback_except", "except block returns/pass fallback value", "medium")


def _scan_function_node(path_str: str, node: ast.FunctionDef | ast.AsyncFunctionDef, findings: list[FileFinding]) -> None:
    fn_len = function_length(node)
    if fn_len and fn_len > MAX_OK_FUNCTION_LINES:
        severity = "high" if fn_len > HIGH_FUNCTION_LINES else "medium"
        add_finding(findings, path_str, "oversized_function", f"{node.name} -> {fn_len} lines", severity)
    fn_complexity = complexity_score(node)
    if fn_complexity > COMPLEXITY_THRESHOLD:
        severity = "high" if fn_complexity > HIGH_COMPLEXITY_THRESHOLD else "medium"
        add_finding(findings, path_str, "complex_function", f"{node.name} -> complexity {fn_complexity}", severity)


def _scan_class_node(path_str: str, node: ast.ClassDef, findings: list[FileFinding]) -> None:
    duplicate_method_names = duplicate_class_method_names(node)
    for method_name, count in sorted(duplicate_method_names.items()):
        add_finding(findings, path_str, "duplicate_class_method_name", f"{node.name}.{method_name} defined {count} times", "high")


def _scan_assignment_node(path_str: str, top_level_dir: str, node: ast.Assign, findings: list[FileFinding]) -> None:
    literal_drift = None if _is_config_literal_owner(path_str, top_level_dir) else config_drift_assignment(node)
    if literal_drift:
        add_finding(findings, path_str, "hardcoded_config_candidate", literal_drift, "low")


def _scan_ann_assignment_node(path_str: str, top_level_dir: str, node: ast.AnnAssign, findings: list[FileFinding]) -> None:
    literal_drift = None if _is_config_literal_owner(path_str, top_level_dir) else config_drift_ann_assignment(node)
    if literal_drift:
        add_finding(findings, path_str, "hardcoded_config_candidate", literal_drift, "low")


def _is_config_literal_owner(path_str: str, top_level_dir: str) -> bool:
    return (
        top_level_dir == "config"
        or path_str.endswith("tools/diagnostics/core/config.py")
        or path_str.endswith("/config/settings.py")
    )
