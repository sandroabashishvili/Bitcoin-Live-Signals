"""Optional model answer composer.

The deterministic assistant answer remains the source of truth. This adapter is
best-effort and only rewrites/explains the extracted answer; it must not add
facts.
"""

from __future__ import annotations

import subprocess


MODEL_TIMEOUT_SECONDS = 90


def compose_with_model(*, model: str | None, question: str, deterministic_answer: str) -> str:
    if not model:
        return deterministic_answer
    if deterministic_answer.startswith("Unsupported question yet."):
        if not question.strip().casefold().startswith("/general "):
            return deterministic_answer
        general_question = question.strip()[len("/general "):].strip()
        return _answer_general_with_model(model=model, question=general_question, fallback=deterministic_answer)
    provider, _, model_name = model.partition(":")
    if provider != "ollama" or not model_name:
        return deterministic_answer + f"\n\nModel composer skipped: unsupported model adapter '{model}'."
    prompt = (
        "You are formatting a SmartSignalHub assistant answer.\n"
        "Use only the deterministic facts below. Do not add facts, paths, numbers, or conclusions.\n"
        "Preserve every important number, status, reason, and source path from the deterministic facts.\n"
        "Do not remove Source lines. If a fact is uncertain or says no rows found, keep that limitation.\n"
        "Answer concisely in the user's language.\n\n"
        f"Question:\n{question}\n\n"
        f"Deterministic facts:\n{deterministic_answer}\n"
    )
    try:
        completed = subprocess.run(
            ["ollama", "run", model_name],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=MODEL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return deterministic_answer + f"\n\nModel composer unavailable: {type(exc).__name__}: {exc}"
    output = completed.stdout.strip()
    if completed.returncode != 0 or not output:
        detail = completed.stderr.strip() or f"exit_code={completed.returncode}"
        return deterministic_answer + f"\n\nModel composer failed: {detail}"
    return _append_missing_sources(output, deterministic_answer)


def _answer_general_with_model(*, model: str, question: str, fallback: str) -> str:
    provider, _, model_name = model.partition(":")
    if provider != "ollama" or not model_name:
        return fallback + f"\n\nGeneral model skipped: unsupported model adapter '{model}'."
    prompt = (
        "You are answering a general non-project question in a SmartSignalHub chat.\n"
        "Do not claim to have read SmartSignalHub files unless project facts are provided.\n"
        "Do not provide financial, legal, medical, or current-news certainty without sources.\n"
        "For historical/general knowledge, answer concisely and mention if dates or details may need verification.\n"
        "Answer in the user's language when clear.\n\n"
        f"Question:\n{question}\n"
    )
    try:
        completed = subprocess.run(
            ["ollama", "run", model_name],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=MODEL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return fallback + f"\n\nGeneral model unavailable: {type(exc).__name__}: {exc}"
    output = completed.stdout.strip()
    if completed.returncode != 0 or not output:
        detail = completed.stderr.strip() or f"exit_code={completed.returncode}"
        return fallback + f"\n\nGeneral model failed: {detail}"
    return output


def _append_missing_sources(output: str, deterministic_answer: str) -> str:
    source_lines = [line for line in deterministic_answer.splitlines() if line.startswith("Source: ")]
    if not source_lines:
        return output
    missing = [line for line in source_lines if line not in output]
    if not missing:
        return output
    return output.rstrip() + "\n\nVerified sources:\n" + "\n".join(missing)
