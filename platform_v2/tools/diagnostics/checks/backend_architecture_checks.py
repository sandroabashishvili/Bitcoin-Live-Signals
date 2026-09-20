"""Backend-only maintainability and ownership checks."""

from __future__ import annotations

import ast
from collections import defaultdict
import hashlib
from pathlib import Path

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


_TERMINATORS = (ast.Return, ast.Raise, ast.Break, ast.Continue)
_BACKEND_SERVICE_PREFIXES = (
    "spot/services/",
    "futures/services/",
    "futures_hedge/services/",
)
_RESPONSIBILITY_PREFIXES = {
    "read": ("load", "read", "fetch", "get"),
    "write": ("write", "store", "save", "append", "upsert", "replace"),
    "decision": ("score", "evaluate", "decide", "classify", "resolve", "calculate"),
    "presentation": ("render", "format", "build_page"),
    "notification": ("notify", "send", "publish"),
}


def backend_architecture_findings(paths: list[Path]) -> list[FileFinding]:
    findings: list[FileFinding] = []
    duplicate_bodies: dict[str, list[tuple[Path, str, int, int]]] = defaultdict(list)

    for path in paths:
        relative = path.relative_to(V2_ROOT).as_posix()
        if _is_test_path(path):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue

        _add_shared_ownership_finding(path, relative, tree, findings)
        if _is_backend_path(relative):
            _add_unreachable_findings(path, tree, findings)
            _collect_duplicate_function_bodies(path, tree, duplicate_bodies)
            _add_multi_responsibility_finding(path, relative, source, tree, findings)

    _add_duplicate_body_findings(duplicate_bodies, findings)
    return findings


def _add_shared_ownership_finding(
    path: Path,
    relative: str,
    tree: ast.Module,
    findings: list[FileFinding],
) -> None:
    if not relative.startswith("shared/backend/"):
        return
    forbidden: set[str] = set()
    for node in ast.walk(tree):
        module = ""
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(("platform_v2.spot", "platform_v2.futures")):
                    forbidden.add(alias.name)
        if module.startswith(("platform_v2.spot", "platform_v2.futures")):
            forbidden.add(module)
    if forbidden:
        add_finding(
            findings,
            _display_path(path),
            "shared_backend_strategy_dependency",
            ", ".join(sorted(forbidden)),
            "high",
        )


def _add_unreachable_findings(
    path: Path,
    tree: ast.Module,
    findings: list[FileFinding],
) -> None:
    for body in _statement_bodies(tree):
        terminated_at: int | None = None
        for statement in body:
            if terminated_at is not None:
                add_finding(
                    findings,
                    _display_path(path),
                    "unreachable_python_code",
                    f"line {statement.lineno} follows unconditional control exit at line {terminated_at}",
                    "medium",
                )
                break
            if isinstance(statement, _TERMINATORS):
                terminated_at = statement.lineno


def _statement_bodies(tree: ast.AST):
    for node in ast.walk(tree):
        for attribute in ("body", "orelse", "finalbody"):
            value = getattr(node, attribute, None)
            if isinstance(value, list) and value and all(isinstance(item, ast.stmt) for item in value):
                yield value
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.body:
                    yield handler.body


def _collect_duplicate_function_bodies(
    path: Path,
    tree: ast.Module,
    groups: dict[str, list[tuple[Path, str, int, int]]],
) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        if node.name in {"__init__", "main"} or line_count < 10:
            continue
        body_tree = ast.Module(body=node.body, type_ignores=[])
        if sum(1 for _ in ast.walk(body_tree)) < 14:
            continue
        normalized = ast.dump(body_tree, annotate_fields=True, include_attributes=False)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        groups[digest].append((path, node.name, node.lineno, line_count))


def _add_duplicate_body_findings(
    groups: dict[str, list[tuple[Path, str, int, int]]],
    findings: list[FileFinding],
) -> None:
    for matches in groups.values():
        distinct_paths = {item[0] for item in matches}
        if len(distinct_paths) < 2:
            continue
        locations = "; ".join(
            f"{path.relative_to(V2_ROOT).as_posix()}:{line}:{name}"
            for path, name, line, _ in sorted(matches, key=lambda item: str(item[0]))
        )
        estimated_duplicate_lines = sum(item[3] for item in matches) - max(item[3] for item in matches)
        first_path = sorted(distinct_paths, key=str)[0]
        add_finding(
            findings,
            _display_path(first_path),
            "duplicate_backend_function_body",
            f"estimated duplicate lines={estimated_duplicate_lines}; {locations}",
            "medium",
        )


def _add_multi_responsibility_finding(
    path: Path,
    relative: str,
    source: str,
    tree: ast.Module,
    findings: list[FileFinding],
) -> None:
    if not relative.startswith(_BACKEND_SERVICE_PREFIXES):
        return
    line_count = source.count("\n") + 1
    if line_count <= 400:
        return
    names = [
        node.name.casefold()
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    responsibilities = sorted(
        label
        for label, prefixes in _RESPONSIBILITY_PREFIXES.items()
        if any(name.startswith(prefixes) for name in names)
    )
    if len(responsibilities) < 3:
        return
    add_finding(
        findings,
        _display_path(path),
        "backend_multi_responsibility_candidate",
        f"{line_count} lines; responsibilities={','.join(responsibilities)}",
        "medium",
    )


def _is_test_path(path: Path) -> bool:
    return path.name.startswith("test_") or "tests" in path.parts


def _is_backend_path(relative: str) -> bool:
    return not any(
        marker in relative
        for marker in ("/dashboard/", "public_site/", "shared/frontend/")
    )


def _display_path(path: Path) -> str:
    return str(path.relative_to(V2_ROOT.parent))
