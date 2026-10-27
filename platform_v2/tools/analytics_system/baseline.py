"""Read-only cross-system baseline report for Spot, Futures, and Hedge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from math import isfinite

from platform_v2.shared.backend.persistence.sqlite_document_queries import list_documents
from platform_v2.shared.backend.persistence import DEFAULT_DATABASE_PATH

from platform_v2.shared.backend.runtime_store.futures import (
    METRICS_FAMILY as FUTURES_METRICS_FAMILY,
    TRADE_ENTRY_AUDITS_FAMILY,
    load_family_rows_all as load_futures_rows_all,
    load_latest_document as load_latest_futures_document,
)
from platform_v2.shared.backend.runtime_store.hedge import (
    HEDGE_DAILY_SUMMARIES_FAMILY,
    HEDGE_ENTRIES_FAMILY,
    HEDGE_RESET_EVENTS_FAMILY,
    load_family_rows_all as load_hedge_rows_all,
    load_latest_document as load_latest_hedge_document,
)
from platform_v2.shared.backend.runtime_store.spot import (
    FORCE_CLOSES_FAMILY as SPOT_FORCE_CLOSES_FAMILY,
    METRICS_FAMILY as SPOT_METRICS_FAMILY,
    load_family_rows_all as load_spot_rows_all,
    load_latest_document as load_latest_spot_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "platform_v2" / "runtime" / "artifacts" / "analytics" / "baseline"


@dataclass(frozen=True)
class BaselineDataRoots:
    spot: Path
    futures: Path
    hedge: Path
    database_primary: bool = False

    @classmethod
    def live(cls) -> "BaselineDataRoots":
        return cls(
            spot=PROJECT_ROOT / "platform_v2" / "runtime" / "spot" / "data",
            futures=PROJECT_ROOT / "platform_v2" / "runtime" / "futures" / "data",
            hedge=PROJECT_ROOT / "platform_v2" / "runtime" / "hedge" / "data",
            database_primary=True,
        )


def build_baseline(roots: BaselineDataRoots) -> dict[str, Any]:
    if roots.database_primary:
        spot_payload = load_latest_spot_document(SPOT_METRICS_FAMILY)
        futures_payload = load_latest_futures_document(FUTURES_METRICS_FAMILY)
        hedge_payload = load_latest_hedge_document(HEDGE_DAILY_SUMMARIES_FAMILY)
        spot_metrics = spot_payload if isinstance(spot_payload, dict) else {}
        futures_metrics = futures_payload if isinstance(futures_payload, dict) else {}
        hedge_summaries = hedge_payload if isinstance(hedge_payload, list) else ([hedge_payload] if isinstance(hedge_payload, dict) else [])
        spot_force_closes = load_spot_rows_all(SPOT_FORCE_CLOSES_FAMILY)
        futures_audits = _unique_by(load_futures_rows_all(TRADE_ENTRY_AUDITS_FAMILY), "position_id")
        hedge_entries = _unique_by(load_hedge_rows_all(HEDGE_ENTRIES_FAMILY), "hedge_entry_id")
        hedge_resets = _unique_by(load_hedge_rows_all(HEDGE_RESET_EVENTS_FAMILY), "reset_id")
        spot_positions = load_spot_rows_all("positions")
        futures_positions = load_futures_rows_all("futures_position_events")
    else:
        spot_metrics = _latest_dict(roots.spot / "metrics")
        futures_metrics = _latest_dict(roots.futures / "futures_metrics")
        hedge_summaries = _load_rows(roots.hedge / "hedge_daily_summaries")
        spot_force_closes = _load_rows(roots.spot / "force_closes")
        futures_audits = _unique_by(_load_rows(roots.futures / "futures_trade_entry_audits"), "position_id")
        hedge_entries = _unique_by(_load_rows(roots.hedge / "hedge_entries"), "hedge_entry_id")
        hedge_resets = _unique_by(_load_rows(roots.hedge / "hedge_reset_events"), "reset_id")
        spot_positions = _load_rows(roots.spot / "positions")
        futures_positions = _load_rows(roots.futures / "futures_position_events")
    hedge_summary = max(
        hedge_summaries,
        key=lambda row: str(row.get("generated_at") or row.get("date") or ""),
        default={},
    )


    report: dict[str, Any] = {
        "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
        "input_mode": "read_only",
        "storage_mode": "sqlite" if roots.database_primary else "json",
        "source_database": str(DEFAULT_DATABASE_PATH) if roots.database_primary else None,
        "report_version": 2,
        "purpose": "Descriptive results only; run diagnostics for integrity checks. Not a backtest.",
        "data_available": {"spot": bool(spot_metrics), "futures": bool(futures_metrics), "hedge": bool(hedge_summary)},
        "source_roots": {
            "spot": str(roots.spot),
            "futures": str(roots.futures),
            "hedge": str(roots.hedge),
        },
        "source_timestamps": {
            "spot": spot_metrics.get("datetime") or spot_metrics.get("date"),
            "futures": futures_metrics.get("datetime") or futures_metrics.get("date"),
            "hedge": hedge_summary.get("generated_at") or hedge_summary.get("date"),
        },
        "date_range": _combined_date_range(roots),
        "spot": _standard_metrics(spot_metrics),
        "futures": _standard_metrics(futures_metrics),
        "hedge": {
            "starting_capital": _number(hedge_summary.get("starting_capital_usdt")),
            "equity": _number(hedge_summary.get("equity_usdt")),
            "available_balance": _number(hedge_summary.get("available_capital_usdt")),
            "used_margin": _number(hedge_summary.get("used_margin_usdt")),
            "realized_pnl": _number(hedge_summary.get("realized_pnl_usdt")),
            "unrealized_pnl": _number(hedge_summary.get("unrealized_pnl_usdt")),
            "fees_paid": _number(hedge_summary.get("total_fees_usdt")),
            "entries": len(hedge_entries),
            "resets": len(hedge_resets),
            "max_drawdown_pct": _number(hedge_summary.get("max_drawdown_pct")),
            "max_runup_pct": _number(hedge_summary.get("max_runup_pct")),
            "liquidation_risk": hedge_summary.get("liquidation_risk"),
            "net_exposure_side": hedge_summary.get("net_exposure_side"),
            "net_exposure_usdt": _number(hedge_summary.get("net_exposure_usdt")),
        },
        "raw_evidence": {
            "spot_force_close_rows": len(spot_force_closes),
            "futures_closed_trade_audits": len(futures_audits),
            "hedge_entry_rows": len(hedge_entries),
            "hedge_reset_rows": len(hedge_resets),
        },
    }
    report["performance"] = {
        "spot": _performance_summary(spot_positions),
        "futures": _performance_summary(futures_positions),
    }
    report["limitations"] = [
        "Observed retained history, not evidence that a strategy will remain profitable.",
        "Spot/Futures trade outcomes use latest state per position ID; Hedge basket resets are not individual trade outcomes.",
        "Missing/non-finite net PnL is excluded and counted; zero losses make profit factor undefined, not infinite.",
        "Live metrics and history are read sequentially and can span a running cycle; diagnostics owns snapshot-consistent accounting checks.",
    ]
    return report


def write_baseline(report: dict[str, Any], output_root: Path = DEFAULT_OUTPUT_ROOT) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    json_path = output_root / f"system_baseline_{stamp}.json"
    md_path = output_root / f"system_baseline_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, md_path


def _standard_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "starting_capital",
        "equity",
        "available_balance",
        "reserved_capital",
        "total_net_pnl",
        "unrealized_pnl",
        "fees_paid",
        "net_return_pct",
        "win_rate",
        "total_positions",
        "open_positions",
        "closed_positions",
        "tp_hits",
        "sl_hits",
        "force_close_events",
        "total_signals_since_start",
        "buy_signals_since_start",
        "long_signals_since_start",
        "short_signals_since_start",
        "no_signal_since_start",
        "denied_entries_since_start",
        "trades_opened_since_start",
        "strategy_start",
        "elapsed",
    )
    return {key: metrics.get(key) for key in keys if key in metrics}


def _performance_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    latest = list(_unique_by(history, "position_id").values())
    closed = [row for row in latest if row.get("status") == "CLOSED"]

    def outcomes(rows):
        values = [_number(row.get("net_pnl")) for row in rows]
        valid = [value for value in values if value is not None]
        positive = sum(value for value in valid if value > 0)
        negative = -sum(value for value in valid if value < 0)
        return {
            "closed_positions": len(rows), "valid_net_outcomes": len(valid),
            "missing_net_outcomes": len(rows) - len(valid),
            "wins": sum(value > 0 for value in valid),
            "losses": sum(value < 0 for value in valid),
            "breakeven": sum(value == 0 for value in valid),
            "net_pnl": round(sum(valid), 6) if valid else None,
            "win_rate_pct": round(sum(value > 0 for value in valid) / len(valid) * 100, 4) if valid else None,
            "average_net_pnl": round(sum(valid) / len(valid), 6) if valid else None,
            "profit_factor": round(positive / negative, 6) if negative else None,
        }

    return {
        **outcomes(closed), "total_positions": len(latest),
        "open_positions": sum(row.get("status") == "OPEN" for row in latest),
        "rows_without_position_id": sum(not row.get("position_id") for row in history),
        "by_side": {side: outcomes([row for row in closed if str(row.get("side") or "UNKNOWN") == side])
                    for side in sorted({str(row.get("side") or "UNKNOWN") for row in closed})},
    }


def _latest_dict(folder: Path) -> dict[str, Any]:
    paths = sorted(folder.glob("*.json")) if folder.exists() else []
    if not paths:
        return {}
    payload = _load_json(paths[-1])
    return payload if isinstance(payload, dict) else {}


def _load_rows(folder: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")) if folder.exists() else ():
        payload = _load_json(path)
        if isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
        elif isinstance(payload, dict):
            rows.append(payload)
    return rows


def _unique_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(row[key]): row
        for row in rows
        if row.get(key) not in (None, "")
    }


def _combined_date_range(roots: BaselineDataRoots) -> dict[str, str | None]:
    dates: set[str] = set()
    if roots.database_primary:
        dates = {
            str(document["date_iso"])
            for document in list_documents()
            if document["system"] in {"spot", "futures", "hedge"} and document.get("date_iso")
        }
        return {"start": min(dates) if dates else None, "end": max(dates) if dates else None}
    for root in (roots.spot, roots.futures, roots.hedge):
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            candidate = path.stem[-10:]
            if len(candidate) == 10 and candidate[4] == "-" and candidate[7] == "-":
                dates.add(candidate)
    return {
        "start": min(dates) if dates else None,
        "end": max(dates) if dates else None,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if isfinite(number) and not isinstance(value, bool) else None
    except (TypeError, ValueError):
        return None


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SmartSignalHub System Baseline",
        "",
        f"Generated: {report['generated_at']}",
        f"Range: {report['date_range']['start']} – {report['date_range']['end']}",
        f"Storage: {report['storage_mode']}; source database: {report['source_database']}",
        "Purpose: descriptive results, not integrity verification or historical replay.",
        "",
    ]
    for name in ("spot", "futures", "hedge"):
        values = report[name]
        lines.extend(
            [
                f"## {name.title()}",
                "",
                f"- Source available: {report['data_available'][name]}; timestamp: {report['source_timestamps'][name]}",
                f"- Equity: {values.get('equity')}",
                f"- Net/realized PnL: {values.get('total_net_pnl', values.get('realized_pnl'))}",
                f"- Entries/positions: {values.get('total_positions', values.get('entries'))}",
                f"- Win rate: {values.get('win_rate', 'n/a')}",
                "",
            ]
        )
    lines.extend(["## Closed-trade outcomes", "", "Win rate uses finite net PnL (fees included). Breakeven outcomes count in the denominator.", ""])
    for system, summary in report["performance"].items():
        lines.append(f"### {system.title()}")
        for side, values in {"ALL": summary, **summary["by_side"]}.items():
            lines.append(f"- {side}: closed={values['closed_positions']}, wins={values['wins']}, losses={values['losses']}, breakeven={values['breakeven']}, net={values['net_pnl']}, win_rate={values['win_rate_pct']}, profit_factor={values['profit_factor']}, missing_net={values['missing_net_outcomes']}")
    lines.extend(["", "## Limits", "", *[f"- {item}" for item in report["limitations"]]])
    return "\n".join(lines) + "\n"
