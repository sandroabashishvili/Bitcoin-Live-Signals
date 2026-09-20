"""Documentation search capability for active platform docs."""

from __future__ import annotations

from pathlib import Path

from platform_v2.tools.ai_assistant.runtime_readers import REPO_ROOT

from .contracts import CapabilityAnswer


DOCS_ROOT = REPO_ROOT / "platform_v2" / "docs"


def answer_docs_search(query: str) -> CapabilityAnswer:
    terms = _terms(query)
    matches: list[tuple[Path, int, str]] = []
    for path in sorted(DOCS_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for idx, line in enumerate(lines, start=1):
            lowered = line.casefold()
            if any(term in lowered for term in terms):
                matches.append((path, idx, line.strip()))
                break

    if not matches:
        text = "\n".join(
            [
                "Docs search",
                f"Query terms: {', '.join(terms) if terms else '--'}",
                "No active docs match found.",
                f"Docs root: {DOCS_ROOT}",
            ]
        )
        return CapabilityAnswer("docs_search", text, (str(DOCS_ROOT),))

    lines = [
        "Docs search",
        f"Query terms: {', '.join(terms)}",
        "First matching docs:",
    ]
    for path, lineno, line in matches[:8]:
        rel = path.relative_to(REPO_ROOT)
        lines.append(f"- {rel}:{lineno} - {line[:180]}")
    return CapabilityAnswer("docs_search", "\n".join(lines), tuple(str(path) for path, _, _ in matches[:8]))


def _terms(query: str) -> list[str]:
    text = query.casefold()
    mapped: list[str] = []
    if any(token in text for token in ("hard", "blocker", "ბლოკ", "ბლოკერ")):
        mapped.extend(["hard blocker", "blocker", "block"])
    if any(token in text for token in ("telegram", "ტელეგრამ")):
        mapped.extend(["telegram", "bot"])
    if any(token in text for token in ("backup", "reset", "ბექაფ", "რეზეტ")):
        mapped.extend(["backup", "reset"])
    if "mtf" in text or "მტფ" in text:
        mapped.extend(["mtf", "multi"])
    if any(token in text for token in ("risk", "რისკ", "permission")):
        mapped.extend(["risk", "permission"])
    if any(token in text for token in ("სიგნალ", "signal")):
        mapped.extend(["signal"])
    if any(token in text for token in ("სტოპ", "stop", "sl", "tp")):
        mapped.extend(["stop", "sl", "tp"])
    if not mapped:
        mapped.extend(token for token in text.replace("?", " ").split() if len(token) >= 3)
    return list(dict.fromkeys(mapped))
