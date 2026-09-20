"""Helper utilities for AST file scanning."""

from __future__ import annotations

import ast
from pathlib import Path

from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding
from platform_v2.tools.diagnostics.core.shared import annotate_parents


def parse_source_tree(path: Path, path_str: str, findings: list[FileFinding]) -> tuple[str, ast.AST] | None:
    source = ""
    tree: ast.AST | None = None
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as exc:
        add_finding(findings, path_str, "parse_error", str(exc), "high")
    if tree is None:
        return None
    annotate_parents(tree)
    return source, tree
