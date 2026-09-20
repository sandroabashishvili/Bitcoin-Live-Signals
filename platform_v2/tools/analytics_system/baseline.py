"""Read-only cross-system baseline report for Spot, Futures, and Hedge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

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
    else:
        spot_metrics = _latest_dict(roots.spot / "metrics")
        futures_metrics = _latest_dict(roots.futures / "futures_metrics")
        hedge_summaries = _load_rows(roots.hedge / "hedge_daily_summaries")
        spot_force_closes = _load_rows(roots.spot / "force_closes")
        futures_audits = _unique_by(_load_rows(roots.futures / "futures_trade_entry_audits"), "position_id")
        hedge_entries = _unique_by(_load_rows(roots.hedge / "hedge_entries"), "hedge_entry_id")
        hedge_resets = _unique_by(_load_rows(roots.hedge / "hedge_reset_events"), "reset_id")
    hedge_summary = max(
        hedge_summaries,
        key=lambda row: str(row.get("generated_at") or row.get("date") or ""),
        default={},
    )


    report: dict[str, Any] = {
        "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
        "input_mode": "read_only",
        "source_roots": {
            "spot": str(roots.spot),
            "futures": str(roots.futures),
            "hedge": str(roots.hedge),
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
    report["consistency_checks"] = _consistency_checks(
        spot_metrics=spot_metrics,
        spot_force_closes=spot_force_closes,
        futures_metrics=futures_metrics,
        futures_audits=futures_audits,
        hedge_summary=hedge_summary,
        hedge_entries=hedge_entries,
        hedge_resets=hedge_resets,
    )
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


def _consistency_checks(
    *,
    spot_metrics: dict[str, Any],
    spot_force_closes: list[dict[str, Any]],
    futures_metrics: dict[str, Any],
    futures_audits: dict[str, dict[str, Any]],
    hedge_summary: dict[str, Any],
    hedge_entries: dict[str, dict[str, Any]],
    hedge_resets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    checks = [
        _equality_check(
            "spot_force_close_count",
            spot_metrics.get("force_close_events"),
            len(spot_force_closes),
            "Spot metrics versus force-close ledger rows.",
        ),
        _equality_check(
            "futures_closed_trade_count",
            futures_metrics.get("closed_positions"),
            len(futures_audits),
            "Futures metrics versus unique closed-trade audits.",
        ),
        _equality_check(
            "futures_to_hedge_entries",
            futures_metrics.get("trades_opened_since_start"),
            len(hedge_entries),
            "Every Futures entry should feed one Hedge entry in the current replay.",
        ),
        _equality_check(
            "hedge_summary_entry_count",
            hedge_summary.get("hedge_entries_accepted"),
            len(hedge_entries),
            "Hedge summary versus unique Hedge entry rows.",
        ),
        _equality_check(
            "hedge_summary_reset_count",
            hedge_summary.get("reset_count"),
            len(hedge_resets),
            "Hedge summary versus unique reset rows.",
        ),
    ]
    return checks


def _equality_check(name: str, reported: Any, observed: Any, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if _number(reported) == _number(observed) else "mismatch",
        "reported": reported,
        "observed": observed,
        "detail": detail,
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


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SmartSignalHub System Baseline",
        "",
        f"Generated: {report['generated_at']}",
        f"Range: {report['date_range']['start']} – {report['date_range']['end']}",
        "",
    ]
    for name in ("spot", "futures", "hedge"):
        values = report[name]
        lines.extend(
            [
                f"## {name.title()}",
                "",
                f"- Equity: {values.get('equity')}",
                f"- Net/realized PnL: {values.get('total_net_pnl', values.get('realized_pnl'))}",
                f"- Entries/positions: {values.get('total_positions', values.get('entries'))}",
                f"- Win rate: {values.get('win_rate', 'n/a')}",
                "",
            ]
        )
    lines.extend(["## Consistency checks", ""])
    for check in report["consistency_checks"]:
        lines.append(
            f"- **{check['status'].upper()}** `{check['name']}`: "
            f"reported={check['reported']} observed={check['observed']}"
        )
    return "\n".join(lines) + "\n"
