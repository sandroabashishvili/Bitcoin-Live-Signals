"""Create a validated research snapshot, exporting live SQLite data on demand."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.persistence import (
    list_documents,
    list_market_series,
    read_document,
    read_market_series,
)
from platform_v2.shared.backend.persistence.database_paths import DATABASE_ROOT
from platform_v2.tools.research.paths import DEFAULT_SNAPSHOT_PARENT, ResearchDataRoots


def create_snapshot(
    *,
    source_roots: ResearchDataRoots | None = None,
    snapshot_parent: Path = DEFAULT_SNAPSHOT_PARENT,
) -> Path:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    destination = snapshot_parent.expanduser().resolve() / f"smartsignalhub_{stamp}"
    if destination.exists():
        raise FileExistsError(destination)

    if source_roots is None:
        manifest_files = _export_database_snapshot(destination)
        source_mode = "sqlite_export_on_demand"
        source_labels = {"database_root": str(DATABASE_ROOT)}
    else:
        manifest_files = _copy_json_snapshot(destination, source_roots)
        source_mode = "explicit_json_roots"
        source_labels = {
            "spot": str(source_roots.spot),
            "futures": str(source_roots.futures),
            "hedge": str(source_roots.hedge),
        }

    manifest = {
        "format": "smartsignalhub-research-snapshot-v1",
        "created_at": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
        "source_mode": source_mode,
        "source_roots": source_labels,
        "file_count": len(manifest_files),
        "files": manifest_files,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def _copy_json_snapshot(destination: Path, sources: ResearchDataRoots) -> list[dict[str, Any]]:
    manifest_files: list[dict[str, Any]] = []
    for system, source in (("spot", sources.spot), ("futures", sources.futures), ("hedge", sources.hedge)):
        if not source.is_dir():
            raise FileNotFoundError(f"{system} data root not found: {source}")
        for source_path in sorted(source.rglob("*.json")):
            relative = source_path.relative_to(source)
            _write_snapshot_payload(
                destination=destination,
                relative_path=Path(system) / "data" / relative,
                payload=_stable_json_bytes(source_path),
                system=system,
                manifest_files=manifest_files,
            )
    return manifest_files


def _export_database_snapshot(destination: Path) -> list[dict[str, Any]]:
    manifest_files: list[dict[str, Any]] = []
    for document in list_documents():
        system = str(document["system"])
        family = str(document["family"])
        date_iso = str(document["date_iso"])
        payload = read_document(system=system, family=family, date_iso=date_iso)
        if payload is None:
            continue
        relative = Path(system) / "data" / family / f"{family}_{date_iso}.json"
        _write_snapshot_payload(
            destination=destination,
            relative_path=relative,
            payload=_json_bytes(payload),
            system=system,
            manifest_files=manifest_files,
        )

    for series in list_market_series():
        system = str(series["market_type"])
        if system not in {"spot", "futures"}:
            continue
        relative = _market_snapshot_path(system=system, series=series)
        rows = read_market_series(
            venue=str(series["venue"]),
            asset_class=str(series["asset_class"]),
            market_type=system,
            dataset=str(series["dataset"]),
            symbol=str(series["symbol"]),
            timeframe=str(series["timeframe"]),
        )
        _write_snapshot_payload(
            destination=destination,
            relative_path=relative,
            payload=_json_bytes(rows),
            system=system,
            manifest_files=manifest_files,
        )
    return manifest_files


def _market_snapshot_path(*, system: str, series: dict[str, Any]) -> Path:
    dataset = str(series["dataset"])
    symbol = str(series["symbol"])
    timeframe = str(series["timeframe"])
    if system == "spot":
        family = {"candles": "candles", "indicators": "indicator_snapshots", "orderflow": "orderflow"}[dataset]
        filename = f"{timeframe}.json"
    else:
        family = {"candles": "candles_futures", "indicators": "indicator_snapshots_futures", "orderflow": "orderflow_futures"}[dataset]
        prefix = {"candles": "candles", "indicators": "indicators", "orderflow": "orderflow"}[dataset]
        filename = f"{prefix}_{timeframe}.json"
    return Path(system) / "data" / family / symbol / filename


def _write_snapshot_payload(
    *, destination: Path, relative_path: Path, payload: bytes, system: str,
    manifest_files: list[dict[str, Any]],
) -> None:
    target = destination / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    manifest_files.append(
        {
            "system": system,
            "path": str(relative_path),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    )


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def verify_snapshot(snapshot_root: Path) -> list[str]:
    root = snapshot_root.expanduser().resolve()
    manifest_path = root / "manifest.json"
    manifest: Any = None
    manifest_error = ""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        manifest_error = f"invalid manifest: {exc}"
    if manifest_error:
        return [manifest_error]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        return ["invalid manifest structure"]

    errors: list[str] = []
    for item in manifest["files"]:
        if not isinstance(item, dict):
            errors.append("invalid manifest file row")
            continue
        relative = str(item.get("path") or "")
        path = root / relative
        if not path.is_file():
            errors.append(f"missing: {relative}")
            continue
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != item.get("sha256"):
            errors.append(f"hash mismatch: {relative}")
        try:
            json.loads(payload)
        except json.JSONDecodeError:
            errors.append(f"invalid json: {relative}")
    return errors


def _stable_json_bytes(path: Path, attempts: int = 3) -> bytes:
    for _ in range(attempts):
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            continue
        json.loads(payload)
        return payload
    raise RuntimeError(f"runtime file changed repeatedly while snapshotting: {path}")
