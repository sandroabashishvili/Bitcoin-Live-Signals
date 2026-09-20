"""File: terminal_output.py
Folder: platform_v2/shared
Created date: 2026-04-24
Last updated date: 2026-06-01
Author: Codex
Purpose: Human-readable terminal output helpers for runtime operations.
"""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:  # pragma: no cover - import fallback depends on local environment
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
except ImportError:  # pragma: no cover
    Console = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]
    Text = None  # type: ignore[assignment]


_CONSOLE = Console() if Console is not None else None


def print_process_start(*, name: str, command: list[str]) -> None:
    command_text = " ".join(command)
    _print_status_line(
        tag="runtime",
        style="cyan",
        message=f"starting {name}",
        detail=command_text,
    )


def print_process_stop(
    *,
    name: str,
    return_code: int,
    action: str = "stopping all loops",
) -> None:
    _print_status_line(
        tag="runtime",
        style="red",
        message=f"{name} exited",
        detail=f"code={return_code}; {action}",
    )


def print_process_shutdown(message: str) -> None:
    _print_status_line(tag="runtime", style="yellow", message=message, detail="shutting down children")


def print_network_skip(*, scope: str, error: object) -> None:
    _print_status_line(
        tag=scope,
        style="yellow",
        message="cycle skipped",
        detail=f"transient network error: {error}",
    )


def print_pages_updated(*, scope: str, paths: list[Path]) -> None:
    if not paths:
        return
    page_names = ", ".join(_page_label(path) for path in paths)
    _print_status_line(
        tag=scope,
        style="blue",
        message=f"frontend updated ({len(paths)})",
        detail=page_names,
    )


def print_spot_cycle(result: Any) -> None:
    if result.skipped:
        rows = [
            ("System", "SPOT"),
            ("State", "SKIPPED"),
            ("Market", "BTCUSDT 15m"),
            ("Reason", result.skip_reason or "unknown"),
            ("Candle close", _cycle_close_text(result.cycle_note)),
        ]
        _print_runtime_table(title="Spot Cycle", rows=rows, accent="yellow")
        return

    signal_result = result.signal_result
    signal = signal_result.signal if signal_result else None
    score = getattr(signal, "score", None)
    threshold = getattr(signal, "threshold", None)
    signal_side = _enum_text(getattr(signal, "side", None), fallback="NO_DATA")
    failed_gates = _failed_gate_names(getattr(signal, "gates", None))
    passed_gates = _passed_gate_names(getattr(signal, "gates", None))
    status = "SKIPPED" if result.skipped else "OK"

    rows = [
        ("System", "SPOT"),
        ("State", status),
        ("Market", "BTCUSDT 15m"),
        ("Mode", "simulation spot"),
        ("Signal", signal_side),
        ("BUY score", _score_text(score=score, threshold=threshold)),
        ("Passed BUY gates", passed_gates or "none"),
        ("Failed BUY gates", failed_gates or "none"),
        ("Candle close", _cycle_close_text(result.cycle_note)),
        ("Storage", "SQLite market-data + trading databases"),
    ]
    if result.skip_reason:
        rows.append(("Skip", result.skip_reason))
    _print_runtime_table(title="Spot Cycle", rows=rows, accent=_signal_style(signal_side))


