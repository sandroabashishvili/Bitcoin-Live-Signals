"""Assistant question-answer engine."""

from __future__ import annotations

from .answer_contract import apply_project_answer_contract
from .capabilities.router import dispatch
from .intents import detect_intent
from .model_adapter import compose_with_model


def answer_question(question: str, *, model: str | None = None) -> str:
    intent = detect_intent(question)
    deterministic_answer = apply_project_answer_contract(dispatch(intent))
    return compose_with_model(model=model, question=question, deterministic_answer=deterministic_answer)
