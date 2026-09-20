from __future__ import annotations

from typing import Any
from html import escape

from platform_v2.shared.backend.runtime_store.futures import (
    METRICS_FAMILY as FUTURES_METRICS_FAMILY,
    POSITIONS_FAMILY as FUTURES_POSITIONS_FAMILY,
    load_family_rows_all as load_futures_rows_all,
    load_latest_document as load_latest_futures_document,
)
from platform_v2.shared.backend.runtime_store.hedge import (
    HEDGE_DAILY_SUMMARIES_FAMILY,
    load_latest_document as load_latest_hedge_document,
)
from platform_v2.shared.backend.runtime_store.spot import (
    METRICS_FAMILY as SPOT_METRICS_FAMILY,
    POSITIONS_FAMILY as SPOT_POSITIONS_FAMILY,
    load_family_rows_all as load_spot_rows_all,
    load_latest_document as load_latest_spot_document,
)
from platform_v2.shared.backend.persistence import read_market_series_safely


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:.2f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def _signed_money(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}${value:.2f}"


def _signed_pct(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _pnl_icon(value: float | None) -> str:
    if value is None or value == 0:
        return "⚪"
    return "🟢" if value > 0 else "🔴"


def _side_icon(side: str) -> str:
    normalized = side.upper()
    if normalized in {"BUY", "LONG"}:
        return "🟢"
    if normalized in {"SELL", "SHORT"}:
        return "🔴"
    return "⚪"


def _h(value: Any) -> str:
    return escape(str(value), quote=False)


def _line_money(label: str, value: float | None, *, signed: bool = False) -> str:
    icon = _pnl_icon(value) if signed else ""
    formatted = _signed_money(value) if signed else _money(value)
    prefix = f"{icon} " if icon else ""
    return f"{label}: <b>{prefix}{formatted}</b>"


def _line_pct(label: str, value: float | None, *, signed: bool = False) -> str:
    icon = _pnl_icon(value) if signed else ""
    formatted = _signed_pct(value) if signed else _pct(value)
    prefix = f"{icon} " if icon else ""
    return f"{label}: <b>{prefix}{formatted}</b>"


def _line_count(label: str, value: int | None) -> str:
    text = "—" if value is None else str(value)
    return f"{label}: <b>{text}</b>"


def _line_text(label: str, value: Any) -> str:
    text = str(value or "—")
    return f"{label}: <b>{_h(text)}</b>"


def _load_latest_hedge_summary() -> dict[str, Any]:
    payload = load_latest_hedge_document(HEDGE_DAILY_SUMMARIES_FAMILY)
    rows = payload if isinstance(payload, list) else ([payload] if isinstance(payload, dict) else [])
    return rows[-1] if rows else {}


def _latest_open_positions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_position: dict[str, dict[str, Any]] = {}
    for row in rows:
        position_id = str(row.get("position_id") or "").strip()
        if not position_id:
            continue
        latest_by_position[position_id] = row
    return [
        row
        for row in latest_by_position.values()
        if str(row.get("status") or "").upper() == "OPEN"
    ]


def _latest_spot_mark(symbol: str, timeframe: str = "15m") -> float | None:
    rows = read_market_series_safely(
        venue="binance",
        asset_class="crypto",
        market_type="spot",
        dataset="candles",
        symbol=symbol,
        timeframe=timeframe,
    )
    if not rows:
        return None
    return _as_float(rows[-1].get("close"))


def build_capital_snapshot_reply() -> str:
    spot_payload = load_latest_spot_document(SPOT_METRICS_FAMILY)
    futures_payload = load_latest_futures_document(FUTURES_METRICS_FAMILY)
    spot = spot_payload if isinstance(spot_payload, dict) else {}
    futures = futures_payload if isinstance(futures_payload, dict) else {}
    hedge = _load_latest_hedge_summary()

    hedge_equity = _as_float(hedge.get("equity_usdt"))
    hedge_starting_capital = _as_float(hedge.get("starting_capital_usdt"))
    hedge_net_pnl = None
    hedge_return_pct = None
    if hedge_equity is not None and hedge_starting_capital:
        hedge_net_pnl = hedge_equity - hedge_starting_capital
        hedge_return_pct = hedge_net_pnl / hedge_starting_capital * 100.0
    return (
        "<b>SmartSignalHub · Capital</b>\n\n"
        f"Spot: Equity {_money(_as_float(spot.get('equity')))} | Available {_money(_as_float(spot.get('available_balance')))} | PnL {_signed_money(_as_float(spot.get('total_net_pnl')))}\n"
        f"Futures: Equity {_money(_as_float(futures.get('equity')))} | Available {_money(_as_float(futures.get('available_balance')))} | PnL {_signed_money(_as_float(futures.get('total_net_pnl')))}\n"
        f"Hedge: Equity {_money(hedge_equity)} | Available {_money(_as_float(hedge.get('available_capital_usdt')))} | Margin {_money(_as_float(hedge.get('used_margin_usdt')))} | PnL {_signed_money(hedge_net_pnl)}"
    )


def _build_system_snapshot_reply(*, title: str, payload: dict[str, Any]) -> str:
    """Format one trading engine without mixing Spot/Futures/Hedge data."""
    return (
        f"<b>{_h(title)}</b>\n"
        f"Date: <b>{_h(payload.get('date') or '—')}</b> | Updated: {_h(payload.get('datetime') or '—')}\n\n"
        f"{_line_money('Starting Capital', _as_float(payload.get('starting_capital')))}\n"
        f"{_line_money('Available Balance', _as_float(payload.get('available_balance')))}\n"
        f"{_line_money('Equity', _as_float(payload.get('equity')))}\n"
        f"{_line_money('Total Net PnL', _as_float(payload.get('total_net_pnl')), signed=True)}\n"
        f"{_line_pct('Net Return %', _as_float(payload.get('net_return_pct')), signed=True)}\n"
        f"{_line_money('Unrealized PnL', _as_float(payload.get('unrealized_pnl')), signed=True)}\n"
        f"{_line_money('Reserved Capital', _as_float(payload.get('reserved_capital')))}\n"
        f"{_line_count('Open Positions', _as_int(payload.get('open_positions')))}\n"
        f"{_line_count('Closed Positions', _as_int(payload.get('closed_positions')))}\n"
        f"{_line_pct('Win Rate', _as_float(payload.get('win_rate')))}"
    )


def build_spot_reply() -> str:
    payload = load_latest_spot_document(SPOT_METRICS_FAMILY)
    return _build_system_snapshot_reply(title="SmartSignalHub · Spot", payload=payload if isinstance(payload, dict) else {})


def build_futures_reply() -> str:
    payload = load_latest_futures_document(FUTURES_METRICS_FAMILY)
    return _build_system_snapshot_reply(title="SmartSignalHub · Futures", payload=payload if isinstance(payload, dict) else {})


def build_hedge_reply() -> str:
    hedge = _load_latest_hedge_summary()
    equity = _as_float(hedge.get("equity_usdt"))
    starting = _as_float(hedge.get("starting_capital_usdt"))
    pnl = equity - starting if equity is not None and starting is not None else None
    return (
        "<b>SmartSignalHub · Hedge</b>\n"
        f"Date: <b>{_h(hedge.get('date') or hedge.get('as_of_date') or '—')}</b>\n\n"
        f"{_line_money('Starting Capital', starting)}\n"
        f"{_line_money('Open Equity', equity)}\n"
        f"{_line_money('Available Capital', _as_float(hedge.get('available_capital_usdt')))}\n"
        f"{_line_money('Used Margin', _as_float(hedge.get('used_margin_usdt')))}\n"
        f"{_line_money('Total Net PnL', pnl, signed=True)}\n"
        f"{_line_money('Unrealized PnL', _as_float(hedge.get('unrealized_pnl_usdt')), signed=True)}\n"
        f"{_line_money('Realized PnL', _as_float(hedge.get('realized_pnl_usdt')), signed=True)}\n"
        f"{_line_money('Total Fees', _as_float(hedge.get('total_fees_usdt')))}\n"
        f"{_line_text('Net Exposure', _hedge_exposure_label(hedge))}\n"
        f"{_line_text('Liquidation Risk', hedge.get('liquidation_risk'))}"
    )


def build_health_reply() -> str:
    spot = load_latest_spot_document(SPOT_METRICS_FAMILY)
    futures = load_latest_futures_document(FUTURES_METRICS_FAMILY)
    hedge = _load_latest_hedge_summary()
    def state(label: str, payload: Any) -> str:
        if not isinstance(payload, dict) or not payload:
            return f"🔴 {label}: no runtime snapshot"
        return f"🟢 {label}: {_h(payload.get('date') or payload.get('datetime') or 'snapshot available')}"
    return (
        "<b>SmartSignalHub · Health</b>\n\n"
        f"{state('Spot', spot)}\n"
        f"{state('Futures', futures)}\n"
        f"{state('Hedge', hedge)}\n\n"
        "Listener: 🟢 responding to this command"
    )


def build_summary_reply() -> str:
    spot_payload = load_latest_spot_document(SPOT_METRICS_FAMILY)
    futures_payload = load_latest_futures_document(FUTURES_METRICS_FAMILY)
    spot = spot_payload if isinstance(spot_payload, dict) else {}
    futures = futures_payload if isinstance(futures_payload, dict) else {}
    hedge = _load_latest_hedge_summary()

    hedge_equity = _as_float(hedge.get("equity_usdt"))
    hedge_starting_capital = _as_float(hedge.get("starting_capital_usdt"))
    hedge_net_pnl = None
    hedge_return_pct = None
    if hedge_equity is not None and hedge_starting_capital:
        hedge_net_pnl = hedge_equity - hedge_starting_capital
        hedge_return_pct = hedge_net_pnl / hedge_starting_capital * 100.0

    spot_pnl = _as_float(spot.get("total_net_pnl"))
    futures_pnl = _as_float(futures.get("total_net_pnl"))
    total_pnl = None
    known_pnls = [value for value in (spot_pnl, futures_pnl, hedge_net_pnl) if value is not None]
    if known_pnls:
        total_pnl = sum(known_pnls)

    return (
        "<b>SmartSignalHub Summary</b>\n"
        f"Total: <b>{_pnl_icon(total_pnl)} {_signed_money(total_pnl)}</b>\n\n"
        f"Spot: <b>{_pnl_icon(spot_pnl)} {_signed_money(spot_pnl)}</b> | "
        f"Equity {_money(_as_float(spot.get('equity')))} | Open {_h(_as_int(spot.get('open_positions')) or 0)}\n"
        f"Futures: <b>{_pnl_icon(futures_pnl)} {_signed_money(futures_pnl)}</b> | "
        f"Equity {_money(_as_float(futures.get('equity')))} | Open {_h(_as_int(futures.get('open_positions')) or 0)}\n"
        f"Hedge: <b>{_pnl_icon(hedge_net_pnl)} {_signed_money(hedge_net_pnl)}</b> | "
        f"Equity {_money(hedge_equity)} | Return {_signed_pct(hedge_return_pct)}\n\n"
        f"Risk: <b>{_h(hedge.get('liquidation_risk') or '—')}</b> | "
        f"Exposure: <b>{_h(_hedge_exposure_label(hedge))}</b>"
    )


def _hedge_exposure_label(hedge: dict[str, Any]) -> str:
    side = str(hedge.get("net_exposure_side") or "—").upper()
    amount = _as_float(hedge.get("net_exposure_usdt"))
    if side in {"", "—"}:
        return "—"
    if side == "FLAT":
        return "FLAT"
    return f"{side} {_money(amount)}"


def build_open_positions_reply() -> str:
    spot_rows = _latest_open_positions(load_spot_rows_all(SPOT_POSITIONS_FAMILY))
    futures_rows = _latest_open_positions(load_futures_rows_all(FUTURES_POSITIONS_FAMILY))

    spot_lines: list[str] = []
    for row in spot_rows:
        execution = row.get("execution") if isinstance(row.get("execution"), dict) else {}
        entry = _as_float(execution.get("entry_price"))
        symbol = str(row.get("symbol") or "—")
        side = str(row.get("side") or "—").upper()
        mark = _as_float(row.get("mark_price") or row.get("exit_trigger_price")) or _latest_spot_mark(symbol)
        unreal = _as_float(row.get("unrealized_pnl"))
        position_size = _as_float(execution.get("position_size"))
        tp = _as_float(execution.get("take_profit"))
        sl = _as_float(execution.get("stop_loss"))
        position_id = str(row.get("position_id") or "—")
        spot_lines.append(
            f"{_side_icon(side)} <b>{_h(position_id)} {_h(side)} {_h(symbol)}</b>\n"
            f"Entry {_money(entry)} | Mark {_money(mark)}\n"
            f"Unreal {_pnl_icon(unreal)} {_signed_money(unreal)}\n"
            f"TP {_money(tp)} | SL {_money(sl)} | Size {_money(position_size)}"
        )
    if not spot_lines:
        spot_lines.append("No open positions.")

    futures_lines: list[str] = []
    for row in futures_rows:
        entry = _as_float(row.get("entry_price"))
        symbol = str(row.get("symbol") or "—")
        side = str(row.get("side") or "—").upper()
        mark = _as_float(row.get("mark_price"))
        notional = _as_float(row.get("notional_usdt")) or _as_float(row.get("margin_usdt"))
        unreal = _as_float(row.get("unrealized_pnl"))
        margin = _as_float(row.get("margin_usdt"))
        roe = _as_float(row.get("roe_pct"))
        position_id = str(row.get("position_id") or "—")
        tp = _as_float(row.get("tp_price"))
        sl = _as_float(row.get("sl_price"))
        futures_lines.append(
            f"{_side_icon(side)} <b>{_h(position_id)} {_h(side)} {_h(symbol)}</b>\n"
            f"Entry {_money(entry)} | Mark {_money(mark)}\n"
            f"Unreal {_pnl_icon(unreal)} {_signed_money(unreal)} | ROE {_pnl_icon(roe)} {_signed_pct(roe)}\n"
            f"TP {_money(tp)} | SL {_money(sl)} | Margin {_money(margin)} | Notional {_money(notional)}"
        )
    if not futures_lines:
        futures_lines.append("No open positions.")

    hedge = _load_latest_hedge_summary()
    long_basket = hedge.get("long_basket") if isinstance(hedge.get("long_basket"), dict) else {}
    short_basket = hedge.get("short_basket") if isinstance(hedge.get("short_basket"), dict) else {}
    hedge_lines = [
        f"🟢 <b>LONG Basket</b>\n"
        f"Entries {_h(long_basket.get('count') or 0)} | Avg {_money(_as_float(long_basket.get('average_entry_price')))} | Mark {_money(_as_float(long_basket.get('mark_price')))}\n"
        f"Margin {_money(_as_float(long_basket.get('margin_usdt')))} | Notional {_money(_as_float(long_basket.get('notional_usdt')))}\n"
        f"Unreal {_pnl_icon(_as_float(long_basket.get('unrealized_pnl')))} {_signed_money(_as_float(long_basket.get('unrealized_pnl')))} | ROE {_pnl_icon(_as_float(long_basket.get('roe_pct')))} {_signed_pct(_as_float(long_basket.get('roe_pct')))}",
        f"🔴 <b>SHORT Basket</b>\n"
        f"Entries {_h(short_basket.get('count') or 0)} | Avg {_money(_as_float(short_basket.get('average_entry_price')))} | Mark {_money(_as_float(short_basket.get('mark_price')))}\n"
        f"Margin {_money(_as_float(short_basket.get('margin_usdt')))} | Notional {_money(_as_float(short_basket.get('notional_usdt')))}\n"
        f"Unreal {_pnl_icon(_as_float(short_basket.get('unrealized_pnl')))} {_signed_money(_as_float(short_basket.get('unrealized_pnl')))} | ROE {_pnl_icon(_as_float(short_basket.get('roe_pct')))} {_signed_pct(_as_float(short_basket.get('roe_pct')))}",
    ]

    return (
        "<b>SmartSignalHub Open Positions</b>\n\n"
        "<b>Spot</b>\n"
        + "\n".join(spot_lines)
        + "\n\n<b>Futures</b>\n"
        + "\n".join(futures_lines)
        + "\n\n<b>Hedge</b>\n"
        + "\n\n".join(hedge_lines)
    )
