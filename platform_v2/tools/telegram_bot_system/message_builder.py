from __future__ import annotations

from datetime import UTC, datetime
from html import escape


SITE_URL = "https://sandro-abashishvili.de/Bitcoin-Live-Signals/"


def _short_position_id(position_id: str | None) -> str:
    text = (position_id or "").strip()
    if not text:
        return "—"
    return text


def _h(value: object) -> str:
    return escape(str(value), quote=False)


def _side_icon(side: str) -> str:
    normalized = side.upper()
    if normalized in {"BUY", "LONG"}:
        return "🟢"
    if normalized in {"SELL", "SHORT"}:
        return "🔴"
    return "⚪"


def _pnl_icon(value: float | None) -> str:
    if value is None or value == 0:
        return "⚪"
    return "🟢" if value > 0 else "🔴"


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:.2f}"


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


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def _format_event_time_utc(event_time: str | None) -> str:
    text = (event_time or "").strip()
    if not text:
        return "—"
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text) / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, OSError):
            return text
    normalized = text.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
        return parsed.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return text


def _build_snapshot_block(
    *,
    open_positions: int | None = None,
    active_exposure: float | None = None,
    available_balance: float | None = None,
    equity: float | None = None,
    annualized_return: float | None = None,
    net_return_pct: float | None = None,
    total_net_pnl: float | None = None,
    unrealized_pnl: float | None = None,
    total_positions: int | None = None,
    closed_positions: int | None = None,
    tp_hits: int | None = None,
    sl_hits: int | None = None,
    force_close_events: int | None = None,
) -> str:
    open_text = "—" if open_positions is None else str(open_positions)
    exposure_text = _money(active_exposure)
    available_text = _money(available_balance)
    equity_text = _money(equity)
    net_pnl_text = f"{_pnl_icon(total_net_pnl)} {_signed_money(total_net_pnl)}"
    unrealized_text = f"{_pnl_icon(unrealized_pnl)} {_signed_money(unrealized_pnl)}"
    return (
        "<b>Account</b>\n"
        f"Equity {equity_text} | PnL {net_pnl_text} | Open {open_text}\n"
        f"Available {available_text} | Unrealized {unrealized_text} | Exposure {exposure_text}"
    )


def build_start_reply() -> str:
    return (
        "SmartSignalHub alerts are now enabled.\n\n"
        "You will receive live trade alerts in this chat.\n"
        f"Website: {SITE_URL}\n\n"
        "Use /status to check your subscription, /stop to disable alerts, or /help to see available commands."
    )


def build_stop_reply() -> str:
    return "SmartSignalHub alerts are now disabled. Use /start to enable them again."


def build_status_reply(*, active: bool) -> str:
    if active:
        return (
            "Your SmartSignalHub Telegram alerts are active.\n"
            f"Website: {SITE_URL}"
        )
    return (
        "Your SmartSignalHub Telegram alerts are not active. Use /start to enable them.\n"
        f"Website: {SITE_URL}"
    )


def build_help_reply() -> str:
    return (
        "<b>SmartSignalHub</b> · Command guide\n\n"
        "<b>Overview</b>\n"
        "/summary — short account overview\n"
        "/health — runtime/data health\n\n"
        "<b>Details</b>\n"
        "/spot — Spot account snapshot\n"
        "/futures — Futures account snapshot\n"
        "/hedge — Hedge account snapshot\n"
        "/capital — capital and PnL by system\n"
        "/positions — currently open positions\n\n"
        "<b>Alerts</b>\n"
        "/start — enable alerts\n"
        "/stop — disable alerts\n"
        "/status — check alert status\n\n"
        f"Website: {SITE_URL}"
    )


def build_access_denied_reply() -> str:
    return "⛔ Access is not enabled for this chat. Use /start first or contact the administrator."


def build_onboarding_markup(*, active: bool) -> dict[str, object]:
    if active:
        keyboard = [
            [{"text": "/status"}, {"text": "/help"}],
            [{"text": "/summary"}, {"text": "/capital"}],
            [{"text": "/health"}, {"text": "/positions"}],
            [{"text": "/spot"}, {"text": "/futures"}, {"text": "/hedge"}],
            [{"text": "/stop"}],
        ]
    else:
        keyboard = [
            [{"text": "/start"}, {"text": "/help"}],
        ]
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "is_persistent": True,
    }


