"""HTML hook diagnostics checks."""

from __future__ import annotations

import re

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


FRONTEND_ROOT = V2_ROOT / "spot" / "dashboard"
SHARED_FRONTEND_ROOT = V2_ROOT / "shared" / "frontend"
ID_PATTERN = re.compile(r'\bid=["\']([A-Za-z][\w\-:]*)["\']')
DATA_ATTR_PATTERN = re.compile(r'\b(data-[a-z0-9\-]+)=["\']', re.IGNORECASE)
SAFE_DATA_ATTRS = {
    "data-theme",
}


def unused_html_hook_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    non_html_text = build_non_html_frontend_text()

    for html_path in sorted(FRONTEND_ROOT.rglob("*.html")):
        text = html_path.read_text(encoding="utf-8")
        path_str = str(html_path.relative_to(V2_ROOT.parent))

        for hook_id in sorted(set(ID_PATTERN.findall(text))):
            if hook_id.startswith("explanation-drawer-"):
                continue
            if id_has_reference(hook_id, text, non_html_text):
                continue
            add_finding(findings, path_str, "unused_html_hook", f'id="{hook_id}"', "low")

        for attr_name in sorted(set(DATA_ATTR_PATTERN.findall(text))):
            lowered = attr_name.lower()
            if lowered in SAFE_DATA_ATTRS:
                continue
            if data_attr_has_reference(lowered, non_html_text):
                continue
            add_finding(findings, path_str, "unused_html_hook", lowered, "low")

    return findings


def build_non_html_frontend_text() -> str:
    chunks: list[str] = []
    for root in (FRONTEND_ROOT, SHARED_FRONTEND_ROOT):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".js", ".css"}:
                continue
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def id_has_reference(hook_id: str, html_text: str, non_html_text: str) -> bool:
    html_reference_patterns = (
        f'aria-labelledby="{hook_id}"',
        f"aria-labelledby='{hook_id}'",
        f'aria-describedby="{hook_id}"',
        f"aria-describedby='{hook_id}'",
        f'aria-controls="{hook_id}"',
        f"aria-controls='{hook_id}'",
        f'for="{hook_id}"',
        f"for='{hook_id}'",
        f'href="#{hook_id}"',
        f"href='#{hook_id}'",
    )
    if any(pattern in html_text for pattern in html_reference_patterns):
        return True

    non_html_reference_patterns = (
        f"#{hook_id}",
        f'getElementById("{hook_id}")',
        f"getElementById('{hook_id}')",
        hook_id,
    )
    return any(pattern in non_html_text for pattern in non_html_reference_patterns)


def data_attr_has_reference(attr_name: str, non_html_text: str) -> bool:
    reference_patterns = (
        attr_name,
        f"[{attr_name}]",
    )
    return any(pattern in non_html_text for pattern in reference_patterns)