def print_futures_cycle(*, profile: Any, result: Any) -> None:
    summary = result.summary
    if result.skipped or summary is None:
        rows = [
            ("System", "FUTURES"),
            ("State", "SKIPPED"),
            ("Market", f"{profile.symbol} {profile.timeframe}"),
            ("Mode", f"{profile.mode} x{profile.leverage} {profile.margin_mode}"),
            ("Reason", result.skip_reason or "unknown"),
            ("Candle close", _cycle_close_text(result.cycle_note)),
        ]
        _print_runtime_table(title="Futures Cycle", rows=rows, accent="yellow")
        return

    direction_scores = getattr(summary, "direction_scores", {}) or {}
    long_score = direction_scores.get("long")
    short_score = direction_scores.get("short")
    failed_gates = ", ".join(name for name, passed in summary.gates.items() if not passed)
    passed_gates = ", ".join(name for name, passed in summary.gates.items() if passed)
    rows = [
        ("System", "FUTURES"),
        ("State", "OK"),
        ("Market", f"{profile.symbol} {profile.timeframe}"),
        ("Mode", f"{profile.mode} x{profile.leverage} {profile.margin_mode}"),
        ("Signal", summary.signal),
        ("Selected score", _score_text(score=summary.score, threshold=summary.threshold)),
        ("LONG score", _score_text(score=long_score, threshold=summary.threshold)),
        ("SHORT score", _score_text(score=short_score, threshold=summary.threshold)),
        ("Entry status", _entry_status_text(summary)),
        ("Main blocker", _main_blocker_text(summary)),
        ("Selected passed gates", passed_gates or "none"),
        ("Selected failed gates", failed_gates or "none"),
        ("Candle close", _cycle_close_text(result.cycle_note)),
        ("Storage", "SQLite market-data + trading databases"),
    ]
    _print_runtime_table(title="Futures Cycle", rows=rows, accent=_signal_style(summary.signal))
    print_pages_updated(scope="futures", paths=list(result.updated_page_paths))
    print_hedge_replay(result)


def print_hedge_replay(result: Any) -> None:
    report_path = getattr(result, "hedge_report_path", None)
    page_path = getattr(result, "hedge_page_path", None)
    report = _load_json_dict(report_path) if isinstance(report_path, Path) and report_path.exists() else {}
    report_label = _artifact_label(report_path) if report else "SQLite trading database"
    if not report:
        from platform_v2.shared.backend.runtime_store.hedge import (
            HEDGE_DAILY_SUMMARIES_FAMILY,
            load_latest_document,
        )

        summary = load_latest_document(HEDGE_DAILY_SUMMARIES_FAMILY)
        if isinstance(summary, list):
            summary = summary[-1] if summary else None
        if not isinstance(summary, dict):
            return
        report = {
            "mode": summary.get("mode"),
            "source_counts": {
                "hedge_entries_accepted": summary.get("hedge_entries_accepted"),
                "opened_futures_events": summary.get("opened_futures_events"),
            },
            "final_snapshot": {
                "equity_usdt": summary.get("equity_usdt"),
                "estimated_close_equity_usdt": summary.get("estimated_close_equity_usdt"),
                "available_capital_usdt": summary.get("available_capital_usdt"),
                "used_margin_usdt": summary.get("used_margin_usdt"),
                "unrealized_pnl_usdt": summary.get("unrealized_pnl_usdt"),
                "long_basket": summary.get("long_basket"),
                "short_basket": summary.get("short_basket"),
            },
            "decision_summary": {"can_open_next_entry": summary.get("can_open_next_entry")},
        }
    source_counts = report.get("source_counts") if isinstance(report.get("source_counts"), dict) else {}
    final_snapshot = report.get("final_snapshot") if isinstance(report.get("final_snapshot"), dict) else {}
    decision_summary = (
        report.get("decision_summary") if isinstance(report.get("decision_summary"), dict) else {}
    )
    long_basket = (
        final_snapshot.get("long_basket") if isinstance(final_snapshot.get("long_basket"), dict) else {}
    )
    short_basket = (
        final_snapshot.get("short_basket") if isinstance(final_snapshot.get("short_basket"), dict) else {}
    )

    rows = [
        ("System", "FUTURES_HEDGE"),
        ("State", "OK"),
        ("Mode", str(report.get("mode") or "paper_replay")),
        ("Entries", _count_text(source_counts.get("hedge_entries_accepted"))),
        ("Opened futures events", _count_text(source_counts.get("opened_futures_events"))),
        ("Open equity", _money_text(final_snapshot.get("equity_usdt"))),
        ("If closed now", _money_text(final_snapshot.get("estimated_close_equity_usdt"))),
        ("Available", _money_text(final_snapshot.get("available_capital_usdt"))),
        ("Used margin", _money_text(final_snapshot.get("used_margin_usdt"))),
        ("Unrealized", _money_text(final_snapshot.get("unrealized_pnl_usdt"))),
        ("LONG basket", _basket_text(long_basket)),
        ("SHORT basket", _basket_text(short_basket)),
        ("Can open next", _yes_no_text(decision_summary.get("can_open_next_entry"))),
        ("Storage", report_label),
    ]
    _print_runtime_table(title="Hedge Replay", rows=rows, accent="cyan")
    if isinstance(page_path, Path):
        print_pages_updated(scope="hedge", paths=[page_path])


