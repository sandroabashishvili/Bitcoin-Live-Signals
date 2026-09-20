"""Futures dashboard diagnostics checks."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


FUTURES_DASHBOARD_ROOT = V2_ROOT / "futures" / "dashboard"
PAGE_DIR_NAMES = (
    "overview_futures",
    "portfolio_futures",
    "trade_outcomes_futures",
    "strategy_edge_futures",
    "orderbook_futures",
)
REQUIRED_NAV_TARGETS = (
    "../overview_futures/",
    "../portfolio_futures/",
    "../trade_outcomes_futures/",
    "../strategy_edge_futures/",
    "../orderbook_futures/",
)
FORBIDDEN_TOKENS = (
    "/platform_v2/public_site/overview_futures/",
    "/platform_v2/public_site/portfolio_futures/",
    "/platform_v2/public_site/trade_outcomes_futures/",
    "/platform_v2/public_site/strategy_edge_futures/",
    "/platform_v2/public_site/orderbook_futures/",
    "/home/sandro/SmartSignalHub/",
)
EXPLANATION_DATA_PATH = FUTURES_DASHBOARD_ROOT / "explanation_system" / "data" / "explanations.json"
EXPLANATION_KEY_PATTERN = re.compile(r"""data-expl-key=["']([^"']+)["']|render_explanation_anchor\(\s*key=['"]([^'"]+)['"]""")
PAYLOAD_KEY_PATTERN = re.compile(r"""payload\[['"]([^'"]+)['"]\]|payload\.get\(\s*['"]([^'"]+)['"]""")


def futures_dashboard_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    if not FUTURES_DASHBOARD_ROOT.exists():
        add_finding(findings, "platform_v2/futures/dashboard", "missing_futures_dashboard_root", "futures/dashboard is missing", "high")
        return findings

    findings.extend(_page_structure_findings())
    findings.extend(_generated_page_findings())
    findings.extend(_cross_root_findings())
    findings.extend(_explanation_findings())
    findings.extend(_payload_contract_findings())
    findings.extend(_dead_css_findings())
    return findings


def _page_structure_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    for page_name in PAGE_DIR_NAMES:
        page_dir = FUTURES_DASHBOARD_ROOT / page_name
        if not page_dir.exists():
            add_finding(findings, "platform_v2/futures/dashboard", "missing_page_dir", page_name, "high")
            continue

        if not (page_dir / "index.html").exists():
            add_finding(findings, _path_str(page_dir), "missing_page_file", "index.html", "medium")

        has_page_builder = (page_dir / "page_builder.py").exists() or (page_dir / "py" / "page_builder.py").exists()
        if not has_page_builder:
            add_finding(findings, _path_str(page_dir), "missing_page_file", "page_builder.py", "medium")
    return findings


def _generated_page_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    for page_name in PAGE_DIR_NAMES:
        html_path = FUTURES_DASHBOARD_ROOT / page_name / "index.html"
        if not html_path.exists():
            continue
        text = html_path.read_text(encoding="utf-8")
        if "<title>" not in text:
            add_finding(findings, _path_str(html_path), "missing_html_title", "missing <title>", "medium")
        if 'meta name="description"' not in text:
            add_finding(findings, _path_str(html_path), "missing_meta_description", "missing meta description", "medium")
        if "<!-- ssh-generator:" not in text:
            add_finding(findings, _path_str(html_path), "generated_page_missing_marker", "missing ssh-generator marker", "low")

        missing_nav = [href for href in REQUIRED_NAV_TARGETS if href not in text]
        if missing_nav:
            add_finding(findings, _path_str(html_path), "nav_link_drift", ", ".join(missing_nav), "medium")
    return findings


def _cross_root_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    candidate_files = list(FUTURES_DASHBOARD_ROOT.rglob("*.py")) + list(FUTURES_DASHBOARD_ROOT.rglob("*.html")) + list(FUTURES_DASHBOARD_ROOT.rglob("*.css"))
    for path in sorted(candidate_files):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                add_finding(findings, _path_str(path), "futures_dashboard_forbidden_reference", token, "high")
    return findings


def _explanation_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    explanation_keys = _load_explanation_keys()
    referenced_keys = _referenced_explanation_keys()
    for key in sorted(referenced_keys):
        if key not in explanation_keys:
            add_finding(findings, _path_str(EXPLANATION_DATA_PATH), "missing_explanation_content", key, "high")
    return findings


def _payload_contract_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    page_dirs = sorted(path for path in FUTURES_DASHBOARD_ROOT.iterdir() if path.is_dir())
    for page_dir in page_dirs:
        builder_path = page_dir / "py" / "page_builder.py"
        renderer_path = page_dir / "py" / "renderer.py"
        if not builder_path.exists() or not renderer_path.exists():
            continue
        builder_keys = _builder_payload_keys(builder_path)
        renderer_keys = _renderer_payload_keys(renderer_path)
        if not builder_keys or not renderer_keys:
            continue
        missing = sorted(key for key in renderer_keys if key not in builder_keys)
        if missing:
            add_finding(findings, _path_str(renderer_path), "payload_key_drift", ", ".join(missing), "medium")
    return findings


def _dead_css_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(FUTURES_DASHBOARD_ROOT.rglob("*"))
        if path.is_file() and path.suffix in {".py", ".html", ".js"}
    )
    simple_selector_pattern = re.compile(r"(?m)^([.#][a-zA-Z][\w\-]*)\s*\{")
    for css_path in sorted(FUTURES_DASHBOARD_ROOT.rglob("*.css")):
        text = css_path.read_text(encoding="utf-8")
        selectors = {match.group(1) for match in simple_selector_pattern.finditer(text)}
        for selector in sorted(selectors):
            token = selector[1:]
            if token not in frontend_text:
                add_finding(findings, _path_str(css_path), "dead_css_candidate", selector, "low")
    return findings


def _load_explanation_keys() -> set[str]:
    if not EXPLANATION_DATA_PATH.exists():
        return set()
    try:
        payload = json.loads(EXPLANATION_DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if not isinstance(payload, dict):
        return set()
    return {str(key) for key in payload}


def _referenced_explanation_keys() -> set[str]:
    keys: set[str] = set()
    candidate_files = list(FUTURES_DASHBOARD_ROOT.rglob("*.py")) + list(FUTURES_DASHBOARD_ROOT.rglob("*.html")) + list(FUTURES_DASHBOARD_ROOT.rglob("*.js"))
    for path in sorted(candidate_files):
        text = path.read_text(encoding="utf-8")
        for match in EXPLANATION_KEY_PATTERN.finditer(text):
            key = match.group(1) or match.group(2)
            if key:
                keys.add(key)
    return keys


def _builder_payload_keys(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def _renderer_payload_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    keys: set[str] = set()
    for match in PAYLOAD_KEY_PATTERN.finditer(text):
        key = match.group(1) or match.group(2)
        if key:
            keys.add(key)
    return keys


def _path_str(path: Path) -> str:
    return str(path.relative_to(V2_ROOT.parent))
