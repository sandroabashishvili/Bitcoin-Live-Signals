"""Code-location and focused logic explanation capability."""

from __future__ import annotations

from dataclasses import dataclass

from platform_v2.tools.ai_assistant.intents import AssistantIntent

from .contracts import CapabilityAnswer


@dataclass(frozen=True)
class LogicTopic:
    title: str
    summary: tuple[str, ...]
    paths: tuple[str, ...]


SIGNAL_LOGIC_PATHS = (
    "platform_v2/futures/services/signal/futures_signal_decision_service.py",
    "platform_v2/futures/services/signal/futures_component_score_service.py",
    "platform_v2/futures/services/signal/futures_mtf_context_service.py",
    "platform_v2/spot/services/signal/signal_decision_service.py",
    "platform_v2/spot/services/signal/mtf_context_service.py",
)

RISK_PATHS = (
    "platform_v2/futures/services/permission/futures_permission_decision_service.py",
    "platform_v2/futures/services/simulation/entry_quality_service.py",
    "platform_v2/futures/services/simulation/position_service.py",
    "platform_v2/futures/services/simulation/position_lifecycle_service.py",
    "platform_v2/futures/services/trading/futures_sl_tp_service.py",
    "platform_v2/futures/domain/models/stop_loss.py",
    "platform_v2/futures/domain/models/take_profit.py",
    "platform_v2/spot/services/permission/permission_decision_service.py",
    "platform_v2/spot/services/trading/sl_tp_service.py",
    "platform_v2/spot/domain/models/execution.py",
)

FUTURES_PERMISSION_PATHS = (
    "platform_v2/futures/services/permission/futures_permission_decision_service.py",
    "platform_v2/futures/services/simulation/entry_permission_context_service.py",
    "platform_v2/futures/services/simulation/permission_text.py",
    "platform_v2/futures/services/simulation/entry_event_writer_service.py",
    "platform_v2/futures/services/simulation/directional_futures_simulation_service.py",
    "platform_v2/docs/trading/risk_and_permissions.md",
)

TOPICS: dict[str, LogicTopic] = {
    "mtf": LogicTopic(
        title="MTF gate logic",
        summary=(
            "Futures and Spot both resolve 5m, 15m, and 4h context before scoring.",
            "The primary timeframe must agree before a signal becomes actionable.",
            "Futures supports LONG/SHORT; Spot supports BUY/NO_SIGNAL.",
        ),
        paths=(
            "platform_v2/futures/services/signal/futures_mtf_context_service.py",
            "platform_v2/futures/services/signal/futures_signal_decision_service.py",
            "platform_v2/spot/services/signal/mtf_context_service.py",
            "platform_v2/spot/services/signal/signal_decision_service.py",
        ),
    ),
    "proximity": LogicTopic(
        title="proximity_block logic",
        summary=(
            "Proximity compares the candidate entry price to the last same-direction entry price.",
            "If distance percentage is not greater than the configured proximity threshold, entry is denied.",
            "Futures applies this in permission after signal selection; it does not change the signal score.",
        ),
        paths=(
            "platform_v2/futures/services/permission/futures_permission_decision_service.py",
            "platform_v2/spot/services/permission/permission_decision_service.py",
        ),
    ),
    "entry_quality": LogicTopic(
        title="entry_quality_block logic",
        summary=(
            "Futures entry quality classifies timing such as FRESH_FLIP, EARLY_CONTINUATION, and LATE_EXTENSION.",
            "Late or exhausted timing can block entry unless an explicit continuation override allows it.",
            "This is a permission layer, not a gate-score formula.",
        ),
        paths=(
            "platform_v2/futures/services/simulation/entry_quality_service.py",
            "platform_v2/futures/services/simulation/entry_permission_context_service.py",
            "platform_v2/futures/services/analytics/trade_audit/entry_timing_classifier.py",
        ),
    ),
    "sl_tp": LogicTopic(
        title="SL/TP logic",
        summary=(
            "Spot and Futures use adaptive_v2 SL/TP payloads when ATR exists.",
            "Stop loss uses structure priority: swing, kijun, ema50, then ATR fallback.",
            "Take profit starts from risk-based R:R and can clamp to resistance, liquidity, or psychological levels.",
        ),
        paths=(
            "platform_v2/futures/services/trading/futures_sl_tp_service.py",
            "platform_v2/futures/domain/models/stop_loss.py",
            "platform_v2/futures/domain/models/take_profit.py",
            "platform_v2/spot/services/trading/sl_tp_service.py",
            "platform_v2/spot/domain/models/stop_loss.py",
            "platform_v2/spot/domain/models/take_profit.py",
        ),
    ),
}


def answer_code_search(intent: AssistantIntent) -> CapabilityAnswer:
    if intent.topic == "permission_files":
        return answer_futures_permission_files(paths_only="paths only" in intent.question.casefold())
    topic_key = _topic_key(intent.topic)
    if topic_key:
        return _answer_topic(TOPICS[topic_key])
    if intent.topic == "risk_logic":
        return answer_risk_logic()
    return answer_signal_logic()


def answer_futures_permission_files(*, paths_only: bool = False) -> CapabilityAnswer:
    if paths_only:
        return CapabilityAnswer("code_search", "\n".join(FUTURES_PERMISSION_PATHS), FUTURES_PERMISSION_PATHS)
    lines = [
        "Futures permission files",
        *[f"- {path}" for path in FUTURES_PERMISSION_PATHS],
    ]
    return CapabilityAnswer("code_search", "\n".join(lines), FUTURES_PERMISSION_PATHS)


def answer_signal_logic() -> CapabilityAnswer:
    lines = [
        "Signal logic source map",
        "Core flow: market context -> component scores -> gates -> weighted score -> primary timeframe actionability.",
        "Main source areas:",
        *[f"- {path}" for path in SIGNAL_LOGIC_PATHS],
        "Ask a focused question such as: MTF gate როგორ მუშაობს?",
    ]
    return CapabilityAnswer("code_search", "\n".join(lines), SIGNAL_LOGIC_PATHS)


def answer_risk_logic() -> CapabilityAnswer:
    lines = [
        "Risk and permission source map",
        "Core flow: selected signal -> permission checks -> execution setup -> lifecycle updates.",
        "Main source areas:",
        *[f"- {path}" for path in RISK_PATHS],
        "Ask a focused question such as: proximity_block სად წყდება?",
    ]
    return CapabilityAnswer("code_search", "\n".join(lines), RISK_PATHS)


def _answer_topic(topic: LogicTopic) -> CapabilityAnswer:
    lines = [
        topic.title,
        *[f"- {line}" for line in topic.summary],
        "Source files:",
        *[f"- {path}" for path in topic.paths],
    ]
    return CapabilityAnswer("code_search", "\n".join(lines), topic.paths)


def _topic_key(topic: str) -> str | None:
    if topic in TOPICS:
        return topic
    return None
