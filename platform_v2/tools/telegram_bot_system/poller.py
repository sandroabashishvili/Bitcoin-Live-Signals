from __future__ import annotations

import fcntl
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from platform_v2.spot.config import settings
from platform_v2.shared.backend.persistence import read_runtime_state, write_runtime_state
from platform_v2.shared.runtime_warnings import warn_runtime_fallback

from .handlers import (
    handle_capital,
    handle_futures,
    handle_help,
    handle_health,
    handle_hedge,
    handle_positions,
    handle_start,
    handle_status,
    handle_stop,
    handle_summary,
    handle_spot,
)

_NEXT_FETCH_ALLOWED_AT = 0.0
_CONSECUTIVE_FAILURES = 0
_WARNING_THROTTLE_SECONDS = 300.0
_LAST_WARNING_AT_BY_KEY: dict[str, float] = {}
_NETWORK_BACKOFF_SECONDS = (2.0, 5.0, 10.0, 20.0, 30.0, 60.0)
_LISTENER_LOCK_PATH = Path(__file__).resolve().parent / "state" / "listener.lock"
_POLL_STATE_SYSTEM = "telegram"
_POLL_STATE_KEY = "polling"


class ListenerAlreadyRunningError(RuntimeError):
    """Raised when another process already owns the Telegram polling listener."""


def _bot_api_url(method: str) -> str:
    token = settings.TELEGRAM_BOT_TOKEN.strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty.")
    return f"https://api.telegram.org/bot{token}/{method}"


