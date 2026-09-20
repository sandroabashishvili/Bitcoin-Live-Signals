"""Payload contract and stale-payload diagnostics."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


FRONTEND_ROOT = V2_ROOT / "spot" / "dashboard"
PAYLOAD_KEY_PATTERN = re.compile(r"""payload\[['"]([^'"]+)['"]\]|payload\.get\(\s*['"]([^'"]+)['"]""")
WINDOW_KEY_PATTERN = re.compile(r"""__SSH_[A-Z0-9_]+""")


def frontend_payload_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    page_dirs = sorted(path for path in FRONTEND_ROOT.iterdir() if path.is_dir())
    for page_dir in page_dirs:
        builder_path = page_dir / "py" / "page_builder.py"
        renderer_path = page_dir / "py" / "renderer.py"
        if not builder_path.exists() or not renderer_path.exists():
            continue

        builder_keys = builder_payload_keys(builder_path)
        renderer_keys = renderer_payload_keys(renderer_path)
        if not builder_keys:
            continue

        # payload_key_drift is emitted by frontend_checks.frontend_payload_contract_findings;
        # keep this check focused on stale payload detection to avoid duplicate findings.
        _ = renderer_keys

        consumer_text = page_consumer_text(page_dir)
        stale = sorted(key for key in builder_keys if not payload_key_has_consumer(key, consumer_text))
        for key in stale:
            add_finding(
                findings,
                str(builder_path.relative_to(V2_ROOT.parent)),
                "stale_payload_candidate",
                key,
                "low",
            )

    return findings


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
    keys: set[str] = set()
    for match in PAYLOAD_KEY_PATTERN.finditer(text):
        key = match.group(1) or match.group(2)
        if key:
            keys.add(key)
    return keys


def related_page_js_text(page_dir: Path) -> str:
    texts: list[str] = []
    for js_path in sorted((page_dir.parent / "charts").glob("*.js")):
        text = js_path.read_text(encoding="utf-8")
        if any(token in text for token in window_tokens_for_page(page_dir.name)):
            texts.append(text)
    return "\n".join(texts)


def page_consumer_text(page_dir: Path) -> str:
    chunks: list[str] = []

    py_dir = page_dir / "py"
    if py_dir.exists():
        for path in sorted(py_dir.rglob("*.py")):
            chunks.append(path.read_text(encoding="utf-8"))

    html_path = page_dir / "index.html"
    if html_path.exists():
        chunks.append(html_path.read_text(encoding="utf-8"))

    related_js = related_page_js_text(page_dir)
    if related_js:
        chunks.append(related_js)

    return "\n".join(chunks)


def window_tokens_for_page(page_name: str) -> tuple[str, ...]:
    mapping = {
        "overview_spot": ("__SSH_OVERVIEW_",),
        "portfolio": ("__SSH_PORTFOLIO_",),
        "strategy": ("__SSH_STRATEGY_",),
        "strategy_edge": ("__SSH_STRATEGY_",),
        "orderbook": ("__SSH_ORDERBOOK_",),
        "how_it_works": ("__SSH_HOW_IT_WORKS_",),
        "resources": ("__SSH_RESOURCES_",),
    }
    return mapping.get(page_name, tuple())


def payload_key_has_consumer(key: str, consumer_text: str) -> bool:
    direct_patterns = (
        f"payload['{key}']",
        f'payload["{key}"]',
        f"payload.get('{key}'",
        f'payload.get("{key}"',
        key,
    )
    return any(pattern in consumer_text for pattern in direct_patterns)
