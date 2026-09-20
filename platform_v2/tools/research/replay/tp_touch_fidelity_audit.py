"""Audit recorded Spot/Futures exits against persisted closed-candle wicks."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT, ResearchDataRoots
from platform_v2.tools.research.replay.portfolio_replay_state import load_family_rows


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _candle_gap_count(candles: list[dict[str, Any]]) -> int:
    open_times = sorted(
        {int(row.get("timestamp") or 0) for row in candles if int(row.get("timestamp") or 0) > 0}
    )
    return sum(current - previous != 5 * 60 * 1000 for previous, current in zip(open_times, open_times[1:]))


def _timestamp_ms(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    try:
        parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return 0
    return int(parsed.timestamp() * 1000) + 999


def _normalized_exit_reason(row: dict[str, Any]) -> str:
    value = str(row.get("exit_reason") or row.get("outcome") or "").strip().upper()
    if value in {"TP", "TP_HIT"}:
        return "TP"
    if value in {"SL", "SL_HIT"}:
        return "SL"
    if bool(row.get("was_force_closed")) or "FORCE" in value:
        return "FORCE_CLOSE"
    if str(row.get("status") or "").upper() == "OPEN":
        return "OPEN"
    return value or "UNKNOWN"


def _first_touch(
    *,
    side: str,
    opened_at_ms: int,
    closed_at_ms: int,
    take_profit: float,
    stop_loss: float,
    candles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for candle in candles:
        candle_close_ms = int(candle.get("close_time") or 0)
        if candle_close_ms <= opened_at_ms:
            continue
        if closed_at_ms > 0 and candle_close_ms > closed_at_ms:
            break
        high = float(candle.get("high") or 0.0)
        low = float(candle.get("low") or 0.0)
        if side == "SHORT":
            tp_hit = low <= take_profit
            sl_hit = high >= stop_loss
        else:
            tp_hit = high >= take_profit
            sl_hit = low <= stop_loss
        if not tp_hit and not sl_hit:
            continue
        expected = "BOTH" if tp_hit and sl_hit else "TP" if tp_hit else "SL"
        return {
            "expected": expected,
            "candle_open_ms": int(candle.get("timestamp") or 0),
            "candle_close_ms": candle_close_ms,
            "high": high,
            "low": low,
            "close": float(candle.get("close") or 0.0),
            "tp_hit": tp_hit,
            "sl_hit": sl_hit,
        }
    return None


def _closest_tp_approach(
    *,
    side: str,
    opened_at_ms: int,
    closed_at_ms: int,
    take_profit: float,
    candles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    relevant = [
        candle
        for candle in candles
        if int(candle.get("close_time") or 0) > opened_at_ms
        and (closed_at_ms <= 0 or int(candle.get("close_time") or 0) <= closed_at_ms)
    ]
    if not relevant or take_profit <= 0:
        return None
    if side == "SHORT":
        candle = min(relevant, key=lambda row: float(row.get("low") or float("inf")))
        favorable_price = float(candle.get("low") or 0.0)
        distance_pct = (favorable_price - take_profit) / take_profit * 100.0
    else:
        candle = max(relevant, key=lambda row: float(row.get("high") or 0.0))
        favorable_price = float(candle.get("high") or 0.0)
        distance_pct = (take_profit - favorable_price) / take_profit * 100.0
    return {
        "favorable_price": favorable_price,
        "distance_to_tp_pct": round(distance_pct, 6),
        "candle_close_ms": int(candle.get("close_time") or 0),
    }


def _audit_position(
    *,
    market: str,
    opened: dict[str, Any],
    latest: dict[str, Any],
    candles: list[dict[str, Any]],
) -> dict[str, Any]:
    execution = opened.get("execution") if isinstance(opened.get("execution"), dict) else {}
    position_id = str(opened.get("position_id") or latest.get("position_id") or "")
    side = str(opened.get("side") or latest.get("side") or "BUY").upper()
    opened_at_ms = int(opened.get("opened_at_ms") or 0) or _timestamp_ms(opened.get("opened_at"))
    closed_at_ms = int(latest.get("timestamp_ms") or 0) if str(latest.get("event") or "").upper() == "CLOSED" else 0
    if closed_at_ms <= 0:
        closed_at_ms = _timestamp_ms(latest.get("closed_at"))
    take_profit = float(
        opened.get("tp_price")
        or execution.get("take_profit")
        or (latest.get("execution") or {}).get("take_profit")
        or 0.0
    )
    stop_loss = float(
        opened.get("sl_price")
        or execution.get("stop_loss")
        or (latest.get("execution") or {}).get("stop_loss")
        or 0.0
    )
    touch = _first_touch(
        side=side,
        opened_at_ms=opened_at_ms,
        closed_at_ms=closed_at_ms,
        take_profit=take_profit,
        stop_loss=stop_loss,
        candles=candles,
    )
    recorded = _normalized_exit_reason(latest)
    expected = str((touch or {}).get("expected") or "NO_TOUCH")
    closest_tp = _closest_tp_approach(
        side=side,
        opened_at_ms=opened_at_ms,
        closed_at_ms=closed_at_ms,
        take_profit=take_profit,
        candles=candles,
    )
    closest_tp_before_recorded_close = None
    if recorded == "TP" and closed_at_ms > 0:
        closest_tp_before_recorded_close = _closest_tp_approach(
            side=side,
            opened_at_ms=opened_at_ms,
            closed_at_ms=closed_at_ms - 1,
            take_profit=take_profit,
            candles=candles,
        )
    issue = ""
    touch_close_ms = int((touch or {}).get("candle_close_ms") or 0)
    delay_ms = 0
    if expected == "BOTH":
        issue = "same_5m_candle_touched_tp_and_sl"
    elif expected in {"TP", "SL"} and recorded != expected:
        issue = f"recorded_{recorded.lower()}_after_{expected.lower()}_touch"
    elif (
        expected in {"TP", "SL"}
        and recorded == expected
        and closed_at_ms > touch_close_ms > 0
    ):
        delay_ms = closed_at_ms - touch_close_ms
        issue = f"delayed_recorded_{expected.lower()}_after_first_touch"
    elif expected == "NO_TOUCH" and recorded in {"TP", "SL"}:
        issue = "recorded_exit_missing_from_persisted_5m_candles"
    return {
        "market": market,
        "position_id": position_id,
        "side": side,
        "opened_at_ms": opened_at_ms,
        "closed_at_ms": closed_at_ms,
        "entry_price": float(opened.get("entry_price") or execution.get("entry_price") or 0.0),
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "recorded_exit": recorded,
        "first_touch": touch,
        "recording_delay_ms": delay_ms,
        "recording_delay_minutes": round(delay_ms / 60_000, 3),
        "closest_tp_approach": closest_tp,
        "closest_tp_before_recorded_close": closest_tp_before_recorded_close,
        "issue": issue,
    }


def build_report(snapshot_root: Path) -> dict[str, Any]:
    roots = ResearchDataRoots.from_snapshot(snapshot_root)
    spot_candles = _load_json_rows(roots.spot / "candles" / "BTCUSDT" / "5m.json")
    futures_candles = _load_json_rows(
        roots.futures / "candles_futures" / "BTCUSDT" / "candles_5m.json"
    )

    spot_history: dict[str, list[dict[str, Any]]] = {}
    for row in load_family_rows(roots.spot / "positions"):
        position_id = str(row.get("position_id") or "")
        if position_id:
            spot_history.setdefault(position_id, []).append(row)
    audits = [
        _audit_position(
            market="SPOT",
            opened=rows[0],
            latest=rows[-1],
            candles=spot_candles,
        )
        for rows in spot_history.values()
    ]

    futures_history: dict[str, list[dict[str, Any]]] = {}
    for row in load_family_rows(roots.futures / "futures_position_events"):
        position_id = str(row.get("position_id") or "")
        if position_id:
            futures_history.setdefault(position_id, []).append(row)
    audits.extend(
        _audit_position(
            market="FUTURES",
            opened=next(
                (row for row in rows if str(row.get("event") or "").upper() == "OPENED"),
                rows[0],
            ),
            latest=next(
                (row for row in reversed(rows) if str(row.get("event") or "").upper() == "CLOSED"),
                rows[-1],
            ),
            candles=futures_candles,
        )
        for rows in futures_history.values()
    )
    suspicious = [row for row in audits if row["issue"]]
    near_tp_without_hit = sorted(
        (
            row
            for row in audits
            if row["recorded_exit"] != "TP"
            and row.get("closest_tp_approach")
            and 0.0 < float(row["closest_tp_approach"]["distance_to_tp_pct"]) <= 0.1
        ),
        key=lambda row: float(row["closest_tp_approach"]["distance_to_tp_pct"]),
    )
    near_tp_before_later_hit = sorted(
        (
            row
            for row in audits
            if row["recorded_exit"] == "TP"
            and row.get("closest_tp_before_recorded_close")
            and 0.0
            < float(row["closest_tp_before_recorded_close"]["distance_to_tp_pct"])
            <= 0.1
        ),
        key=lambda row: float(
            row["closest_tp_before_recorded_close"]["distance_to_tp_pct"]
        ),
    )
    return {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": str(snapshot_root.expanduser().resolve()),
        "method": "persisted_5m_wick_vs_recorded_exit",
        "rules": {
            "long": "TP when high >= TP; SL when low <= SL",
            "short": "TP when low <= TP; SL when high >= SL",
            "same_candle": "Reported as ambiguous because 5m data cannot prove which level came first.",
        },
        "counts": {
            "positions": len(audits),
            "spot": sum(row["market"] == "SPOT" for row in audits),
            "futures": sum(row["market"] == "FUTURES" for row in audits),
            "suspicious": len(suspicious),
            "same_candle_ambiguous": sum(
                row["issue"] == "same_5m_candle_touched_tp_and_sl" for row in suspicious
            ),
            "missed_tp_touch": sum("after_tp_touch" in row["issue"] for row in suspicious),
            "delayed_tp_close": sum(
                row["issue"] == "delayed_recorded_tp_after_first_touch" for row in suspicious
            ),
            "delayed_sl_close": sum(
                row["issue"] == "delayed_recorded_sl_after_first_touch" for row in suspicious
            ),
            "near_tp_without_hit_within_0_1pct": len(near_tp_without_hit),
            "near_tp_before_later_hit_within_0_1pct": len(near_tp_before_later_hit),
            "spot_5m_candle_gaps": _candle_gap_count(spot_candles),
            "futures_5m_candle_gaps": _candle_gap_count(futures_candles),
        },
        "suspicious": suspicious,
        "near_tp_without_hit": near_tp_without_hit,
        "near_tp_before_later_hit": near_tp_before_later_hit,
    }


def _markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "# TP Touch Fidelity Audit",
        "",
        f"Generated: `{report['generated_at_utc']} UTC`",
        f"Snapshot: `{report['snapshot']}`",
        "",
        f"- Positions: `{counts['positions']}`",
        f"- Suspicious: `{counts['suspicious']}`",
        f"- Missed TP touch candidates: `{counts['missed_tp_touch']}`",
        f"- TP recorded later than first touch: `{counts['delayed_tp_close']}`",
        f"- SL recorded later than first touch: `{counts['delayed_sl_close']}`",
        f"- Same-5m-candle TP/SL ambiguity: `{counts['same_candle_ambiguous']}`",
        f"- Near TP without hit (within 0.1%): `{counts['near_tp_without_hit_within_0_1pct']}`",
        f"- Near TP before a later real hit (within 0.1%): `{counts['near_tp_before_later_hit_within_0_1pct']}`",
        f"- Spot/Futures 5m candle gaps: `{counts['spot_5m_candle_gaps']}/{counts['futures_5m_candle_gaps']}`",
        "",
        "| Market | Position | Side | Recorded | First touch | Issue | First touch close | Recorded close | Delay min | High | Low |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["suspicious"]:
        touch = row.get("first_touch") or {}
        lines.append(
            f"| {row['market']} | {row['position_id']} | {row['side']} | "
            f"{row['recorded_exit']} | {touch.get('expected', 'NO_TOUCH')} | {row['issue']} | "
            f"{touch.get('candle_close_ms', '')} | {row['closed_at_ms']} | "
            f"{row['recording_delay_minutes']} | {touch.get('high', '')} | {touch.get('low', '')} |"
        )
    if report["near_tp_without_hit"]:
        lines.extend(
            [
                "",
                "## Near TP Without A Recorded Touch",
                "",
                "| Market | Position | Side | Recorded | TP | Closest price | Distance % | Candle close |",
                "|---|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for row in report["near_tp_without_hit"]:
            closest = row["closest_tp_approach"]
            lines.append(
                f"| {row['market']} | {row['position_id']} | {row['side']} | {row['recorded_exit']} | "
                f"{row['take_profit']} | {closest['favorable_price']} | "
                f"{closest['distance_to_tp_pct']} | {closest['candle_close_ms']} |"
            )
    if report["near_tp_before_later_hit"]:
        lines.extend(
            [
                "",
                "## Near TP Before A Later Recorded Hit",
                "",
                "| Market | Position | Side | TP | Earlier closest price | Distance % | Earlier candle close | Recorded close |",
                "|---|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for row in report["near_tp_before_later_hit"]:
            closest = row["closest_tp_before_recorded_close"]
            lines.append(
                f"| {row['market']} | {row['position_id']} | {row['side']} | "
                f"{row['take_profit']} | {closest['favorable_price']} | "
                f"{closest['distance_to_tp_pct']} | {closest['candle_close_ms']} | "
                f"{row['closed_at_ms']} |"
            )
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
    json_path = output_root / f"tp_touch_fidelity_audit_{stamp}.json"
    markdown_path = output_root / f"tp_touch_fidelity_audit_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit recorded exits against 5m candle wicks.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    args = parser.parse_args()
    report = build_report(args.snapshot)
    for path in write_report(report, args.output_root.expanduser().resolve()):
        print(f"[OK] {path}")
    print(json.dumps(report["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