def _failure_category(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        return "network"
    return type(exc).__name__


def _progressive_backoff_seconds(consecutive_failures: int) -> float:
    index = min(max(consecutive_failures - 1, 0), len(_NETWORK_BACKOFF_SECONDS) - 1)
    return _NETWORK_BACKOFF_SECONDS[index]


def _retry_after_seconds(exc: BaseException, *, consecutive_failures: int) -> float:
    if isinstance(exc, urllib.error.HTTPError):
        retry_after = exc.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass
        try:
            raw = exc.read().decode("utf-8")
            payload = json.loads(raw)
        except (OSError, ValueError):
            payload = {}
        if isinstance(payload, dict):
            parameters = payload.get("parameters")
            if isinstance(parameters, dict):
                try:
                    return max(1.0, float(parameters.get("retry_after") or 0))
                except (TypeError, ValueError):
                    pass
        if exc.code == 429:
            return 30.0
        if exc.code == 409:
            return 60.0
        if exc.code in {401, 403}:
            return 300.0
        if exc.code >= 500:
            return max(15.0, _progressive_backoff_seconds(consecutive_failures))
    return _progressive_backoff_seconds(consecutive_failures)


def _post_form(method: str, payload: dict[str, Any], *, request_timeout: float = 25.0) -> dict[str, Any]:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(_bot_api_url(method), data=body, method="POST")
    with urllib.request.urlopen(request, timeout=request_timeout) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("Telegram API returned a non-dict payload.")
    return data


def _warn_fetch_fallback_once_per_window(
    *,
    exc: BaseException,
    offset: int | None,
    timeout: int,
    retry_after: float,
) -> None:
    now = time.monotonic()
    key = _failure_category(exc)
    last_warning_at = _LAST_WARNING_AT_BY_KEY.get(key, 0.0)
    if now - last_warning_at < _WARNING_THROTTLE_SECONDS:
        return
    _LAST_WARNING_AT_BY_KEY[key] = now
    warn_runtime_fallback(
        scope="telegram_bot_poller",
        operation="fetch_updates",
        error=exc,
        fallback=f"return_empty_updates_backoff_{retry_after:.0f}s",
        extra={"offset": offset, "timeout": timeout, "retry_after_seconds": retry_after},
    )


def fetch_updates(offset: int | None = None, *, timeout: int = 10) -> list[dict[str, Any]]:
    global _CONSECUTIVE_FAILURES, _NEXT_FETCH_ALLOWED_AT
    now = time.monotonic()
    if now < _NEXT_FETCH_ALLOWED_AT:
        time.sleep(_NEXT_FETCH_ALLOWED_AT - now)
    payload: dict[str, Any] = {"timeout": str(timeout)}
    if offset is not None:
        payload["offset"] = str(offset)
    try:
        data = _post_form("getUpdates", payload, request_timeout=float(timeout) + 10.0)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        _CONSECUTIVE_FAILURES += 1
        retry_after = _retry_after_seconds(
            exc,
            consecutive_failures=_CONSECUTIVE_FAILURES,
        )
        _NEXT_FETCH_ALLOWED_AT = time.monotonic() + retry_after
        _warn_fetch_fallback_once_per_window(
            exc=exc,
            offset=offset,
            timeout=timeout,
            retry_after=retry_after,
        )
        return []
    _CONSECUTIVE_FAILURES = 0
    _NEXT_FETCH_ALLOWED_AT = 0.0
    result = data.get("result")
    if not isinstance(result, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in result:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def handle_update(update: dict[str, Any]) -> int | None:
    update_id = update.get("update_id")
    if not isinstance(update_id, int):
        return None

    message = update.get("message")
    if not isinstance(message, dict):
        return update_id
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return update_id
    chat_id = chat.get("id")
    if not isinstance(chat_id, int):
        return update_id
    text = message.get("text")
    if not isinstance(text, str):
        return update_id
    sender = message.get("from")
    username = sender.get("username") if isinstance(sender, dict) else None
    first_name = sender.get("first_name") if isinstance(sender, dict) else None

    command = text.strip().split(maxsplit=1)[0].lower().split("@", 1)[0]
    handled = True
    if command == "/start":
        handled = handle_start(chat_id, username=username if isinstance(username, str) else None, first_name=first_name if isinstance(first_name, str) else None)
    elif command == "/stop":
        handled = handle_stop(chat_id)
    elif command == "/status":
        handled = handle_status(chat_id)
    elif command == "/summary":
        handled = handle_summary(chat_id)
    elif command == "/capital":
        handled = handle_capital(chat_id)
    elif command == "/positions":
        handled = handle_positions(chat_id)
    elif command == "/health":
        handled = handle_health(chat_id)
    elif command == "/spot":
        handled = handle_spot(chat_id)
    elif command == "/futures":
        handled = handle_futures(chat_id)
    elif command == "/hedge":
        handled = handle_hedge(chat_id)
    elif command == "/help":
        handled = handle_help(chat_id)
    if not handled:
        # Keep the update pending so a transient Telegram/API failure is retried.
        return -1
    return update_id


def run_poll_cycle(*, offset: int | None = None, timeout: int = 10) -> int | None:
    next_offset = offset
    for update in fetch_updates(offset=offset, timeout=timeout):
        update_id = handle_update(update)
        if update_id == -1:
            break
        if update_id is None:
            continue
        next_offset = update_id + 1
        _persist_offset(next_offset)
    return next_offset


def _load_persisted_offset() -> int | None:
    payload = read_runtime_state(system=_POLL_STATE_SYSTEM, state_key=_POLL_STATE_KEY) or {}
    value = payload.get("next_offset")
    return value if isinstance(value, int) and value >= 0 else None


def _persist_offset(next_offset: int | None) -> None:
    if next_offset is None:
        return
    write_runtime_state(
        system=_POLL_STATE_SYSTEM,
        state_key=_POLL_STATE_KEY,
        payload={"next_offset": next_offset},
    )


@contextmanager
def _listener_lock():
    _LISTENER_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LISTENER_LOCK_PATH.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ListenerAlreadyRunningError(
                "Another SmartSignalHub Telegram listener is already running."
            ) from exc
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def run_poll_forever(*, offset: int | None = None, timeout: int = 10, idle_sleep_seconds: float = 1.0) -> None:
    with _listener_lock():
        next_offset = _load_persisted_offset() if offset is None else offset
        while True:
            next_offset = run_poll_cycle(offset=next_offset, timeout=timeout)
            time.sleep(idle_sleep_seconds)
