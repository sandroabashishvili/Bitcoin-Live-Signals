"""File: __init__.py
Folder: platform_v2/futures/services/analytics/futures_strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Export the Futures strategy effectiveness analytics package API.
"""

from .service import StrategyEffectivenessService
from .types import (
    ClosedTradeLogicEvaluationPayload,
    ClosedTradeLogicEvaluationRow,
    ClosedTradeLogicEvaluationTotals,
    ClosedTradeSummary,
    GateEffectivenessStat,
    LogicEvaluationPayload,
    LogicEvaluationRow,
    LogicEvaluationTotals,
    SignalActivitySummary,
)

__all__ = [
    "ClosedTradeLogicEvaluationPayload",
    "ClosedTradeLogicEvaluationRow",
    "ClosedTradeLogicEvaluationTotals",
    "ClosedTradeSummary",
    "GateEffectivenessStat",
    "LogicEvaluationPayload",
    "LogicEvaluationRow",
    "LogicEvaluationTotals",
    "SignalActivitySummary",
    "StrategyEffectivenessService",
]
