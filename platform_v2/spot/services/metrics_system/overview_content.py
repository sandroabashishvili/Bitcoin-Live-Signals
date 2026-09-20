"""Backend-prepared content builders for the Overview page."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from platform_v2.spot.config import settings
from platform_v2.spot.services.analytics.strategy_effectiveness import StrategyEffectivenessService
from platform_v2.spot.services.account.position_state_service import PositionStateService

from .grouped_payloads import build_strategy_activity_evaluation_items


class OverviewPageContentService:
    """Build backend-owned content payloads for Overview page sections."""

    def __init__(
        self,
        position_state_service: PositionStateService | None = None,
        strategy_effectiveness_service: StrategyEffectivenessService | None = None,
    ) -> None:
        self._position_state_service = position_state_service or PositionStateService()
        self._strategy_effectiveness_service = strategy_effectiveness_service or StrategyEffectivenessService()

    def build_content(
        self,
        *,
        latest_signal: dict[str, Any] | None,
        signals: list[dict[str, Any]],
        denied_entries: list[dict[str, Any]],
        metrics: dict[str, Any],
        timeframe_snapshots: list[dict[str, Any] | None],
        symbol: str,
        candles_health: str,
        indicators_health: str,
        orderbook_health: str,
    ) -> dict[str, Any]:
        strategy_snapshot = self._build_strategy_snapshot(signals=signals)
        return {
            "equity_chart_rows": self._build_capital_curve(metrics=metrics),
            "strategy_snapshot_items": build_strategy_activity_evaluation_items(strategy_snapshot),
            "timeframe_context_cards": self._build_timeframe_context_cards(
                latest_signal=latest_signal,
                timeframe_snapshots=timeframe_snapshots,
            ),
            "runtime_health": {
                "symbol": symbol,
                "candles": candles_health,
                "indicators": indicators_health,
                "orderbook": orderbook_health,
            },
        }

    def _build_capital_curve(self, *, metrics: dict[str, Any]) -> list[dict[str, Any]]:
        positions = self._position_state_service.load_latest_positions()
        closed_positions = [position for position in positions if position.is_closed]
        starting_capital = float(settings.DEFAULT_STARTING_BALANCE)
        if not closed_positions:
            now = datetime.now(tz=UTC)
            equity_value = metrics.get("equity", starting_capital)
            try:
                equity = float(equity_value)
            except (TypeError, ValueError):
                equity = starting_capital
            return [
                {
                    "date": now.date().isoformat(),
                    "datetime": now.isoformat(),
                    "starting_capital": starting_capital,
                    "equity": round(equity, 2),
                    "last_capital": round(equity, 2),
                }
            ]

        equity = starting_capital
        curve: list[dict[str, Any]] = []
        ordered = sorted(
            closed_positions,
            key=lambda position: self._position_sort_key(position.closed_at or position.opened_at),
        )
        for position in ordered:
            equity += self._position_net_pnl(position)
            close_value = position.closed_at or position.opened_at or ""
            curve.append(
                {
                    "date": self._curve_date_text(close_value),
                    "datetime": self._curve_datetime_text(close_value),
                    "starting_capital": starting_capital,
                    "equity": round(equity, 2),
                    "last_capital": round(equity, 2),
                }
            )
        return curve

    @staticmethod
    def _position_sort_key(value: str | None) -> tuple[int, str]:
        text = str(value or "").strip()
        if not text:
            return (0, "")
        if text.isdigit():
            return (int(text), text)
        try:
            parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
            return (int(parsed.timestamp() * 1000), text)
        except ValueError:
            return (0, text)

    @staticmethod
    def _curve_datetime_text(value: str | None) -> str:
        text = str(value or "").strip()
        if text.isdigit():
            return datetime.fromtimestamp(int(text) / 1000, tz=UTC).isoformat()
        return text

    @classmethod
    def _curve_date_text(cls, value: str | None) -> str:
        datetime_text = cls._curve_datetime_text(value)
        if not datetime_text:
            return ""
        if "T" in datetime_text:
            return datetime_text[:10]
        return datetime_text[:10]

    @staticmethod
    def _position_net_pnl(position: Any) -> float:
        value = position.net_pnl if position.net_pnl is not None else position.pnl
        return float(value or 0.0)

    def _build_strategy_snapshot(self, *, signals: list[dict[str, Any]]) -> dict[str, Any]:
        return self._strategy_effectiveness_service.build_signal_activity_summary(signals)

    @staticmethod
    def _build_timeframe_context_cards(
        *,
        latest_signal: dict[str, Any] | None,
        timeframe_snapshots: list[dict[str, Any] | None],
    ) -> list[dict[str, Any]]:
        signal = latest_signal or {}
        mtf_signals = signal.get("mtf_signals") or {}
        timeframe_roles = {
            "5m": "Fast momentum and short-term pressure.",
            "15m": "Primary timeframe used for the signal decision.",
            "4h": "Broader trend and market backdrop.",
        }
        cards: list[dict[str, Any]] = []
        for snapshot in timeframe_snapshots:
            if snapshot is None:
                cards.append(
                    {
                        "label": "Missing",
                        "signal": "NO DATA",
                        "kind": "generic",
                        "role": "Market data is not available yet.",
                        "stats": [],
                        "empty_text": "No indicator snapshot available.",
                    }
                )
                continue
            timeframe = str(snapshot.get("timeframe") or "—")
            tf_signal = str(mtf_signals.get(timeframe, "NO_SIGNAL"))
            close = snapshot.get("overview_close", snapshot.get("price"))
            change_pct = snapshot.get("overview_change_pct")
            volume = snapshot.get("overview_volume", snapshot.get("volume"))
            cards.append(
                {
                    "label": f"{timeframe} Direction",
                    "signal": tf_signal,
                    "kind": "tp" if tf_signal == "BUY" else "generic",
                    "role": timeframe_roles.get(timeframe, "Market context for this timeframe."),
                    "stats": [
                        {
                            "label": "Close",
                            "value": f"{float(close):.2f}" if close is not None else "—",
                            "kind": "neutral",
                        },
                        {
                            "label": "Change",
                            "value": f"{float(change_pct):.2f}%" if change_pct is not None else "—",
                            "kind": "tp" if float(change_pct or 0.0) >= 0 else "sl",
                        },
                        {
                            "label": "Volume",
                            "value": f"{float(volume):.2f}" if volume is not None else "—",
                            "kind": "neutral",
                        },
                    ],
                    "empty_text": "",
                }
            )
        return cards
