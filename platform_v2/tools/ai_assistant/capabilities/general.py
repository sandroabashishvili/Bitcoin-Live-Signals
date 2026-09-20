"""General assistant identity and greeting answers."""

from __future__ import annotations

from .contracts import CapabilityAnswer


def answer_greeting() -> CapabilityAnswer:
    return CapabilityAnswer(
        "general",
        "\n".join(
            [
                "გამარჯობა.",
                "მე ვარ SmartSignalHub Assistant. შემიძლია წავიკითხო პროექტის runtime, signals, positions, metrics, diagnostics, tools, docs და artifacts.",
                "თუ server გაშვებულია `--model ollama:...` პარამეტრით, მოდელი მხოლოდ პასუხის ტექსტს ალაგებს; ფაქტებს მაინც Python readers იღებს.",
            ]
        ),
    )


def answer_identity() -> CapabilityAnswer:
    return CapabilityAnswer(
        "general",
        "\n".join(
            [
                "I am the SmartSignalHub Assistant running inside this project.",
                "My job is to answer from real SmartSignalHub files and runtime ledgers.",
                "I do not know personal identity details unless they are provided in the current conversation or project context.",
                "When Ollama/Qwen is enabled, it is only an answer composer. Python remains the source of truth for project facts.",
            ]
        ),
    )