def _print_runtime_table(*, title: str, rows: list[tuple[str, str]], accent: str) -> None:
    stamp = datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC")
    if _CONSOLE is None or Table is None:
        body = " | ".join(f"{key}={value}" for key, value in rows)
        print(f"[{stamp}] {title}: {body}", flush=True)
        return

    table = Table(
        title=f"{title} [{stamp}]",
        title_style=f"bold {accent}",
        title_justify="left",
        show_header=False,
        show_lines=False,
        box=None,
        pad_edge=False,
    )
    table.add_column("Metric", style="dim", no_wrap=True)
    table.add_column("Value", overflow="fold")
    for key, value in rows:
        table.add_row(key, _styled_value(key=key, value=value))
    _CONSOLE.print(table)
    _CONSOLE.print()


def _print_status_line(*, tag: str, style: str, message: str, detail: str) -> None:
    stamp = datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC")
    if _CONSOLE is None:
        print(f"[{stamp}] [{tag}] {message} | {detail}", flush=True)
        return
    if Text is None:
        _CONSOLE.print(f"{stamp} [{tag}] {message} | {detail}")
        return
    line = Text()
    line.append(stamp, style="dim")
    line.append(" ")
    line.append(f"[{tag}]", style=f"bold {style}")
    line.append(f" {message}")
    line.append(f" | {detail}", style="dim")
    _CONSOLE.print(line)
    _CONSOLE.print()


def _styled_value(*, key: str, value: str) -> Any:
    if Text is None:
        return value
    if key in {"State", "Permission", "Entry status"}:
        if "OK" in value or "ALLOWED" in value:
            return Text(value, style="green")
        if "SKIPPED" in value or "DENIED" in value:
            return Text(value, style="yellow")
    if key == "Main blocker" and value not in {"--", "allowed"}:
        return Text(value, style="yellow")
    if key == "Signal":
        return Text(value, style=_signal_style(value))
    if key in {"Net PnL", "Unrealized", "Open equity", "If closed now", "Available"}:
        numeric = _numeric_from_text(value)
        if numeric is None:
            return value
        return Text(value, style="green" if numeric >= 0 else "red")
    if key in {"Used margin", "Entries", "Opened futures events"} and value != "--":
        return Text(value, style="cyan")
    if key in {"LONG basket"} and value != "--":
        return Text(value, style="green")
    if key in {"SHORT basket"} and value != "--":
        return Text(value, style="red")
    if key == "Can open next":
        return Text(value, style="green" if value.upper() == "YES" else "yellow")
    key_lower = key.lower()
    if "failed" in key_lower and "gates" in key_lower and value != "none":
        return Text(value, style="yellow")
    if "passed" in key_lower and "gates" in key_lower and value != "none":
        return Text(value, style="green")
    return value


def _signal_style(signal_side: str) -> str:
    normalized = signal_side.upper()
    if normalized in {"BUY", "LONG"}:
        return "green"
    if normalized in {"SELL", "SHORT"}:
        return "red"
    if normalized in {"NO_SIGNAL", "DENIED", "SKIPPED"}:
        return "yellow"
    return "cyan"


def _score_text(*, score: object, threshold: object) -> str:
    if isinstance(score, (int, float)) and isinstance(threshold, (int, float)):
        return f"{score:.2f}/{threshold:.2f}"
    return "--"


def _money_text(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.2f} USDT"
    return "--"


def _count_text(value: object) -> str:
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value))
    return "--"


