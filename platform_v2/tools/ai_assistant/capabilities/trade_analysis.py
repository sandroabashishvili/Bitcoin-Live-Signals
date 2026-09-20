"""Trade analysis capability for closed trades and entry attribution."""

from __future__ import annotations

from typing import Any

from platform_v2.tools.ai_assistant.runtime_readers import family_rows

from .contracts import CapabilityAnswer


def answer_trade_analysis(market: str | None = None) -> CapabilityAnswer:
    markets = [market] if market in ("futures", "spot") else ["futures", "spot"]
    sections = [_format_market_trades(selected) for selected in markets]
    return CapabilityAnswer("trade_analysis", "\n\n".join(sections))


def answer_side_performance() -> CapabilityAnswer:
    rows = _futures_trade_rows()
    if not rows:
        return CapabilityAnswer("trade_analysis", "No Futures trade audit rows found.")
    stats = _side_stats(rows)
    lines = [
        "Futures LONG vs SHORT performance",
        f"Audit sample size: {len(rows)}",
        "Side stats:",
    ]
    for side in ("LONG", "SHORT"):
        item = stats.get(side, _empty_stats())
        lines.append(
            f"- {side}: count={item['count']}, wins={item['wins']}, losses={item['losses']}, win_rate={item['win_rate']}%, net_pnl={round(item['net_pnl'], 4)}"
        )
    long_net = stats.get("LONG", _empty_stats())["net_pnl"]
    short_net = stats.get("SHORT", _empty_stats())["net_pnl"]
    if short_net > long_net:
        lines.append("Conclusion: SHORT currently performs better based only on Futures trade audit net PnL.")
    elif long_net > short_net:
        lines.append("Conclusion: LONG currently performs better based only on Futures trade audit net PnL.")
    else:
        lines.append("Conclusion: LONG and SHORT are tied on current audit net PnL.")
    lines.append("Source: smartsignalhub_trading.sqlite3 / futures_trade_entry_audits")
    return CapabilityAnswer("trade_analysis", "\n".join(lines))


def answer_side_outperformance() -> CapabilityAnswer:
    rows = _futures_trade_rows()
    if not rows:
        return CapabilityAnswer("trade_analysis", "No Futures trade audit rows found.")
    stats = _side_stats(rows)
    lines = [answer_side_performance().text, "Evidence-only explanation:"]
    long_item = stats.get("LONG", _empty_stats())
    short_item = stats.get("SHORT", _empty_stats())
    if short_item["net_pnl"] > long_item["net_pnl"]:
        lines.append(
            f"- SHORT net PnL ({round(short_item['net_pnl'], 4)}) is higher than LONG net PnL ({round(long_item['net_pnl'], 4)})."
        )
    if short_item["win_rate"] > long_item["win_rate"]:
        lines.append(
            f"- SHORT win rate ({short_item['win_rate']}%) is higher than LONG win rate ({long_item['win_rate']}%)."
        )
    if long_item["count"] == 0 or short_item["count"] == 0 or len(rows) < 10:
        lines.append(f"- Sample size is small ({len(rows)} audited trades), so this is early evidence, not a final strategy verdict.")
    return CapabilityAnswer("trade_analysis", "\n".join(lines))


def answer_biggest_weakness() -> CapabilityAnswer:
    rows = _futures_trade_rows()
    stats = _side_stats(rows)
    lines = [
        "Biggest Futures weakness from current audit evidence",
        f"Trade audit sample size: {len(rows)}",
    ]
    long_item = stats.get("LONG", _empty_stats())
    short_item = stats.get("SHORT", _empty_stats())
    if long_item["net_pnl"] < 0 and short_item["net_pnl"] > 0:
        lines.append(
            f"- Main weakness: LONG side is negative while SHORT side is positive. LONG net_pnl={round(long_item['net_pnl'], 4)}, SHORT net_pnl={round(short_item['net_pnl'], 4)}."
        )
    elif rows:
        losses = [row for row in rows if _float(row.get("net_pnl")) < 0]
        if losses:
            worst = min(losses, key=lambda row: _float(row.get("net_pnl")))
            lines.append(
                f"- Main weakness in sample: worst audited trade is {worst.get('side')} {worst.get('outcome')} net_pnl={worst.get('net_pnl')} timing={worst.get('entry_timing_type')} location={worst.get('entry_location_type')}."
            )
        else:
            lines.append("- No losing audited trade found in the current sample.")
    else:
        lines.append("- No trade audit rows available.")
    if len(rows) < 10:
        lines.append("- Caveat: sample size is small, so treat this as a current evidence snapshot.")
    lines.append("Source: smartsignalhub_trading.sqlite3 / futures_trade_entry_audits")
    return CapabilityAnswer("trade_analysis", "\n".join(lines))


