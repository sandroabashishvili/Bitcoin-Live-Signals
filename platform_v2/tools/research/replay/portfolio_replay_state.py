"""Shared portfolio state and runtime-fidelity helpers for research replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from platform_v2.tools.research.paths import ResearchDataRoots
from platform_v2.tools.research.replay.candidate_signal_outcome_replay import _stats
from platform_v2.tools.research.replay.historical_component_replay import _float, _load_json


@dataclass
class OpenPosition:
    side: str
    entry_timestamp_ms: int
    entry: float
    margin: float
    entry_fee: float
    outcome: dict[str, Any]


def load_family_rows(directory: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        payload = _load_json(path)
        if not isinstance(payload, list):
            continue
        rows.extend(row for row in payload if isinstance(row, dict))
    return rows


def close_due_positions(
    *,
    open_positions: list[OpenPosition],
    timestamp_ms: int,
) -> tuple[list[OpenPosition], list[dict[str, Any]]]:
    remaining: list[OpenPosition] = []
    closed: list[dict[str, Any]] = []
    for position in open_positions:
        outcome = position.outcome
        resolution = str(outcome.get("resolution") or "")
        exit_timestamp_ms = int(outcome.get("exit_timestamp_ms") or 0)
        if resolution != "DATA_END" and exit_timestamp_ms <= timestamp_ms:
            closed.append(outcome)
        else:
            remaining.append(position)
    return remaining, closed


def portfolio_stats(
    *,
    opened: list[dict[str, Any]],
    closed: list[dict[str, Any]],
    open_positions: list[OpenPosition],
    split_timestamp_ms: int,
    period_origin_timestamp_ms: int,
) -> dict[str, Any]:
    marked = [*closed, *(position.outcome for position in open_positions)]
    train = [row for row in closed if int(row.get("entry_timestamp_ms") or 0) <= split_timestamp_ms]
    test = [row for row in closed if int(row.get("entry_timestamp_ms") or 0) > split_timestamp_ms]
    sides = sorted({str(row.get("side") or "UNKNOWN") for row in [*closed, *marked]})
    by_side = {
        side: {
            "closed": _stats([row for row in closed if str(row.get("side") or "UNKNOWN") == side]),
            "train": _stats([row for row in train if str(row.get("side") or "UNKNOWN") == side]),
            "test": _stats([row for row in test if str(row.get("side") or "UNKNOWN") == side]),
        }
        for side in sides
    }
    period_ms = 7 * 24 * 60 * 60 * 1000
    rolling_groups: dict[int, list[dict[str, Any]]] = {}
    for row in closed:
        entry_timestamp_ms = int(row.get("entry_timestamp_ms") or 0)
        bucket = max(0, (entry_timestamp_ms - period_origin_timestamp_ms) // period_ms)
        rolling_groups.setdefault(bucket, []).append(row)
    rolling_7d: list[dict[str, Any]] = []
    for bucket, rows in sorted(rolling_groups.items()):
        start = datetime.fromtimestamp(
            (period_origin_timestamp_ms + bucket * period_ms) / 1000,
            tz=UTC,
        )
        end = start + timedelta(days=7)
        rolling_7d.append(
            {
                "bucket": bucket,
                "start_date": start.date().isoformat(),
                "end_date_exclusive": end.date().isoformat(),
                "all": _stats(rows),
                "by_side": {
                    side: _stats([row for row in rows if str(row.get("side") or "UNKNOWN") == side])
                    for side in sorted({str(row.get("side") or "UNKNOWN") for row in rows})
                },
            }
        )
    return {
        "opened_positions": len(opened),
        "closed_positions": len(closed),
        "open_positions_at_data_end": len(open_positions),
        "closed_stats": _stats(closed),
        "marked_to_data_end_stats": _stats(marked),
        "chronological_split_timestamp_ms": split_timestamp_ms,
        "chronological_train": _stats(train),
        "chronological_test": _stats(test),
        "by_side": by_side,
        "rolling_7d": rolling_7d,
    }


def _timestamp_from_spot_opened_at(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    try:
        parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None
    return int(parsed.timestamp() * 1000) + 999


def actual_open_timestamps(roots: ResearchDataRoots) -> dict[str, list[int]]:
    spot_latest: dict[str, dict[str, Any]] = {}
    for row in load_family_rows(roots.spot / "positions"):
        position_id = str(row.get("position_id") or "")
        if position_id:
            spot_latest[position_id] = row
    spot = sorted(
        timestamp
        for timestamp in (
            _timestamp_from_spot_opened_at(row.get("opened_at")) for row in spot_latest.values()
        )
        if timestamp is not None
    )

    futures_by_side: dict[str, list[int]] = {"LONG": [], "SHORT": []}
    seen: set[str] = set()
    for row in load_family_rows(roots.futures / "futures_position_events"):
        if str(row.get("event") or "").upper() != "OPENED":
            continue
        position_id = str(row.get("position_id") or "")
        if not position_id or position_id in seen:
            continue
        seen.add(position_id)
        side = str(row.get("side") or "").upper()
        if side in futures_by_side:
            futures_by_side[side].append(int(row.get("opened_at_ms") or row.get("timestamp_ms") or 0))
    return {
        "SPOT": spot,
        "LONG": sorted(futures_by_side["LONG"]),
        "SHORT": sorted(futures_by_side["SHORT"]),
    }


def actual_closed_performance(
    roots: ResearchDataRoots,
    *,
    evaluation_start_ms: int | None = None,
) -> dict[str, dict[str, Any]]:
    spot_latest: dict[str, dict[str, Any]] = {}
    for row in load_family_rows(roots.spot / "positions"):
        position_id = str(row.get("position_id") or "")
        if position_id:
            spot_latest[position_id] = row
    spot_closed = [
        row
        for row in spot_latest.values()
        if str(row.get("status") or "").upper() == "CLOSED"
        and (
            evaluation_start_ms is None
            or (_timestamp_from_spot_opened_at(row.get("opened_at")) or 0) > evaluation_start_ms
        )
    ]

    futures_closed: dict[str, dict[str, Any]] = {}
    for row in load_family_rows(roots.futures / "futures_position_events"):
        if str(row.get("event") or "").upper() != "CLOSED":
            continue
        position_id = str(row.get("position_id") or "")
        if position_id:
            opened_at_ms = int(row.get("opened_at_ms") or 0)
            if evaluation_start_ms is None or opened_at_ms > evaluation_start_ms:
                futures_closed[position_id] = row

    def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        net_pnl = round(sum(_float(row.get("net_pnl")) for row in rows), 2)
        wins = sum(_float(row.get("net_pnl")) > 0 for row in rows)
        force_close_events = sum(
            bool(row.get("was_force_closed"))
            or str(row.get("exit_reason") or "").lower() == "force_close"
            for row in rows
        )
        return {
            "closed_positions": len(rows),
            "net_pnl": net_pnl,
            "wins": wins,
            "win_rate": round(wins / len(rows) * 100.0, 2) if rows else 0.0,
            "force_close_events": force_close_events,
        }

    return {
        "SPOT": summary(spot_closed),
        "LONG": summary(
            [row for row in futures_closed.values() if str(row.get("side") or "").upper() == "LONG"]
        ),
        "SHORT": summary(
            [row for row in futures_closed.values() if str(row.get("side") or "").upper() == "SHORT"]
        ),
    }


def validation(predicted: Iterable[int], actual: Iterable[int]) -> dict[str, Any]:
    predicted_set = {int(value) for value in predicted}
    actual_set = {int(value) for value in actual}
    matches = predicted_set & actual_set
    return {
        "predicted": len(predicted_set),
        "actual": len(actual_set),
        "exact_timestamp_matches": len(matches),
        "precision_pct": round(len(matches) / len(predicted_set) * 100.0, 2) if predicted_set else 0.0,
        "recall_pct": round(len(matches) / len(actual_set) * 100.0, 2) if actual_set else 0.0,
        "predicted_only": len(predicted_set - actual_set),
        "actual_only": len(actual_set - predicted_set),
    }
