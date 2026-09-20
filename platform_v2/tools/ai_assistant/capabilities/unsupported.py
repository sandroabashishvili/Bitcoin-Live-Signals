"""Unsupported-question safety response."""

from __future__ import annotations

from .contracts import CapabilityAnswer


def answer_unsupported(question: str) -> CapabilityAnswer:
    text = "\n".join(
        [
            "Unsupported question yet.",
            "No deterministic capability is implemented for this request.",
            "The assistant did not return a fallback signal/position answer because that would be misleading.",
            f"Question: {question}",
        ]
    )
    return CapabilityAnswer("unsupported", text)