def _format_market_trades(market: str) -> str:
    if market != "futures":
        return "Spot trade analysis: no closed trade audit family is wired yet."
    result = family_rows("futures", "futures_trade_entry_audits")
    rows = []
    if result.row and isinstance(result.row.get("rows"), list):
        rows = [row for row in result.row["rows"] if isinstance(row, dict)]
    if not rows:
        return f"Futures trade analysis: no trade audit rows found. Source: {result.source}"

    closed = [row for row in rows if str(row.get("outcome") or "").upper() != "OPEN"]
    sample = closed[-10:] if closed else rows[-10:]
    latest = sample[-1]
    total_net = sum(_float(row.get("net_pnl")) for row in sample)
    wins = sum(1 for row in sample if _float(row.get("net_pnl")) > 0)
    losses = sum(1 for row in sample if _float(row.get("net_pnl")) < 0)
    by_side = _sum_by(sample, "side")
    by_timing = _count_by(sample, "entry_timing_type")
    by_location = _count_by(sample, "entry_location_type")

    lines = [
        "Futures trade analysis",
        f"Audit rows: {result.count}",
        f"Sample: last {len(sample)} closed/audited trades",
        f"Sample net PnL: {round(total_net, 4)}",
        f"Wins/Losses: {wins}/{losses}",
        "Latest audited trade:",
        f"- ID: {_value(latest.get('position_id'))}",
        f"- Side/outcome: {_value(latest.get('side'))} / {_value(latest.get('outcome'))}",
        f"- Time: {_value(latest.get('entry_time'))} -> {_value(latest.get('close_time'))}",
        f"- Net PnL: {_value(latest.get('net_pnl'))}",
        f"- Entry timing: {_value(latest.get('entry_timing_type'))}, age={_value(latest.get('entry_direction_signal_age'))}",
        f"- Entry location: {_value(latest.get('entry_location_type'))}",
    ]
    if by_side:
        lines.append("Sample PnL by side:")
        lines.extend(f"- {key}: {round(value, 4)}" for key, value in sorted(by_side.items()))
    if by_timing:
        lines.append("Sample count by timing:")
        lines.extend(f"- {key}: {value}" for key, value in sorted(by_timing.items(), key=lambda item: item[1], reverse=True))
    if by_location:
        lines.append("Sample count by location:")
        lines.extend(f"- {key}: {value}" for key, value in sorted(by_location.items(), key=lambda item: item[1], reverse=True))
    lines.append(f"Source: {result.source}")
    return "\n".join(lines)


def _futures_trade_rows() -> list[dict[str, Any]]:
    result = family_rows("futures", "futures_trade_entry_audits")
    if result.row and isinstance(result.row.get("rows"), list):
        return [row for row in result.row["rows"] if isinstance(row, dict)]
    return []


def _side_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for row in rows:
        side = str(row.get("side") or "UNKNOWN").upper()
        item = stats.setdefault(side, _empty_stats())
        pnl = _float(row.get("net_pnl"))
        item["count"] += 1
        item["net_pnl"] += pnl
        if pnl > 0:
            item["wins"] += 1
        elif pnl < 0:
            item["losses"] += 1
    for item in stats.values():
        decided = item["wins"] + item["losses"]
        item["win_rate"] = round((item["wins"] / decided * 100.0), 2) if decided else 0.0
    return stats


def _empty_stats() -> dict[str, Any]:
    return {"count": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "net_pnl": 0.0}


def _sum_by(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        label = str(row.get(key) or "unknown")
        totals[label] = totals.get(label, 0.0) + _float(row.get("net_pnl"))
    return totals


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _value(value: Any) -> str:
    return "--" if value is None else str(value)
