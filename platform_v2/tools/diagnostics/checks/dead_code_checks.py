"""Dead/stale code candidate checks."""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


@dataclass(frozen=True)
class TopLevelDef:
    path: Path
    name: str
    kind: str
    lineno: int


ENTRYPOINT_DEF_NAMES = {"run", "main"}
ENTRYPOINT_FILE_NAMES = {"__main__.py", "orchestrator.py", "main.py"}


def dead_python_candidate_findings(paths: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    definitions: list[TopLevelDef] = []
    symbol_uses: Counter[str] = Counter()

    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue

        exported = exported_names(tree)
        definitions.extend(module_top_level_defs(path, tree, exported))
        symbol_uses.update(module_symbol_uses(tree))

    for item in definitions:
        if symbol_uses[item.name] > 0:
            continue
        if should_skip_dead_candidate(item):
            continue
        add_finding(
            findings,
            str(item.path.relative_to(V2_ROOT.parent)),
            "dead_python_candidate",
            f"{item.kind} {item.name} at line {item.lineno}",
            "low",
        )

    return findings


def module_top_level_defs(path: Path, tree: ast.Module, exported: set[str]) -> list[TopLevelDef]:
    items: list[TopLevelDef] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name in exported:
            continue
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        items.append(TopLevelDef(path=path, name=node.name, kind=kind, lineno=node.lineno))
    return items


def module_symbol_uses(tree: ast.AST) -> Counter[str]:
    uses: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            uses[node.id] += 1
        elif isinstance(node, ast.Attribute):
            uses[node.attr] += 1
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                uses[alias.name] += 1
    return uses


def exported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                names.update(string_names_from_value(node.value))
    return names


def string_names_from_value(node: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                names.add(elt.value)
    return names


def should_skip_dead_candidate(item: TopLevelDef) -> bool:
    if _is_test_path(item.path):
        return True
    if item.name.startswith("__"):
        return True
    if item.path.name in ENTRYPOINT_FILE_NAMES and item.name in ENTRYPOINT_DEF_NAMES:
        return True
    if item.path.name == "__init__.py":
        return True
    if "domain/models/" in str(item.path.relative_to(V2_ROOT)):
        return True
    if _is_research_replay_entrypoint(item):
        return True
    return False


def _is_test_path(path: Path) -> bool:
    return path.name.startswith("test_") or "tests" in path.parts


def _is_research_replay_entrypoint(item: TopLevelDef) -> bool:
    rel = item.path.relative_to(V2_ROOT).as_posix()
    if not rel.startswith("tools/research/replay/"):
        return False
    if item.path.name.endswith("_what_if.py") and item.name in ENTRYPOINT_DEF_NAMES:
        return True
    return item.path.name in {"execution_replay.py", "signal_only_replay.py"} and item.name in ENTRYPOINT_DEF_NAMES
