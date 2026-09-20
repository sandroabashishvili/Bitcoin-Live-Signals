"""Frontend-specific diagnostics checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
import ast

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


FRONTEND_ROOT = V2_ROOT / "spot" / "dashboard"
PAGE_DIR_NAMES = ("overview_spot", "portfolio", "trade_outcomes", "strategy_edge", "orderbook")
REQUIRED_NAV_TARGETS = (
    "../overview_spot/",
    "../portfolio/",
    "../trade_outcomes/",
    "../strategy_edge/",
    "../orderbook/",
)
FORBIDDEN_CROSS_ROOT_TOKENS = (
    "../docs/",
    "../../docs/",
    "../../../docs/",
    "/home/sandro/SmartSignalHub/docs/",
)
EXPLANATION_DATA_PATH = FRONTEND_ROOT / "explanation_system" / "data" / "explanations.json"
EXPLANATION_KEY_PATTERN = re.compile(r"""data-expl-key=["']([^"']+)["']|render_explanation_anchor\(\s*key=['"]([^'"]+)['"]""")
CRITICAL_OVERVIEW_EXPLANATION_KEYS = (
    "overview.primary_signal.panel",
    "overview.signal_context.panel",
    "overview.portfolio_snapshot.panel",
    "overview.trade_outcomes_snapshot.panel",
    "overview.strategy_snapshot.panel",
    "overview.equity_chart.panel",
    "overview.primary_signal.entry_status",
)


def frontend_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    findings.extend(frontend_page_structure_findings())
    findings.extend(frontend_generated_page_findings())
    findings.extend(frontend_asset_size_findings())
    findings.extend(frontend_cross_root_findings())
    findings.extend(frontend_explanation_findings())
    findings.extend(frontend_payload_contract_findings())
    findings.extend(frontend_dead_css_findings())
    return findings


def frontend_page_structure_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    for page_name in PAGE_DIR_NAMES:
        page_dir = FRONTEND_ROOT / page_name
        if not page_dir.exists():
            add_finding(findings, "platform_v2/spot/dashboard", "missing_page_dir", page_name, "high")
            continue

        if not (page_dir / "index.html").exists():
            add_finding(findings, str(page_dir.relative_to(V2_ROOT.parent)), "missing_page_file", "index.html", "medium")

        has_page_builder = (page_dir / "page_builder.py").exists() or (page_dir / "py" / "page_builder.py").exists()
        if not has_page_builder:
            add_finding(findings, str(page_dir.relative_to(V2_ROOT.parent)), "missing_page_file", "page_builder.py", "medium")
    return findings


def frontend_generated_page_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    for page_name in PAGE_DIR_NAMES:
        html_path = FRONTEND_ROOT / page_name / "index.html"
        if not html_path.exists():
            continue
        text = html_path.read_text(encoding="utf-8")

        if "<title>" not in text:
            add_finding(findings, str(html_path.relative_to(V2_ROOT.parent)), "missing_html_title", "missing <title>", "medium")
        if 'meta name="description"' not in text:
            add_finding(findings, str(html_path.relative_to(V2_ROOT.parent)), "missing_meta_description", "missing meta description", "medium")
        if 'rel="icon"' not in text:
            add_finding(findings, str(html_path.relative_to(V2_ROOT.parent)), "missing_favicon_link", "missing favicon link", "low")
        if "<!-- ssh-generator:" not in text:
            add_finding(
                findings,
                str(html_path.relative_to(V2_ROOT.parent)),
                "generated_page_missing_marker",
                "missing ssh-generator marker",
                "low",
            )

        missing_nav = [href for href in REQUIRED_NAV_TARGETS if href not in text]
        if missing_nav:
            add_finding(
                findings,
                str(html_path.relative_to(V2_ROOT.parent)),
                "nav_link_drift",
                ", ".join(missing_nav),
                "medium",
            )
    return findings


def frontend_asset_size_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    for css_path in sorted(FRONTEND_ROOT.rglob("*.css")):
        line_count = css_path.read_text(encoding="utf-8").count("\n") + 1
        if line_count > 500:
            add_finding(
                findings,
                str(css_path.relative_to(V2_ROOT.parent)),
                "oversized_frontend_css",
                f"{line_count} lines",
                "medium",
            )

    for html_path in sorted(FRONTEND_ROOT.rglob("*.html")):
        line_count = html_path.read_text(encoding="utf-8").count("\n") + 1
        if line_count > 350:
            add_finding(
                findings,
                str(html_path.relative_to(V2_ROOT.parent)),
                "oversized_frontend_html",
                f"{line_count} lines",
                "low",
            )
    return findings


def frontend_cross_root_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    candidate_files = list(FRONTEND_ROOT.rglob("*.py")) + list(FRONTEND_ROOT.rglob("*.html")) + list(FRONTEND_ROOT.rglob("*.css"))

    for path in sorted(candidate_files):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_CROSS_ROOT_TOKENS:
            if token in text:
                add_finding(
                    findings,
                    str(path.relative_to(V2_ROOT.parent)),
                    "frontend_cross_root_reference",
                    token,
                    "high",
                )

        absolute_refs = re.findall(r"/home/sandro/SmartSignalHub/[^\s\"')]+", text)
        for ref in absolute_refs:
            if "/platform_v2/" not in ref:
                add_finding(
                    findings,
                    str(path.relative_to(V2_ROOT.parent)),
                    "frontend_absolute_external_reference",
                    ref,
                    "high",
                )
    return findings


def frontend_explanation_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    explanation_keys = load_explanation_keys()
    referenced_keys = referenced_explanation_keys()

    for key in sorted(referenced_keys):
        if key not in explanation_keys:
            add_finding(
                findings,
                "platform_v2/spot/dashboard/explanation_system/data/explanations.json",
                "missing_explanation_content",
                key,
                "high",
            )

    for key in sorted(explanation_keys):
        if key not in referenced_keys:
            add_finding(
                findings,
                "platform_v2/spot/dashboard/explanation_system/data/explanations.json",
                "orphan_explanation_entry",
                key,
                "low",
            )

    overview_html = FRONTEND_ROOT / "overview_spot" / "index.html"
    overview_text = overview_html.read_text(encoding="utf-8") if overview_html.exists() else ""
    for key in CRITICAL_OVERVIEW_EXPLANATION_KEYS:
        if key not in overview_text:
            add_finding(
                findings,
                str(overview_html.relative_to(V2_ROOT.parent)) if overview_html.exists() else "platform_v2/spot/dashboard/overview_spot/index.html",
                "missing_critical_explanation_anchor",
                key,
                "high",
            )

    return findings


def frontend_payload_contract_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    page_dirs = sorted(path for path in FRONTEND_ROOT.iterdir() if path.is_dir())
    for page_dir in page_dirs:
        builder_path = page_dir / "py" / "page_builder.py"
        renderer_path = page_dir / "py" / "renderer.py"
        if not builder_path.exists() or not renderer_path.exists():
            continue

        builder_keys = builder_payload_keys(builder_path)
        renderer_keys = renderer_payload_keys(renderer_path)
        if not builder_keys or not renderer_keys:
            continue

        missing = sorted(key for key in renderer_keys if key not in builder_keys)
        if missing:
            add_finding(
                findings,
                str(renderer_path.relative_to(V2_ROOT.parent)),
                "payload_key_drift",
                ", ".join(missing),
                "medium",
            )
    return findings


def frontend_dead_css_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    frontend_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(FRONTEND_ROOT.rglob("*"))
        if path.is_file() and path.suffix in {".py", ".html", ".js"}
    )

    simple_selector_pattern = re.compile(r"(?m)^([.#][a-zA-Z][\w\-]*)\s*\{")
    for css_path in sorted(FRONTEND_ROOT.rglob("*.css")):
        text = css_path.read_text(encoding="utf-8")
        selectors = {match.group(1) for match in simple_selector_pattern.finditer(text)}
        for selector in sorted(selectors):
            token = selector[1:]
            if token not in frontend_text:
                add_finding(
                    findings,
                    str(css_path.relative_to(V2_ROOT.parent)),
                    "dead_css_candidate",
                    selector,
                    "low",
                )
    return findings


def load_explanation_keys() -> set[str]:
    if not EXPLANATION_DATA_PATH.exists():
        return set()
    try:
        payload = json.loads(EXPLANATION_DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    if not isinstance(payload, dict):
        return set()
    return {str(key) for key in payload}


def referenced_explanation_keys() -> set[str]:
    keys: set[str] = set()
    candidate_files = list(FRONTEND_ROOT.rglob("*.py")) + list(FRONTEND_ROOT.rglob("*.html")) + list(FRONTEND_ROOT.rglob("*.js"))
    for path in sorted(candidate_files):
        text = path.read_text(encoding="utf-8")
        for match in EXPLANATION_KEY_PATTERN.finditer(text):
            key = match.group(1) or match.group(2)
            if key:
                keys.add(key)
    return keys


def builder_payload_keys(path: Path) -> set[str]:
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


def renderer_payload_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"""payload\[['"]([^'"]+)['"]\]|payload\.get\(\s*['"]([^'"]+)['"]""")
    keys: set[str] = set()
    for match in pattern.finditer(text):
        key = match.group(1) or match.group(2)
        if key:
            keys.add(key)
    return keys
