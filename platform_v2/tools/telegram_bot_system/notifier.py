from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from platform_v2.spot.config import settings
from platform_v2.shared.runtime_warnings import warn_runtime_fallback

from .subscribers import list_active_chat_ids


def _bot_api_url(method: str) -> str:
    token = settings.TELEGRAM_BOT_TOKEN.strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty.")
    return f"https://api.telegram.org/bot{token}/{method}"


def _post_form(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(_bot_api_url(method), data=body, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Telegram API returned a non-dict payload.")
    return data


def send_message(chat_id: int, text: str, *, reply_markup: dict[str, Any] | None = None) -> bool:
    if not settings.TELEGRAM_BOT_ENABLED:
        return False
    payload: dict[str, str] = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    try:
        data = _post_form("sendMessage", payload)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        warn_runtime_fallback(
            scope="telegram_bot_notifier",
            operation="send_message",
            error=exc,
            fallback="return_false",
            extra={"chat_id": chat_id},
        )
        return False
    return bool(data.get("ok"))


def set_my_commands(commands: list[dict[str, str]]) -> bool:
    if not settings.TELEGRAM_BOT_ENABLED:
        return False
    try:
        data = _post_form(
            "setMyCommands",
            {
                "commands": json.dumps(commands, ensure_ascii=False),
            },
        )
    except (OSError, ValueError, urllib.error.URLError) as exc:
        warn_runtime_fallback(
            scope="telegram_bot_notifier",
            operation="set_my_commands",
            error=exc,
            fallback="return_false",
            extra={"command_count": len(commands)},
        )
        return False
    return bool(data.get("ok"))


def broadcast_message(text: str) -> dict[str, int]:
    sent = 0
    failed = 0
    for chat_id in list_active_chat_ids():
        if send_message(chat_id, text):
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed}
