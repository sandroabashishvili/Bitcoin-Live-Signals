"""Shared domain-neutral trading calculations and contracts."""

from .sl_tp import SlTpInputs, SlTpPayload, StopLossResult, TakeProfitResult
from .stop_loss import compute_stop_loss
from .take_profit import compute_take_profit

__all__ = [
    "SlTpInputs",
    "SlTpPayload",
    "StopLossResult",
    "TakeProfitResult",
    "compute_stop_loss",
    "compute_take_profit",
]
