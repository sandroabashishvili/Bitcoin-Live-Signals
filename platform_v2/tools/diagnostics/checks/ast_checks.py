"""AST-driven diagnostics checks."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from platform_v2.tools.diagnostics.core.config import (
    V2_ROOT,
)
from platform_v2.tools.diagnostics.checks.ast_scan_helpers import parse_source_tree
from platform_v2.tools.diagnostics.checks.ast_scan_rules import scan_tree_nodes
from platform_v2.tools.diagnostics.checks.ast_scan_state import collect_top_level_state
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding
from platform_v2.tools.diagnostics.core.shared import (
    annotate_parents,
    build_module_index,
    empty_inbound_counter,
    module_name_for_path,
    resolve_relative_module,
)


def check_layer_violations(path: Path, imported_modules: set[str], findings: list[FileFinding]) -> None:
    relative = path.relative_to(V2_ROOT)
    top = relative.parts[0]
    path_str = str(path.relative_to(V2_ROOT.parent))

    if top == "domain":
        forbidden = sorted(
            module for module in imported_modules
            if module.split(".")[0] in {"urllib", "http", "requests", "sqlite3", "pathlib", "os", "fcntl"}
        )
        if forbidden:
            add_finding(findings, path_str, "layer_violation_domain_io_dependency", ", ".join(forbidden), "high")

    if top == "app":
        infra_imports = sorted(module for module in imported_modules if module.startswith("platform_v2.spot.infrastructure"))
        if infra_imports:
            add_finding(findings, path_str, "app_layer_direct_infrastructure_dependency", ", ".join(infra_imports), "medium")

    if top == "runtime":
        if "platform_v2.spot.services" in imported_modules or any(mod.startswith("platform_v2.spot.services.") for mod in imported_modules):
            add_finding(findings, path_str, "runtime_layer_service_dependency", "runtime layer should not depend on services", "medium")


def scan_file_ast(path: Path, module_index: dict[str, Path], inbound_refs: Counter) -> list[FileFinding]:
    findings: list[FileFinding] = []
    path_str = str(path.relative_to(V2_ROOT.parent))
    top_level_dir = path.relative_to(V2_ROOT).parts[0]
    parsed = parse_source_tree(path, path_str, findings)
    if parsed is None:
        return findings
    source, tree = parsed
    state = collect_top_level_state(path=path, tree=tree, module_index=module_index, inbound_refs=inbound_refs)
    scan_tree_nodes(
        path=path,
        path_str=path_str,
        top_level_dir=top_level_dir,
        source=source,
        tree=tree,
        findings=findings,
        state=state,
    )
    check_layer_violations(path, state.imported_modules, findings)
    return findings


def orphan_module_findings(paths: list[Path], module_index: dict[str, Path], inbound_refs: Counter) -> list[FileFinding]:
    findings: list[FileFinding] = []
    entry_modules = {
        "platform_v2.spot.app.run_loop",
        "platform_v2.spot.app.commands.main_cycle",
        "platform_v2.spot.app.commands.indicator_builder",
        "platform_v2.spot.app.commands.position_updates",
        "platform_v2.spot.app.commands.signal_pipeline",
        "platform_v2.futures.app.run_loop",
        "platform_v2.tools.research.replay.execution_replay",
        "platform_v2.tools.research.replay.futures_entry_quality_what_if",
        "platform_v2.tools.research.replay.signal_only_replay",
    }
    for module_name, path in module_index.items():
        if path.name.startswith("test_") or "tests" in path.parts:
            continue
        if (
            "tools" in path.parts
            and "research" in path.parts
            and "replay" in path.parts
            and path.name.endswith("_what_if.py")
        ):
            continue
        if path.name == "__init__.py":
            continue
        if path.name == "__main__.py":
            continue
        if module_name in entry_modules:
            continue
        if inbound_refs[module_name] == 0 and path.parts[-2] not in {"docs", "frontend"}:
            add_finding(findings, str(path.relative_to(V2_ROOT.parent)), "orphan_module_candidate", "no internal imports and no known entrypoint", "low")
    return findings


def internal_import_graph(paths: list[Path], module_index: dict[str, Path]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for path in paths:
        module_name = module_name_for_path(path)
        graph[module_name] = set()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        annotate_parents(tree)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for name in node.names:
                    if name.name in module_index:
                        graph[module_name].add(name.name)
            elif isinstance(node, ast.ImportFrom):
                resolved = resolve_relative_module(path, node.module, node.level)
                if resolved and resolved in module_index:
                    graph[module_name].add(resolved)
    return graph


def circular_import_findings(paths: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    module_index = build_module_index(paths)
    graph = internal_import_graph(paths, module_index)
    seen_cycles: set[tuple[str, ...]] = set()

    def visit(node: str, stack: list[str], visiting: set[str], visited: set[str]) -> None:
        visiting.add(node)
        stack.append(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in visiting and neighbor not in visited:
                visit(neighbor, stack, visiting, visited)
            elif neighbor in visiting:
                cycle = stack[stack.index(neighbor):] + [neighbor]
                normalized = tuple(cycle)
                if normalized not in seen_cycles:
                    seen_cycles.add(normalized)
                    add_finding(findings, "platform_v2", "circular_import", " -> ".join(cycle), "medium")
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    visited: set[str] = set()
    for module_name in graph:
        if module_name not in visited:
            visit(module_name, [], set(), visited)

    return findings


def ast_findings(paths: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    module_index = build_module_index(paths)
    inbound_refs: Counter = empty_inbound_counter()

    for path in paths:
        findings.extend(scan_file_ast(path, module_index, inbound_refs))

    findings.extend(orphan_module_findings(paths, module_index, inbound_refs))
    return findings
