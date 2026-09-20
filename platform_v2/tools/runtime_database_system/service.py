"""Import JSON ledgers, verify SQLite parity, and generate JSON exports."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any, Iterator

from platform_v2.futures.config import settings as futures_settings
from platform_v2.futures_hedge.config import settings as hedge_settings
from platform_v2.shared.backend.persistence import (
    DEFAULT_DATABASE_PATH,
    content_database_status,
    database_status,
    export_document_to_json,
    import_json_document,
    list_market_series,
    list_news_batches,
    list_documents,
    market_database_status,
    market_series_parity,
    parity_for_document,
    read_market_series,
    read_news_batch,
    replace_market_series,
    replace_news_batch,
    write_runtime_state,
)
from platform_v2.shared.backend.runtime_store.futures import POSITIONS_FAMILY as FUTURES_POSITIONS_FAMILY
from platform_v2.spot.storage.paths import runtime_root as spot_runtime_root


V2_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = V2_ROOT / "runtime" / "artifacts" / "database"
_DAILY_FILE_RE = re.compile(r"^(?P<family>.+)_(?P<date>\d{4}-\d{2}-\d{2})\.json$")


def runtime_sources() -> tuple[tuple[str, Path], ...]:
    return (
        ("spot", spot_runtime_root() / "data"),
        ("futures", futures_settings.RUNTIME_ROOT / "data"),
        ("hedge", hedge_settings.RUNTIME_DATA_ROOT),
    )


def iter_runtime_documents() -> Iterator[tuple[str, str, str, Path]]:
    for system, data_root in runtime_sources():
        if not data_root.exists():
            continue
        for family_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
            family = family_dir.name
            if system == "futures" and family == FUTURES_POSITIONS_FAMILY:
                continue
            for path in sorted(family_dir.glob(f"{family}_*.json")):
                match = _DAILY_FILE_RE.match(path.name)
                if match and match.group("family") == family:
                    yield system, family, match.group("date"), path


def import_all_json(*, db_path: Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    imported = 0
    failures: list[dict[str, str]] = []
    for system, family, date_iso, path in iter_runtime_documents():
        try:
            import_json_document(
                system=system,
                family=family,
                date_iso=date_iso,
                source_path=path,
                db_path=db_path,
            )
            imported += 1
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    state_imported, state_failures = _import_runtime_state_json()
    market_imported, market_failures = _import_market_json()
    content_imported, content_failures = _import_news_json()
    failures.extend(state_failures)
    failures.extend(market_failures)
    failures.extend(content_failures)
    return {
        "trading_documents": imported,
        "trading_states": state_imported,
        "market_series": market_imported,
        "content_batches": content_imported,
        "failures": failures,
        "databases": status(),
    }


def parity_report(*, db_path: Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for system, family, date_iso, path in iter_runtime_documents():
        try:
            items.append(
                parity_for_document(
                    system=system,
                    family=family,
                    date_iso=date_iso,
                    json_path=path,
                    db_path=db_path,
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    matches = sum(1 for item in items if item["status"] == "match")
    mismatches = len(items) - matches
    market_items = market_parity_items()
    content_items = content_parity_items()
    market_mismatches = sum(1 for item in market_items if item["status"] != "match")
    content_mismatches = sum(1 for item in content_items if item["status"] != "match")
    report = {
        "generated_at_utc": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "databases": status(),
        "trading_json_documents": len(items),
        "trading_matches": matches,
        "trading_mismatches": mismatches,
        "market_series": len(market_items),
        "market_mismatches": market_mismatches,
        "content_batches": len(content_items),
        "content_mismatches": content_mismatches,
        "failures": failures,
        "ready_for_primary": bool(
            items
            and mismatches == 0
            and market_mismatches == 0
            and content_mismatches == 0
            and not failures
        ),
        "trading_items": items,
        "market_items": market_items,
        "content_items": content_items,
    }
    _write_report(report)
    return report


def export_all_documents(
    *,
    target_root: Path,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> dict[str, Any]:
    exported: list[str] = []
    for document in list_documents(db_path=db_path):
        system = str(document["system"])
        family = str(document["family"])
        date_iso = str(document["date_iso"])
        target = target_root / system / family / f"{family}_{date_iso}.json"
        export_document_to_json(
            system=system,
            family=family,
            date_iso=date_iso,
            target_path=target,
            db_path=db_path,
        )
        exported.append(str(target))
    for series in list_market_series():
        target = (
            target_root
            / "market_data"
            / str(series["venue"])
            / str(series["asset_class"])
            / str(series["market_type"])
            / str(series["dataset"])
            / str(series["symbol"])
            / f"{series['timeframe']}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        rows = read_market_series(
            venue=str(series["venue"]),
            asset_class=str(series["asset_class"]),
            market_type=str(series["market_type"]),
            dataset=str(series["dataset"]),
            symbol=str(series["symbol"]),
            timeframe=str(series["timeframe"]),
        )
        target.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        exported.append(str(target))
    for batch in list_news_batches():
        day_iso = str(batch["day_iso"])
        target = target_root / "content" / "news" / f"news_items_{day_iso}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {**batch, "items": read_news_batch(day_iso)},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        exported.append(str(target))
    return {"exported_documents": len(exported), "target_root": str(target_root), "paths": exported}


def status(*, db_path: Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    return {
        "trading": database_status(db_path),
        "market_data": market_database_status(),
        "content": content_database_status(),
    }


def iter_market_json() -> Iterator[tuple[str, str, str, str, str, str, Path]]:
    mappings = (
        ("spot", "candles", "candles", "spot"),
        ("spot", "indicator_snapshots", "indicators", "spot"),
        ("spot", "orderflow", "orderflow", "spot"),
        ("futures", "candles_futures", "candles", "futures"),
        ("futures", "indicator_snapshots_futures", "indicators", "futures"),
        ("futures", "orderflow_futures", "orderflow", "futures"),
    )
    roots = dict(runtime_sources())
    for system, family, dataset, market_type in mappings:
        family_root = roots[system] / family
        if not family_root.exists():
            continue
        for path in sorted(family_root.rglob("*.json")):
            symbol = path.parent.name.upper()
            timeframe = _timeframe_from_name(path.stem)
            if timeframe:
                yield "binance", "crypto", market_type, dataset, symbol, timeframe, path


def _import_market_json() -> tuple[int, list[dict[str, str]]]:
    imported = 0
    failures: list[dict[str, str]] = []
    for venue, asset_class, market_type, dataset, symbol, timeframe, path in iter_market_json():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("market payload must be a list")
            replace_market_series(
                venue=venue,
                asset_class=asset_class,
                market_type=market_type,
                dataset=dataset,
                symbol=symbol,
                timeframe=timeframe,
                rows=[row for row in payload if isinstance(row, dict)],
                source_path=path,
            )
            imported += 1
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    return imported, failures


def _import_runtime_state_json() -> tuple[int, list[dict[str, str]]]:
    candidates = (
        ("futures", "simulation_engine", futures_settings.RUNTIME_ROOT / "state" / "engine_state_futures.json"),
    )
    imported = 0
    failures: list[dict[str, str]] = []
    for system, state_key, path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("runtime state payload must be an object")
            write_runtime_state(system=system, state_key=state_key, payload=payload)
            imported += 1
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    return imported, failures


def _news_json_paths() -> Iterator[Path]:
    news_data = V2_ROOT / "public_site" / "news" / "data"
    if news_data.exists():
        yield from sorted(news_data.glob("news_items_*.json"))


def _import_news_json() -> tuple[int, list[dict[str, str]]]:
    imported = 0
    failures: list[dict[str, str]] = []
    for path in _news_json_paths():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise ValueError("news payload must contain an items list")
            day_iso = str(payload.get("day_iso") or path.stem.removeprefix("news_items_"))
            replace_news_batch(
                day_iso=day_iso,
                generated_at_utc=str(payload.get("generated_at_utc") or ""),
                items=[row for row in payload["items"] if isinstance(row, dict)],
                metadata={
                    "source_names": payload.get("source_names") or [],
                    "lookback_hours": payload.get("lookback_hours") or [],
                },
            )
            imported += 1
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    return imported, failures


def market_parity_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for venue, asset_class, market_type, dataset, symbol, timeframe, path in iter_market_json():
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []
        matches = market_series_parity(
            rows=rows,
            venue=venue,
            asset_class=asset_class,
            market_type=market_type,
            dataset=dataset,
            symbol=symbol,
            timeframe=timeframe,
        )
        items.append({"path": str(path), "rows": len(rows), "status": "match" if matches else "mismatch"})
    return items


def content_parity_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in _news_json_paths():
        payload = json.loads(path.read_text(encoding="utf-8"))
        day_iso = str(payload.get("day_iso") or path.stem.removeprefix("news_items_")) if isinstance(payload, dict) else ""
        source_items = payload.get("items") if isinstance(payload, dict) else []
        stored = read_news_batch(day_iso)
        matches = json.dumps(source_items, sort_keys=True, separators=(",", ":")) == json.dumps(stored, sort_keys=True, separators=(",", ":"))
        items.append({"path": str(path), "items": len(source_items) if isinstance(source_items, list) else 0, "status": "match" if matches else "mismatch"})
    return items


def _timeframe_from_name(stem: str) -> str:
    for prefix in ("candles_", "indicators_", "orderflow_"):
        if stem.startswith(prefix):
            return stem.removeprefix(prefix)
    return stem


def _write_report(report: dict[str, Any]) -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_ROOT / "sqlite_parity_latest.json"
    markdown_path = ARTIFACT_ROOT / "sqlite_parity_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(
        "\n".join(
            (
                "# SQLite Runtime Parity",
                "",
                f"- Generated: `{report['generated_at_utc']}`",
                f"- Trading JSON documents: `{report['trading_json_documents']}`",
                f"- Trading matches: `{report['trading_matches']}`",
                f"- Trading mismatches: `{report['trading_mismatches']}`",
                f"- Market series: `{report['market_series']}`",
                f"- Market mismatches: `{report['market_mismatches']}`",
                f"- Content batches: `{report['content_batches']}`",
                f"- Content mismatches: `{report['content_mismatches']}`",
                f"- Import/read failures: `{len(report['failures'])}`",
                f"- Ready for primary-read gate: `{str(report['ready_for_primary']).lower()}`",
                "",
            )
        ),
        encoding="utf-8",
    )
