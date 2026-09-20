from __future__ import annotations

from pathlib import Path

from platform_v2.spot.domain.models.position import PositionRecord
from platform_v2.spot.dashboard.orderbook import OrderbookPageService
from platform_v2.spot.dashboard.overview_spot import OverviewPageService
from platform_v2.spot.dashboard.portfolio import PortfolioPageService
from platform_v2.spot.dashboard.trade_outcomes import TradeOutcomesPageService
from platform_v2.spot.dashboard.strategy_edge import StrategyEdgePageService
from platform_v2.spot.services.metrics_system import MetricsSummaryService
from platform_v2.spot.services.account.position_batch_update_service import PositionBatchUpdateService
from platform_v2.spot.services.analytics.indicator_builder_service import IndicatorBuilderService
from platform_v2.spot.services.market.binance_orderbook_service import BinanceOrderbookService
from platform_v2.spot.services.permission.signal_permission_runtime_service import (
    SignalPermissionRunResult,
    SignalPermissionRuntimeService,
)

from .models import CycleKeyInfo, MainCycleResult
from .notifications import MainCycleNotificationService


class MainCycleExecutionService:
    """Execute the ready-state main cycle body."""

    def __init__(
        self,
        orderbook_service: BinanceOrderbookService | None = None,
        indicator_builder_service: IndicatorBuilderService | None = None,
        signal_permission_runtime_service: SignalPermissionRuntimeService | None = None,
        position_batch_update_service: PositionBatchUpdateService | None = None,
        metrics_summary_service: MetricsSummaryService | None = None,
        overview_page_service: OverviewPageService | None = None,
        portfolio_page_service: PortfolioPageService | None = None,
        trade_outcomes_page_service: TradeOutcomesPageService | None = None,
        strategy_edge_page_service: StrategyEdgePageService | None = None,
        orderbook_page_service: OrderbookPageService | None = None,
        notification_service: MainCycleNotificationService | None = None,
    ) -> None:
        self._orderbook_service = orderbook_service or BinanceOrderbookService()
        self._indicator_builder_service = indicator_builder_service or IndicatorBuilderService()
        self._signal_permission_runtime_service = (
            signal_permission_runtime_service or SignalPermissionRuntimeService()
        )
        self._position_batch_update_service = (
            position_batch_update_service or PositionBatchUpdateService()
        )
        self._metrics_summary_service = metrics_summary_service or MetricsSummaryService()
        self._overview_page_service = overview_page_service or OverviewPageService()
        self._portfolio_page_service = portfolio_page_service or PortfolioPageService()
        self._trade_outcomes_page_service = trade_outcomes_page_service or TradeOutcomesPageService()
        self._strategy_edge_page_service = (
            strategy_edge_page_service or StrategyEdgePageService()
        )
        self._orderbook_page_service = orderbook_page_service or OrderbookPageService()
        self._notification_service = notification_service or MainCycleNotificationService(
            metrics_summary_service=self._metrics_summary_service,
        )

    def run_ready_cycle(
        self,
        *,
        symbol: str,
        timeframe: str,
        date_iso: str,
        position_size: float,
        starting_balance: float,
        fetched_candle_paths: tuple[Path, ...],
        cycle_info: CycleKeyInfo,
    ) -> MainCycleResult:
        fetched_orderbook_path = self._fetch_orderbook(symbol=symbol, timeframe=timeframe)
        built_indicator_paths = self._build_indicators(symbol=symbol)
        updated_positions = self._update_positions(date_iso=date_iso)
        signal_result = self._run_signal_pipeline(
            symbol=symbol,
            timeframe=timeframe,
            date_iso=date_iso,
            position_size=position_size,
            starting_balance=starting_balance,
        )
        try:
            self._notification_service.notify_position_closes(
                updated_positions,
                date_iso=date_iso,
                starting_balance=starting_balance,
            )
            self._notification_service.notify_buy_opened(
                signal_result,
                date_iso=date_iso,
                starting_balance=starting_balance,
            )
        except RuntimeError as exc:
            print(f"[WARN] Telegram notification failed: {exc}", flush=True)
        metrics_path = self._build_metrics(
            date_iso=date_iso,
            starting_balance=starting_balance,
        )
        self._refresh_pages(symbol=symbol, timeframe=timeframe)
        return MainCycleResult(
            cycle_key=cycle_info.key,
            cycle_state=cycle_info.state,
            cycle_note=cycle_info.note,
            skipped=False,
            skip_reason=None,
            fetched_candle_paths=fetched_candle_paths,
            fetched_orderbook_path=fetched_orderbook_path,
            built_indicator_paths=built_indicator_paths,
            signal_result=signal_result,
            updated_positions=updated_positions,
            metrics_path=metrics_path,
            daily_summary_path=None,
        )

    def _fetch_orderbook(self, *, symbol: str, timeframe: str) -> Path | None:
        return self._orderbook_service.fetch_and_store(
            symbol=symbol,
            timeframe=timeframe,
        )

    def _build_indicators(self, *, symbol: str) -> tuple[Path, ...]:
        return tuple(
            self._indicator_builder_service.build_many(
                symbol=symbol,
                timeframes=("5m", "15m", "4h"),
            )
        )

    def _run_signal_pipeline(
        self,
        *,
        symbol: str,
        timeframe: str,
        date_iso: str,
        position_size: float,
        starting_balance: float,
    ) -> SignalPermissionRunResult:
        return self._signal_permission_runtime_service.run_for_symbol(
            symbol=symbol,
            timeframe=timeframe,
            date_iso=date_iso,
            position_size=position_size,
            starting_balance=starting_balance,
        )

    def _update_positions(self, *, date_iso: str) -> tuple[PositionRecord, ...]:
        return tuple(self._position_batch_update_service.run(date_iso=date_iso))

    def _build_metrics(self, *, date_iso: str, starting_balance: float) -> Path | None:
        return self._metrics_summary_service.build_and_store(
            date_iso=date_iso,
            starting_balance=starting_balance,
        )

    def _refresh_pages(self, *, symbol: str, timeframe: str) -> None:
        self._overview_page_service.build_and_store(symbol=symbol)
        self._portfolio_page_service.build_and_store()
        self._trade_outcomes_page_service.build_and_store()
        self._strategy_edge_page_service.build_and_store()
        self._orderbook_page_service.build_and_store(symbol=symbol, timeframe=timeframe)
