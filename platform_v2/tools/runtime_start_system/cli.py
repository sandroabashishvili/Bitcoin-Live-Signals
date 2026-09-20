from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time

from platform_v2.shared.terminal_output import (
    print_process_shutdown,
    print_process_start,
    print_process_stop,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start SmartSignalHub spot/futures run loops from one command."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--spot-only",
        action="store_true",
        help="Start only spot run loop.",
    )
    group.add_argument(
        "--futures-only",
        action="store_true",
        help="Start only futures run loop.",
    )
    return parser


def _selected_targets(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    all_targets = [
        ("spot", [sys.executable, "-m", "platform_v2.spot.app.run_loop"]),
        ("futures", [sys.executable, "-m", "platform_v2.futures.app.run_loop"]),
    ]
    if args.spot_only:
        return [all_targets[0]]
    if args.futures_only:
        return [all_targets[1]]
    return all_targets


def _telegram_target() -> tuple[str, list[str]]:
    return (
        "telegram",
        [sys.executable, "-m", "platform_v2.tools.telegram_bot_system", "--run-forever"],
    )


def _terminate_children(children: dict[str, subprocess.Popen[bytes]]) -> None:
    for process in children.values():
        if process.poll() is None:
            process.terminate()
    end_time = time.time() + 10
    while time.time() < end_time:
        if all(process.poll() is not None for process in children.values()):
            return
        time.sleep(0.1)
    for process in children.values():
        if process.poll() is None:
            process.kill()


def main() -> int:
    args = _build_parser().parse_args()
    targets = _selected_targets(args)
    # The normal launcher is intentionally the single source of truth: the
    # inbound Telegram listener must run with the trading loops so commands
    # work without a second terminal.
    targets.append(_telegram_target())
    children: dict[str, subprocess.Popen[bytes]] = {}
    stop_requested = False

    def _request_stop(_sig: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    for name, command in targets:
        print_process_start(name=name, command=command)
        children[name] = subprocess.Popen(command)

    try:
        while True:
            if stop_requested:
                print_process_shutdown("stop requested")
                _terminate_children(children)
                return 0

            for name, process in list(children.items()):
                return_code = process.poll()
                if return_code is not None:
                    print_process_stop(name=name, return_code=return_code)
                    _terminate_children(children)
                    return return_code
            time.sleep(0.5)
    except KeyboardInterrupt:
        print_process_shutdown("keyboard interrupt")
        _terminate_children(children)
        return 0
