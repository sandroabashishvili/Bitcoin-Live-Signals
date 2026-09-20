"""Futures metrics content system."""

from .grouped_payloads import (
    build_overview_portfolio_snapshot_items,
    build_overview_strategy_snapshot_items,
    build_overview_trade_outcomes_snapshot_items,
    build_portfolio_capital_snapshot_items,
    build_portfolio_trade_outcome_items,
    build_strategy_activity_evaluation_items,
)
from .orderbook_content import OrderbookPageContentService
from .portfolio_content import PortfolioPageContentService
from .strategy_content import StrategyPageContentService

__all__ = [
    "build_portfolio_capital_snapshot_items",
    "build_portfolio_trade_outcome_items",
    "build_overview_portfolio_snapshot_items",
    "build_overview_trade_outcomes_snapshot_items",
    "build_overview_strategy_snapshot_items",
    "build_strategy_activity_evaluation_items",
    "OrderbookPageContentService",
    "PortfolioPageContentService",
    "StrategyPageContentService",
]
