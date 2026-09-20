from __future__ import annotations

from .message_builder import (
    build_access_denied_reply,
    build_help_reply,
    build_onboarding_markup,
    build_start_reply,
    build_status_reply,
    build_stop_reply,
)
from .notifier import send_message
from .runtime_snapshot import (
    build_capital_snapshot_reply,
    build_futures_reply,
    build_health_reply,
    build_hedge_reply,
    build_open_positions_reply,
    build_spot_reply,
    build_summary_reply,
)
from .subscribers import deactivate_subscriber, list_subscribers, upsert_subscriber
from platform_v2.spot.config import settings


def _is_active(chat_id: int) -> bool:
    for row in list_subscribers():
        if row.get("chat_id") == chat_id:
            return row.get("status") == "active"
    return False


def _is_allowed(chat_id: int) -> bool:
    allowlist = getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", frozenset())
    return not allowlist or chat_id in allowlist


def _can_view_details(chat_id: int) -> bool:
    return _is_allowed(chat_id) and _is_active(chat_id)


def handle_start(chat_id: int, *, username: str | None, first_name: str | None) -> bool:
    if not _is_allowed(chat_id):
        return send_message(chat_id, build_access_denied_reply())
    upsert_subscriber(chat_id, username=username, first_name=first_name)
    return send_message(
        chat_id,
        build_start_reply(),
        reply_markup=build_onboarding_markup(active=True),
    )


def handle_stop(chat_id: int) -> bool:
    if not _is_allowed(chat_id):
        return send_message(chat_id, build_access_denied_reply())
    deactivate_subscriber(chat_id)
    return send_message(
        chat_id,
        build_stop_reply(),
        reply_markup=build_onboarding_markup(active=False),
    )


def handle_status(chat_id: int) -> bool:
    if not _is_allowed(chat_id):
        return send_message(chat_id, build_access_denied_reply())
    active = _is_active(chat_id)
    return send_message(
        chat_id,
        build_status_reply(active=active),
        reply_markup=build_onboarding_markup(active=active),
    )


def handle_help(chat_id: int) -> bool:
    if not _is_allowed(chat_id):
        return send_message(chat_id, build_access_denied_reply())
    return send_message(
        chat_id,
        build_help_reply(),
        reply_markup=build_onboarding_markup(active=_is_active(chat_id)),
    )


def handle_capital(chat_id: int) -> bool:
    if not _can_view_details(chat_id):
        return send_message(chat_id, build_access_denied_reply())
    return send_message(
        chat_id,
        build_capital_snapshot_reply(),
        reply_markup=build_onboarding_markup(active=_is_active(chat_id)),
    )


def handle_summary(chat_id: int) -> bool:
    if not _can_view_details(chat_id):
        return send_message(chat_id, build_access_denied_reply())
    return send_message(
        chat_id,
        build_summary_reply(),
        reply_markup=build_onboarding_markup(active=_is_active(chat_id)),
    )


def handle_positions(chat_id: int) -> bool:
    if not _can_view_details(chat_id):
        return send_message(chat_id, build_access_denied_reply())
    return send_message(
        chat_id,
        build_open_positions_reply(),
        reply_markup=build_onboarding_markup(active=_is_active(chat_id)),
    )


def _handle_detail(chat_id: int, builder) -> bool:
    if not _can_view_details(chat_id):
        return send_message(chat_id, build_access_denied_reply())
    return send_message(chat_id, builder(), reply_markup=build_onboarding_markup(active=True))


def handle_health(chat_id: int) -> bool:
    return _handle_detail(chat_id, build_health_reply)


def handle_spot(chat_id: int) -> bool:
    return _handle_detail(chat_id, build_spot_reply)


def handle_futures(chat_id: int) -> bool:
    return _handle_detail(chat_id, build_futures_reply)


def handle_hedge(chat_id: int) -> bool:
    return _handle_detail(chat_id, build_hedge_reply)
