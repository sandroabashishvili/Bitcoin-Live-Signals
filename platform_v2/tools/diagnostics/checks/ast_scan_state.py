"""State collection helpers for AST file scanning."""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from platform_v2.tools.diagnostics.core.shared import resolve_relative_module


@dataclass
class ScanState:
    imported: dict[str, str] = field(default_factory=dict)
    imported_modules: set[str] = field(default_factory=set)
    used_names: set[str] = field(default_factory=set)
    print_calls: int = 0
    top_level_defs: int = 0
    top_level_private_defs: list[str] = field(default_factory=list)
    module_constants: list[str] = field(default_factory=list)
    top_level_names: Counter[str] = field(default_factory=Counter)


def collect_top_level_state(
    *,
    path: Path,
    tree: ast.AST,
    module_index: dict[str, Path],
    inbound_refs: Counter,
) -> ScanState:
    state = ScanState()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            state.top_level_defs += 1
            state.top_level_names[node.name] += 1
            if node.name.startswith("_") and not node.name.startswith("__"):
                state.top_level_private_defs.append(node.name)
        elif isinstance(node, ast.Import):
            _collect_import_node(node, state, module_index, inbound_refs)
        elif isinstance(node, ast.ImportFrom):
            _collect_import_from_node(path, node, state, module_index, inbound_refs)
        elif isinstance(node, ast.Assign):
            _collect_module_constants_from_assign(node, state)
        elif isinstance(node, ast.AnnAssign):
            _collect_module_constants_from_annassign(node, state)
    return state


def _collect_import_node(
    node: ast.Import,
    state: ScanState,
    module_index: dict[str, Path],
    inbound_refs: Counter,
) -> None:
    for name in node.names:
        alias = name.asname or name.name.split(".")[0]
        state.imported[alias] = name.name
        state.imported_modules.add(name.name)
        if name.name in module_index:
            inbound_refs[name.name] += 1


def _collect_import_from_node(
    path: Path,
    node: ast.ImportFrom,
    state: ScanState,
    module_index: dict[str, Path],
    inbound_refs: Counter,
) -> None:
    module_name = resolve_relative_module(path, node.module, node.level) or ""
    if module_name:
        state.imported_modules.add(module_name)
        if module_name in module_index:
            inbound_refs[module_name] += 1
    for name in node.names:
        if name.name == "*":
            continue
        alias = name.asname or name.name
        imported_target = f"{module_name}.{name.name}" if module_name else name.name
        state.imported[alias] = imported_target
        if imported_target in module_index:
            inbound_refs[imported_target] += 1


def _collect_module_constants_from_assign(node: ast.Assign, state: ScanState) -> None:
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id.isupper():
            state.module_constants.append(target.id)


def _collect_module_constants_from_annassign(node: ast.AnnAssign, state: ScanState) -> None:
    if isinstance(node.target, ast.Name) and node.target.id.isupper():
        state.module_constants.append(node.target.id)