def _yes_no_text(value: object) -> str:
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return "--"


def _basket_text(basket: dict[str, Any]) -> str:
    entries = basket.get("entries", basket.get("count"))
    margin = basket.get("margin_usdt")
    pnl = basket.get("unrealized_pnl_usdt", basket.get("unrealized_pnl"))
    if not isinstance(entries, (int, float)) or not isinstance(margin, (int, float)):
        return "--"
    if isinstance(pnl, (int, float)):
        return f"{int(entries)} entries | {margin:,.2f} margin | {pnl:+,.2f} PnL"
    return f"{int(entries)} entries | {margin:,.2f} margin"


def _numeric_from_text(value: str) -> float | None:
    try:
        return float(value.replace("USDT", "").replace(",", "").strip())
    except ValueError:
        return None


def _load_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _entry_status_text(summary: Any) -> str:
    status = str(getattr(summary, "permission_status", "") or "").upper()
    if status == "ALLOWED":
        return "ALLOWED"
    if status == "DENIED":
        return "DENIED"
    return status or "--"


def _main_blocker_text(summary: Any) -> str:
    reason = str(getattr(summary, "permission_reason", "") or "")
    if not reason or reason == "allowed":
        return "--"
    label_map = {
        "entry_quality_block": "Entry timing blocked",
        "short_market_plan_zone_block": "Outside short zone",
        "long_entry_location_block": "Long into resistance",
        "proximity_block": "Too close to recent entry",
        "cooldown_block": "Cooldown active",
        "signal_block": "No actionable setup",
        "capital_block": "Capital limit",
        "exposure_block": "Exposure limit",
        "position_slots_block": "Position limit",
        "direction_position_slots_block": "Direction limit",
        "weak_open_position_block": "Weak open position",
        "duplicate_block": "Duplicate position",
        "liquidation_buffer_block": "Liquidation buffer",
        "manual_block": "Manual block",
        "no_data": "Missing data",
    }
    return label_map.get(reason, reason.replace("_", " ").title())


def _enum_text(value: object, *, fallback: str) -> str:
    text = getattr(value, "value", None)
    if text is None:
        return fallback
    return str(text)


def _failed_gate_names(gates: object) -> str:
    if gates is None:
        return ""
    if isinstance(gates, dict):
        return ", ".join(str(name) for name, passed in gates.items() if not bool(passed))
    if is_dataclass(gates):
        return ", ".join(
            field.name
            for field in fields(gates)
            if not bool(getattr(gates, field.name))
        )
    return ""


def _passed_gate_names(gates: object) -> str:
    if gates is None:
        return ""
    if isinstance(gates, dict):
        return ", ".join(str(name) for name, passed in gates.items() if bool(passed))
    if is_dataclass(gates):
        return ", ".join(
            field.name
            for field in fields(gates)
            if bool(getattr(gates, field.name))
        )
    return ""


def _cycle_close_text(value: object) -> str:
    text = str(value or "").strip()
    if not text or not text.isdigit():
        return text or "--"
    try:
        timestamp_ms = int(text)
    except ValueError:
        return text
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _artifact_label(path: Path) -> str:
    parent = path.parent.name
    grandparent = path.parent.parent.name
    if grandparent in {
        "candles",
        "candles_futures",
        "orderflow",
        "orderflow_futures",
        "indicator_snapshots",
        "indicator_snapshots_futures",
    }:
        return f"{grandparent}/{parent}/{path.name}"
    if path.name in {"1m.json", "5m.json", "15m.json", "4h.json"}:
        return f"{parent}/{path.name}"
    if parent in {"metrics", "cycle_runs", "daily_summaries"}:
        return f"{parent}/{path.name}"
    return f"{parent}/{path.name}"


def _page_label(path: Path | None) -> str:
    if path is None:
        return "--"
    parts = path.parts
    if "futures_hedge" in parts and path.name == "index.html":
        return "overview_hedge"
    if len(parts) >= 2 and path.name == "index.html":
        return parts[-2]
    return path.name
