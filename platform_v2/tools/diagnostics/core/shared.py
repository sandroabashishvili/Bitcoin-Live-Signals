"""Shared diagnostics helper functions."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import py_compile
from py_compile import PyCompileError
from typing import Iterable

from platform_v2.tools.diagnostics.core.config import V2_ROOT, SCAN_ROOTS
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


def repo_python_files() -> list[Path]:
    files: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = V2_ROOT / root_name
        if root.exists():
            files.extend(sorted(root.rglob("*.py")))
    return files


def module_name_for_path(path: Path) -> str:
    relative = path.relative_to(V2_ROOT)
    return ".".join(("platform_v2",) + relative.with_suffix("").parts)


def resolve_relative_module(path: Path, module: str | None, level: int) -> str | None:
    if level == 0:
        return module
    current_parts = list(module_name_for_path(path).split("."))
    if not current_parts:
        return None
    keep_parts = current_parts[:-level] if level > 0 else current_parts[:-1]
    if module:
        keep_parts.extend(module.split("."))
    resolved = ".".join(part for part in keep_parts if part)
    return resolved or None


def complexity_score(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.IfExp)):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(1, len(child.values) - 1)
        elif isinstance(child, ast.comprehension):
            score += 1
        elif isinstance(child, ast.Match):
            score += len(child.cases)
    return score


def function_length(node: ast.AST) -> int | None:
    lineno = getattr(node, "lineno", None)
    end_lineno = getattr(node, "end_lineno", None)
    if isinstance(lineno, int) and isinstance(end_lineno, int):
        return end_lineno - lineno + 1
    return None


def annotate_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "parent", parent)


def compile_findings(paths: Iterable[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    for path in paths:
        try:
            py_compile.compile(str(path), doraise=True)
        except (PyCompileError, OSError) as exc:
            add_finding(findings, str(path.relative_to(V2_ROOT.parent)), "compile_error", str(exc), "high")
    return findings


def build_module_index(paths: list[Path]) -> dict[str, Path]:
    return {module_name_for_path(path): path for path in paths}


def empty_inbound_counter() -> Counter:
    return Counter()
