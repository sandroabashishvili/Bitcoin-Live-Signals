"""File: signal_permission_runtime_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Orchestrate signal building, permission evaluation, and denied-entry persistence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.execution import (
    DeniedEntryRecord,
    PermissionDecision,
    PermissionStatus,
)
from platform_v2.spot.domain.models.market_context import MarketContext
from platform_v2.spot.domain.models.order import OrderResult
from platform_v2.spot.domain.models.position import PositionRecord
from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide
from platform_v2.spot.services.account.position_state_service import PositionStateService
from platform_v2.spot.services.permission.denied_entry_runtime_service import DeniedEntryRuntimeService
from platform_v2.spot.services.permission.permission_decision_service import PermissionDecisionService
from platform_v2.spot.services.trading.order_execution_service import OrderExecutionService
from platform_v2.spot.services.account.portfolio_state_service import PortfolioStateService
from platform_v2.spot.services.account.position_runtime_service import PositionRuntimeService
from platform_v2.spot.services.analytics.entry_location_classifier import SpotEntryLocationClassifier
from platform_v2.spot.services.ops.runtime_write_service import write_order_record
from platform_v2.spot.services.signal.signal_runtime_service import SignalRuntimeService
from platform_v2.spot.services.ops.runtime_write_service import write_signal_record
from platform_v2.shared.backend.market import BinanceQuoteService, MarketQuote
from platform_v2.shared.backend.time import utc_now_ms
from platform_v2.shared.runtime_warnings import warn_runtime_fallback


@dataclass(frozen=True)
class SignalPermissionRunResult:
    """Normalized result bundle for the signal-permission runtime flow."""

    signal: SignalDecision | None
    permission: PermissionDecision | None
    denied_entry: DeniedEntryRecord | None = None
    order_result: OrderResult | None = None
    position: PositionRecord | None = None


@dataclass(frozen=True)
class _SignalContextBundle:
    no_signal: bool
    signal: SignalDecision
    market_context: MarketContext


@dataclass(frozen=True)
class _PortfolioInputs:
    available_balance: float
    current_open_exposure: float
    open_positions_count: int
    last_entry_price: float | None


@dataclass(frozen=True)
class _DerivedPermissionFlags:
    cooldown_active: bool = False
    duplicate_active: bool = False
    weak_open_position_active: bool = False


class SignalPermissionRuntimeService:
    """Run the current minimal signal and permission pipeline."""

    def __init__(
        self,
        signal_runtime_service: SignalRuntimeService | None = None,
        permission_decision_service: PermissionDecisionService | None = None,
        denied_entry_runtime_service: DeniedEntryRuntimeService | None = None,
        order_execution_service: OrderExecutionService | None = None,
        position_runtime_service: PositionRuntimeService | None = None,
        portfolio_state_service: PortfolioStateService | None = None,
        position_state_service: PositionStateService | None = None,
        quote_service: BinanceQuoteService | None = None,
    ) -> None:
        """Initialize runtime dependencies for signal and permission flow."""

        self._signal_runtime_service = signal_runtime_service or SignalRuntimeService()
        self._permission_decision_service = permission_decision_service or PermissionDecisionService()
        self._denied_entry_runtime_service = (
            denied_entry_runtime_service or DeniedEntryRuntimeService()
        )
        self._order_execution_service = order_execution_service or OrderExecutionService()
        self._position_runtime_service = position_runtime_service or PositionRuntimeService()
        self._portfolio_state_service = portfolio_state_service or PortfolioStateService()
        self._position_state_service = position_state_service or PositionStateService()
        self._quote_service = quote_service or BinanceQuoteService()

    def run_for_symbol(
        self,
        *,
        symbol: str,
        timeframe: str,
        date_iso: str,
        live_entry_price: float | None = None,
        candle_limit: int = settings.DEFAULT_CANDLE_LIMIT,
        position_size: float = settings.DEFAULT_POSITION_SIZE,
        available_balance: float | None = None,
        current_open_exposure: float | None = None,
        open_positions_count: int | None = None,
        last_entry_price: float | None = None,
        starting_balance: float = settings.DEFAULT_STARTING_BALANCE,
        manual_block: bool = False,
        cooldown_active: bool = False,
        duplicate_active: bool = False,
        weak_open_position_active: bool = False,
        proximity_pct: float | None = None,
        timestamp_text: str | None = None,
    ) -> SignalPermissionRunResult:
        """Run signal and permission flow and persist denied entries when needed."""

        signal_bundle = self._load_signal_bundle(
            symbol=symbol,
            timeframe=timeframe,
            date_iso=date_iso,
            candle_limit=candle_limit,
        )
        if signal_bundle is None:
            return self._empty_result()
        cycle_decision_time = timestamp_text or self._format_signal_timestamp(utc_now_ms())
        enriched_signal = replace(
            signal_bundle.signal,
            candle_close_time=self._format_signal_timestamp(signal_bundle.signal.timestamp_ms),
            decision_time=cycle_decision_time,
        )
        signal_bundle = replace(signal_bundle, signal=enriched_signal)
        write_signal_record(date_iso=date_iso, signal=enriched_signal)
        if signal_bundle.no_signal:
            return self._no_signal_result(signal=signal_bundle.signal)

        return self._run_for_signal_bundle(
            signal_bundle=signal_bundle,
            date_iso=date_iso,
            live_entry_price=live_entry_price,
            position_size=position_size,
            available_balance=available_balance,
            current_open_exposure=current_open_exposure,
            open_positions_count=open_positions_count,
            last_entry_price=last_entry_price,
            starting_balance=starting_balance,
            manual_block=manual_block,
            cooldown_active=cooldown_active,
            duplicate_active=duplicate_active,
            weak_open_position_active=weak_open_position_active,
            proximity_pct=proximity_pct,
            timestamp_text=cycle_decision_time,
        )

    def _run_for_signal_bundle(
        self,
        *,
        signal_bundle: _SignalContextBundle,
        date_iso: str,
        live_entry_price: float | None,
        position_size: float,
        available_balance: float | None,
        current_open_exposure: float | None,
        open_positions_count: int | None,
        last_entry_price: float | None,
        starting_balance: float,
        manual_block: bool,
        cooldown_active: bool,
        duplicate_active: bool,
        weak_open_position_active: bool,
        proximity_pct: float | None,
        timestamp_text: str | None,
    ) -> SignalPermissionRunResult:
        signal = signal_bundle.signal
        market_context = signal_bundle.market_context
        quote, quote_error = self._resolve_execution_quote(
            symbol=signal.symbol,
            supplied_price=live_entry_price,
        )
        signal = replace(
            signal,
            execution_quote_price=quote.price if quote is not None else None,
            execution_quote_time_ms=quote.observed_at_ms if quote is not None else None,
            execution_quote_source=quote.source if quote is not None else None,
        )
        write_signal_record(date_iso=date_iso, signal=signal)
        resolved_live_entry_price = quote.price if quote is not None else signal.snapshot_price
        resolved_timestamp_text = timestamp_text or self._format_signal_timestamp(
            quote.observed_at_ms if quote is not None else signal.timestamp_ms
        )
        portfolio_inputs = self._resolve_portfolio_inputs(
            starting_balance=starting_balance,
            date_iso=date_iso,
            available_balance=available_balance,
            current_open_exposure=current_open_exposure,
            open_positions_count=open_positions_count,
            last_entry_price=last_entry_price,
        )
        derived_flags = self._derive_permission_flags(
            date_iso=date_iso,
            signal=signal,
            live_entry_price=resolved_live_entry_price,
            decision_timestamp_ms=(
                quote.observed_at_ms if quote is not None else signal.timestamp_ms
            ),
        )
        permission = self._evaluate_permission(
            signal,
            market_context=market_context,
            portfolio_inputs=portfolio_inputs,
            live_entry_price=resolved_live_entry_price,
            manual_block=manual_block,
            cooldown_active=cooldown_active or derived_flags.cooldown_active,
            duplicate_active=duplicate_active or derived_flags.duplicate_active,
            weak_open_position_active=(
                weak_open_position_active or derived_flags.weak_open_position_active
            ),
            proximity_pct=proximity_pct,
            timestamp_text=resolved_timestamp_text,
        )
        if quote_error is not None:
            permission = PermissionDecision(
                status=PermissionStatus.DENIED,
                reason="execution_quote_unavailable",
                checks=replace(permission.checks, execution_quote=False),
                context=permission.context,
            )

        if signal.entry_quality.get('allowed') is False:
            permission = replace(permission, checks=replace(permission.checks, entry_quality=False))
            if permission.is_allowed:
                permission = PermissionDecision(
                    status=PermissionStatus.DENIED,
                    reason=signal.entry_quality.get('reason', 'entry_quality_block'),
                    checks=permission.checks, context=permission.context,
                )

        order_result, position = self._handle_allowed_path(
            permission=permission,
            date_iso=date_iso,
            signal=signal,
            live_entry_price=resolved_live_entry_price,
            market_context=market_context,
            position_size=position_size,
            timestamp_text=resolved_timestamp_text,
            execution_quote=quote,
        )

        denied_entry = self._denied_entry_runtime_service.build_and_persist(
            date_iso=date_iso,
            signal=signal,
            permission=permission,
            live_entry_price=resolved_live_entry_price,
        )

        return SignalPermissionRunResult(
            signal=signal,
            permission=permission,
            denied_entry=denied_entry,
            order_result=order_result,
            position=position,
        )

    def _resolve_execution_quote(
        self,
        *,
        symbol: str,
        supplied_price: float | None,
    ) -> tuple[MarketQuote | None, str | None]:
        if supplied_price is not None:
            return MarketQuote(
                symbol=symbol,
                market_type="spot",
                price=float(supplied_price),
                observed_at_ms=int(datetime.now(tz=UTC).timestamp() * 1000),
                source="supplied_execution_price",
            ), None
        try:
            return self._quote_service.fetch(symbol=symbol, market_type="spot"), None
        except Exception as exc:
            warn_runtime_fallback(
                scope="signal_permission_runtime_service",
                operation="fetch_execution_quote",
                error=exc,
                fallback="deny_new_entry",
                extra={"symbol": symbol},
            )
            return None, str(exc)

    def _load_signal_bundle(
        self,
        *,
        symbol: str,
        timeframe: str,
        date_iso: str,
        candle_limit: int,
    ) -> _SignalContextBundle | None:
        signal_runtime_result = self._signal_runtime_service.run_with_context(
            symbol=symbol,
            timeframe=timeframe,
            date_iso=date_iso,
            candle_limit=candle_limit,
        )
        if signal_runtime_result is None:
            return None
        return _SignalContextBundle(
            no_signal=signal_runtime_result.signal.side == SignalSide.NO_SIGNAL,
            signal=signal_runtime_result.signal,
            market_context=signal_runtime_result.context,
        )

    @staticmethod
    def _empty_result() -> SignalPermissionRunResult:
        return SignalPermissionRunResult(
            signal=None,
            permission=None,
            denied_entry=None,
            order_result=None,
            position=None,
        )

    @staticmethod
    def _no_signal_result(*, signal: SignalDecision) -> SignalPermissionRunResult:
        return SignalPermissionRunResult(
            signal=signal,
            permission=None,
            denied_entry=None,
            order_result=None,
            position=None,
        )

    def _resolve_portfolio_inputs(
        self,
        *,
        starting_balance: float,
        date_iso: str,
        available_balance: float | None,
        current_open_exposure: float | None,
        open_positions_count: int | None,
        last_entry_price: float | None,
    ) -> _PortfolioInputs:
        portfolio_state = self._portfolio_state_service.build_state(
            starting_balance=starting_balance,
            as_of_date_iso=date_iso,
        )
        resolved_available_balance = (
            portfolio_state.available_balance if available_balance is None else available_balance
        )
        resolved_open_exposure = (
            portfolio_state.current_open_exposure
            if current_open_exposure is None
            else current_open_exposure
        )
        resolved_open_positions = (
            portfolio_state.open_positions_count
            if open_positions_count is None
            else open_positions_count
        )
        resolved_last_entry = portfolio_state.last_entry_price if last_entry_price is None else last_entry_price
        return _PortfolioInputs(
            available_balance=resolved_available_balance,
            current_open_exposure=resolved_open_exposure,
            open_positions_count=resolved_open_positions,
            last_entry_price=resolved_last_entry,
        )

    def _derive_permission_flags(
        self,
        *,
        date_iso: str,
        signal: SignalDecision,
        live_entry_price: float,
        decision_timestamp_ms: int,
    ) -> _DerivedPermissionFlags:
        open_positions = self._position_state_service.load_open_positions(
            as_of_date_iso=date_iso,
        )
        latest_opened_at_ms = max(
            (
                parsed_ms
                for parsed_ms in (
                    position.opened_at_ms if position.opened_at_ms is not None else
                    self._parse_position_opened_at_ms(position.opened_at) for position in open_positions
                )
                if parsed_ms is not None
            ),
            default=None,
        )
        cooldown_active = (
            latest_opened_at_ms is not None
            and decision_timestamp_ms
            < (latest_opened_at_ms + settings.DEFAULT_COOLDOWN_SECONDS * 1000)
        )
        duplicate_active = any(
            abs(position.execution.entry_price - live_entry_price) < 0.0001
            for position in open_positions
        )
        weak_open_position_active = settings.WEAK_OPEN_POSITION_BLOCK_ENABLED and any(
            self._position_unrealized_pct(position) <= settings.WEAK_OPEN_POSITION_PCT
            for position in open_positions
        )
        return _DerivedPermissionFlags(
            cooldown_active=cooldown_active,
            duplicate_active=duplicate_active,
            weak_open_position_active=weak_open_position_active,
        )

    @staticmethod
    def _position_unrealized_pct(position: PositionRecord) -> float:
        notional = position.execution.position_size
        unrealized = float(position.unrealized_pnl or 0.0)
        if notional <= 0:
            return 0.0
        return unrealized / notional

    @staticmethod
    def _parse_position_opened_at_ms(value: str | None) -> int | None:
        if not value:
            return None
        text = str(value).strip()
        if text.isdigit():
            return int(text)
        try:
            parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return None
        return int(parsed.timestamp() * 1000) + 999

    @staticmethod
    def _format_signal_timestamp(timestamp_ms: int) -> str:
        return datetime.fromtimestamp(timestamp_ms / 1000, UTC).strftime("%Y-%m-%d %H:%M:%S")

    def _evaluate_permission(
        self,
        signal: SignalDecision,
        *,
        market_context: MarketContext,
        portfolio_inputs: _PortfolioInputs,
        live_entry_price: float,
        manual_block: bool,
        cooldown_active: bool,
        duplicate_active: bool,
        weak_open_position_active: bool,
        proximity_pct: float | None,
        timestamp_text: str | None,
    ) -> PermissionDecision:
        buy_entry_location_ok = self._buy_entry_location_ok(
            signal=signal,
            market_context=market_context,
            live_entry_price=live_entry_price,
        )
        return self._permission_decision_service.evaluate(
            signal,
            live_entry_price=live_entry_price,
            available_balance=portfolio_inputs.available_balance,
            current_open_exposure=portfolio_inputs.current_open_exposure,
            open_positions_count=portfolio_inputs.open_positions_count,
            last_entry_price=portfolio_inputs.last_entry_price,
            manual_block=manual_block,
            cooldown_active=cooldown_active,
            duplicate_active=duplicate_active,
            weak_open_position_active=weak_open_position_active,
            buy_entry_location_ok=buy_entry_location_ok,
            proximity_pct=proximity_pct,
            timestamp_text=timestamp_text,
        )

    @staticmethod
    def _buy_entry_location_ok(
        *,
        signal: SignalDecision,
        market_context: MarketContext,
        live_entry_price: float,
    ) -> bool:
        if signal.side != SignalSide.BUY:
            return True

        snapshot = asdict(market_context.latest_snapshot)
        location = SpotEntryLocationClassifier.classify(
            entry_price=live_entry_price,
            snapshot=snapshot,
        )
        location_type = str(location.get("type") or "").upper()
        if location_type not in {value.upper() for value in settings.BUY_ENTRY_BLOCKED_LOCATIONS}:
            return True
        return False

    def _handle_allowed_path(
        self,
        *,
        permission: PermissionDecision,
        date_iso: str,
        signal: SignalDecision,
        live_entry_price: float,
        market_context: MarketContext,
        position_size: float,
        timestamp_text: str | None,
        execution_quote: MarketQuote | None,
    ) -> tuple[OrderResult | None, PositionRecord | None]:
        if not permission.is_allowed:
            return None, None

        order_result = self._order_execution_service.execute_market_order(
            signal=signal,
            quantity=position_size,
            entry_price=live_entry_price,
            dry_run=True,
        )
        write_order_record(date_iso=date_iso, order_result=order_result)
        position = self._position_runtime_service.build_and_persist(
            date_iso=date_iso,
            signal=signal,
            live_entry_price=order_result.fill.fill_price if order_result.fill else live_entry_price,
            market_context=market_context,
            position_size=position_size,
            opened_at=self._format_signal_timestamp(
                order_result.fill.filled_at_ms if order_result.fill else signal.timestamp_ms
            ),
            opened_at_ms=(order_result.fill.filled_at_ms if order_result.fill else None),
            signal_candle_close_time=self._format_signal_timestamp(signal.timestamp_ms),
            decision_time=timestamp_text,
            signal_reference_price=signal.snapshot_price,
            execution_quote_source=(
                execution_quote.source if execution_quote is not None else None
            ),
        )
        return order_result, position
