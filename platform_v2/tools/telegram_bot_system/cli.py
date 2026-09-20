from __future__ import annotations

import argparse

from platform_v2.spot.config import settings

from .notifier import set_my_commands
from .poller import ListenerAlreadyRunningError, run_poll_cycle, run_poll_forever
from .subscribers import SUBSCRIBERS_PATH, list_subscribers


BOT_COMMANDS: list[dict[str, str]] = [
    {"command": "start", "description": "Enable SmartSignalHub alerts"},
    {"command": "status", "description": "Check whether alerts are active"},
    {"command": "summary", "description": "Show short Spot/Futures/Hedge summary"},
    {"command": "health", "description": "Check runtime and data health"},
    {"command": "spot", "description": "Show Spot account snapshot"},
    {"command": "futures", "description": "Show Futures account snapshot"},
    {"command": "hedge", "description": "Show Hedge account snapshot"},
    {"command": "capital", "description": "Show Spot/Futures/Hedge capital snapshot"},
    {"command": "positions", "description": "Show Spot/Futures/Hedge positions"},
    {"command": "stop", "description": "Disable SmartSignalHub alerts"},
    {"command": "help", "description": "Show available bot commands"},
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or inspect the SmartSignalHub Telegram bot skeleton.")
    parser.add_argument("--poll-once", action="store_true", help="Poll Telegram updates once and exit.")
    parser.add_argument("--run-forever", action="store_true", help="Continuously poll Telegram updates.")
    parser.add_argument("--status", action="store_true", help="Print local Telegram bot status and subscriber count.")
    parser.add_argument("--set-commands", action="store_true", help="Push the bot command menu to Telegram.")
    return parser


def _print_status() -> None:
    subscribers = list_subscribers()
    active_count = sum(1 for row in subscribers if row.get("status") == "active")
    print(f"Telegram enabled: {settings.TELEGRAM_BOT_ENABLED}")
    print(f"Bot token configured: {bool(settings.TELEGRAM_BOT_TOKEN.strip())}")
    print(f"Subscribers file: {SUBSCRIBERS_PATH}")
    print(f"Subscribers total: {len(subscribers)}")
    print(f"Subscribers active: {active_count}")


def main() -> int:
    args = _build_parser().parse_args()
    if args.status or (not args.poll_once and not args.run_forever and not args.set_commands):
        _print_status()
    if args.set_commands:
        if set_my_commands(BOT_COMMANDS):
            print("Telegram bot command menu updated.")
        else:
            print("Telegram bot command menu update failed.")
    if args.poll_once:
        offset = run_poll_cycle(offset=None, timeout=1)
        print(f"Polling completed. Next offset: {offset}")
    if args.run_forever:
        print("Telegram bot listener started. Press Ctrl+C to stop.")
        try:
            run_poll_forever(offset=None, timeout=20, idle_sleep_seconds=1.0)
        except ListenerAlreadyRunningError as exc:
            print(f"Telegram bot listener not started: {exc}")
            return 2
        except KeyboardInterrupt:
            print("\nTelegram bot listener stopped.")
    return 0
