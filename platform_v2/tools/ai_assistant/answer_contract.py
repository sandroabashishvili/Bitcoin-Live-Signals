"""Project answer contract formatting."""

from __future__ import annotations

from .capabilities.contracts import CapabilityAnswer


SKIP_CAPABILITIES = {"general", "unsupported"}


def apply_project_answer_contract(answer: CapabilityAnswer) -> str:
    """Shape project answers without changing their facts.

    The contract makes browser/model answers easier to scan while preserving the
    original deterministic content and source paths.
    """

    text = answer.text.strip()
    if not text or answer.capability in SKIP_CAPABILITIES:
        return answer.text
    if text.startswith("Verdict\n") or text.startswith("Verdict:"):
        return answer.text

    lines = text.splitlines()
    source_lines = [line for line in lines if line.startswith("Source: ")]
    fact_lines = [line for line in lines if not line.startswith("Source: ")]
    verdict = _first_content_line(fact_lines)
    sources = _source_lines(answer, source_lines)

    sections = [
        "Verdict",
        verdict,
        "",
        "Facts",
        "\n".join(fact_lines).strip() or "--",
    ]
    if sources:
        sections.extend(["", "Sources", "\n".join(sources)])
    sections.extend(
        [
            "",
            "Limitations",
            "- Project facts come from deterministic local readers. If a ledger/report is missing, the answer must say so instead of guessing.",
        ]
    )
    return "\n".join(sections).strip()


def _first_content_line(lines: list[str]) -> str:
    for line in lines:
        clean = line.strip()
        if clean:
            return clean
    return "--"


def _source_lines(answer: CapabilityAnswer, source_lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in source_lines:
        if line not in merged:
            merged.append(line)
    for source in answer.sources:
        line = f"Source: {source}"
        if line not in merged:
            merged.append(line)
    return merged
