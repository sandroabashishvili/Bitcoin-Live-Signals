"""Utility helpers shared by AST scan rules."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from platform_v2.tools.diagnostics.core.config import (
    ALLOWED_LITERAL_NUMBERS,
    CONFIG_DRIFT_TOKENS,
    V2_ROOT,
)


def except_is_silent_fallback(node: ast.ExceptHandler) -> bool:
    if not node.body:
        return False
    if except_has_observable_report(node):
        return False
    for statement in node.body:
        if isinstance(statement, ast.Pass):
            return True
        if isinstance(statement, ast.Return):
            value = statement.value
            if value is None:
                return True
            if isinstance(value, ast.Constant) and value.value in {None, False, 0, 0.0, ""}:
                return True
            if isinstance(value, (ast.List, ast.Dict, ast.Tuple, ast.Set)):
                return True
    return False


def except_has_observable_report(node: ast.ExceptHandler) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name) and (func.id == "print" or func.id.startswith("print_")):
            return True
        if isinstance(func, ast.Name) and func.id in {"_send_json", "_write_history", "warn_runtime_fallback"}:
            return True
        if isinstance(func, ast.Attribute) and func.attr in {"_send_json", "_write_history"}:
            return True
        if isinstance(func, ast.Attribute) and func.attr in {"debug", "info", "warning", "error", "exception", "critical"}:
            return True
    return False


def safe_silent_fallback_context(path: Path, node: ast.ExceptHandler) -> bool:
    path_str = str(path.relative_to(V2_ROOT))
    function_name = enclosing_function_name(node)

    safe_prefixes = ("infrastructure/market_data/",)
    safe_functions = {
        "_load_json_list",
        "_load_json_dict",
        "_load_rows",
        "_load_dict",
        "_parse_candle_row",
        "_parse_snapshot_row",
        "_parse_position_row",
        "_fmt_number",
        "_fmt_timestamp_ms",
        "_normalize_event_number",
        "_has_rising_macd_histogram",
        "_as_float",
    }

    if path_str.startswith(safe_prefixes):
        return True
    if function_name in safe_functions:
        return True
    if path_str.startswith("services/") and function_name.startswith("_load_"):
        return True
    return False


def low_risk_silent_fallback_reason(path: Path, node: ast.ExceptHandler) -> str:
    path_str = str(path.relative_to(V2_ROOT))
    function_name = enclosing_function_name(node)
    lowered = function_name.casefold()

    if _is_parse_or_format_helper(lowered):
        return f"parse/format helper fallback in {function_name}"
    if _is_local_read_helper(lowered):
        return f"local read/load fallback in {function_name}"
    if path_str.startswith("tools/ai_assistant/") and function_name not in {"do_POST"}:
        return f"assistant read/format boundary fallback in {function_name}"
    if path_str.startswith("tools/research/replay/") and function_name.startswith("_safe_"):
        return f"research replay coercion fallback in {function_name}"
    if path_str.startswith("tools/telegram_bot_system/runtime_snapshot.py"):
        return f"telegram runtime snapshot coercion fallback in {function_name}"
    if path_str.endswith("/logging_utils.py") and function_name == "_fd_target":
        return "best-effort fd target lookup fallback"
    if path_str.startswith("tools/video_reels/") and function_name == "make_qr_clip":
        return "optional QR/video dependency fallback"
    return ""


def _is_parse_or_format_helper(function_name: str) -> bool:
    prefixes = (
        "_as",
        "as_",
        "_coerce",
        "coerce",
        "_fmt",
        "fmt_",
        "_format",
        "format_",
        "_parse",
        "parse_",
        "_safe",
        "safe_",
        "_to_",
    )
    tokens = (
        "timestamp",
        "float",
        "int",
        "number",
        "numeric",
        "percent",
        "sort_key",
        "macd_histogram",
        "net_pnl",
        "same_utc_date",
        "annualized",
        "elapsed_days",
    )
    return function_name.startswith(prefixes) or any(token in function_name for token in tokens)


def _is_local_read_helper(function_name: str) -> bool:
    prefixes = ("_read", "read_", "_load", "load_")
    return function_name.startswith(prefixes)


def enclosing_function_name(node: ast.AST) -> str:
    current = getattr(node, "parent", None)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
        current = getattr(current, "parent", None)
    return ""


def duplicate_class_method_names(node: ast.ClassDef) -> Counter[str]:
    names: Counter[str] = Counter()
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names[child.name] += 1
    return Counter({name: count for name, count in names.items() if count > 1})


def config_drift_assignment(node: ast.Assign) -> str | None:
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return None
    return config_drift_detail(node.targets[0].id, node.value)


def config_drift_ann_assignment(node: ast.AnnAssign) -> str | None:
    if not isinstance(node.target, ast.Name) or node.value is None:
        return None
    return config_drift_detail(node.target.id, node.value)


def config_drift_detail(name: str, value: ast.AST) -> str | None:
    lowered = name.lower()
    if not any(token in lowered for token in CONFIG_DRIFT_TOKENS):
        return None
    if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)) and value.value not in ALLOWED_LITERAL_NUMBERS:
        return f"{name} = {value.value}"
    return None