def build_signal_opened_message(
    *,
    symbol: str,
    timeframe: str,
    position_id: str | None,
    event_time: str | None,
    side: str,
    entry: float,
    take_profit: float,
    stop_loss: float,
    score: float | None = None,
    open_positions: int | None = None,
    active_exposure: float | None = None,
    available_balance: float | None = None,
    equity: float | None = None,
    annualized_return: float | None = None,
    net_return_pct: float | None = None,
    total_net_pnl: float | None = None,
    unrealized_pnl: float | None = None,
    total_positions: int | None = None,
    closed_positions: int | None = None,
    tp_hits: int | None = None,
    sl_hits: int | None = None,
    force_close_events: int | None = None,
    source_label: str = "Spot",
    hedge_context: str | None = None,
) -> str:
    score_text = "—" if score is None else f"{score:.2f}"
    hedge_block = f"\n\n{hedge_context}" if hedge_context else ""
    snapshot_text = _build_snapshot_block(
        open_positions=open_positions,
        active_exposure=active_exposure,
        available_balance=available_balance,
        equity=equity,
        annualized_return=annualized_return,
        net_return_pct=net_return_pct,
        total_net_pnl=total_net_pnl,
        unrealized_pnl=unrealized_pnl,
        total_positions=total_positions,
        closed_positions=closed_positions,
        tp_hits=tp_hits,
        sl_hits=sl_hits,
        force_close_events=force_close_events,
    )

    return (
        f"{_side_icon(side)} <b>{_h(source_label)} {_h(side)} · OPENED</b>\n"
        f"{_h(symbol)} · {_h(timeframe)} · {_h(_short_position_id(position_id))}\n"
        f"{_format_event_time_utc(event_time)}\n\n"
        "<b>Trade setup</b>\n"
        f"Entry <b>{entry:.2f}</b> · TP <b>{take_profit:.2f}</b> · SL <b>{stop_loss:.2f}</b>\n"
        f"Score <b>{score_text}</b>"
        f"{hedge_block}\n\n"
        f"{snapshot_text}"
    )


def build_position_closed_message(
    *,
    symbol: str,
    timeframe: str,
    position_id: str | None,
    event_time: str | None,
    side: str,
    outcome: str,
    exit_price: float | None = None,
    net_pnl: float | None = None,
    exit_check_timeframe: str | None = None,
    open_positions: int | None = None,
    active_exposure: float | None = None,
    available_balance: float | None = None,
    equity: float | None = None,
    annualized_return: float | None = None,
    net_return_pct: float | None = None,
    total_net_pnl: float | None = None,
    unrealized_pnl: float | None = None,
    total_positions: int | None = None,
    closed_positions: int | None = None,
    tp_hits: int | None = None,
    sl_hits: int | None = None,
    force_close_events: int | None = None,
    source_label: str = "Spot",
) -> str:
    exit_text = "—" if exit_price is None else f"{exit_price:.2f}"
    snapshot_text = _build_snapshot_block(
        open_positions=open_positions,
        active_exposure=active_exposure,
        available_balance=available_balance,
        equity=equity,
        annualized_return=annualized_return,
        net_return_pct=net_return_pct,
        total_net_pnl=total_net_pnl,
        unrealized_pnl=unrealized_pnl,
        total_positions=total_positions,
        closed_positions=closed_positions,
        tp_hits=tp_hits,
        sl_hits=sl_hits,
        force_close_events=force_close_events,
    )

    outcome_label = {
        "TP_HIT": "TAKE PROFIT HIT",
        "SL_HIT": "STOP LOSS HIT",
        "PROFIT_LOCK_HIT": "PROFIT LOCK HIT",
        "FORCE_CLOSE": "FORCE CLOSED",
    }.get(outcome.upper(), outcome.replace("_", " ").upper())
    return (
        f"{_pnl_icon(net_pnl)} <b>{_h(source_label)} {_h(side)} · CLOSED</b>\n"
        f"{_h(symbol)} · {_h(timeframe)} · {_h(_short_position_id(position_id))}\n"
        f"{_format_event_time_utc(event_time)}\n\n"
        f"<b>Result</b> · {_h(outcome_label)}\n"
        f"Exit <b>{exit_text}</b> · Net PnL <b>{_pnl_icon(net_pnl)} {_signed_money(net_pnl)}</b>\n\n"
        f"{snapshot_text}"
    )


def build_hedge_reset_message(
    *,
    reset_id: int,
    event_time: str | None,
    reason: str,
    mark_price: float | None,
    net_pnl: float | None,
    equity_before_reset: float | None,
    cash_after_reset: float | None,
) -> str:
    mark_text = "—" if mark_price is None else f"{mark_price:.2f}"
    return (
        "♻️ <b>Hedge basket reset</b>\n"
        f"Reset #{reset_id} | {_format_event_time_utc(event_time)}\n\n"
        f"Reason: {_h(reason.replace('_', ' '))}\n"
        f"Mark: {mark_text}\n"
        f"Net PnL: {_pnl_icon(net_pnl)} {_signed_money(net_pnl)}\n"
        f"Equity before: {_money(equity_before_reset)}\n"
        f"Cash after: {_money(cash_after_reset)}"
    )


def build_hedge_risk_change_message(
    *,
    previous_risk: str,
    current_risk: str,
    worst_basket_roe_pct: float | None,
    margin_used_pct: float | None,
    net_exposure_side: str,
    net_exposure_usdt: float | None,
) -> str:
    risk_icon = {
        "LOW": "🟢",
        "ELEVATED": "🟡",
        "MEDIUM": "🟠",
        "HIGH": "🔴",
    }.get(current_risk.upper(), "⚪")
    return (
        f"{risk_icon} <b>Hedge risk changed</b>\n"
        f"{_h(previous_risk)} → <b>{_h(current_risk)}</b>\n\n"
        f"Worst basket ROE: {_signed_pct(worst_basket_roe_pct)}\n"
        f"Margin used: {_pct(margin_used_pct)}\n"
        f"Net exposure: {_h(net_exposure_side)} {_money(net_exposure_usdt)}"
    )
