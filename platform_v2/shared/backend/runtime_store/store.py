"""One storage API for Spot, Futures, and Hedge runtime data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from platform_v2.shared.backend.persistence import (
    mirror_daily_json_path_safely,
    mirror_document_safely,
    list_documents,
    read_daily_json_dict,
    read_daily_json_list,
    read_family_rows,
    read_latest_document,
    read_document,
    remove_family_documents_except,
)
from platform_v2.shared.backend.serialization import to_runtime_dict

from .contracts import RuntimeFamilySpec
from .json_io import (
    resolve_row_date,
)
from .system_registry import system_runtime_root
from .validation import missing_required_keys as find_missing_required_keys
from .validation import validate_runtime_record as validate_record


@dataclass(frozen=True)
class RuntimeStore:
    """System-labelled facade over JSON compatibility files and SQLite."""

    system: str
    family_by_name: Mapping[str, RuntimeFamilySpec] = field(default_factory=dict)
    ensure_ascii: bool = False

    def runtime_root(self) -> Path:
        return system_runtime_root(self.system)

    def runtime_data_root(self) -> Path:
        return self.runtime_root() / "data"

    def family_dir(self, family_name: str) -> Path:
        return self.runtime_data_root() / family_name

    def daily_json_path(self, family_name: str, date_iso: str) -> Path:
        return self.family_dir(family_name) / f"{family_name}_{date_iso}.json"

    def load_json_list(self, path: Path) -> list[dict[str, Any]]:
        return read_daily_json_list(system=self.system, path=path)

    def load_json_dict(self, path: Path) -> dict[str, Any]:
        return read_daily_json_dict(system=self.system, path=path)

    def load_family_rows(self, family_name: str, date_iso: str) -> list[dict[str, Any]]:
        return self.load_json_list(self.daily_json_path(family_name, date_iso))

    def load_family_rows_all(self, family_name: str) -> list[dict[str, Any]]:
        return read_family_rows(
            system=self.system,
            family=family_name,
            json_folder=self.family_dir(family_name),
        )

    def load_latest_document(self, family_name: str) -> list[Any] | dict[str, Any] | None:
        stored = read_latest_document(system=self.system, family=family_name)
        if stored is not None:
            return stored[1]
        folder = self.family_dir(family_name)
        files = sorted(folder.glob(f"{family_name}_*.json")) if folder.exists() else []
        if not files:
            return None
        path = files[-1]
        payload = self.load_json_dict(path)
        if payload:
            return payload
        rows = self.load_json_list(path)
        return rows if rows else None

    def load_family_documents(self, family_name: str) -> list[tuple[str, list[Any] | dict[str, Any]]]:
        documents: list[tuple[str, list[Any] | dict[str, Any]]] = []
        for metadata in list_documents():
            if metadata.get("system") != self.system or metadata.get("family") != family_name:
                continue
            date_iso = str(metadata.get("date_iso") or "")
            payload = read_document(system=self.system, family=family_name, date_iso=date_iso)
            if payload is not None:
                documents.append((date_iso, payload))
        return documents

    def write_json(self, path: Path, payload: Any) -> Path:
        if not mirror_daily_json_path_safely(system=self.system, path=path, payload=payload):
            raise ValueError(f"Runtime path is not a daily family document: {path}")
        return path

    def append_runtime_record(self, family_name: str, date_iso: str, record: Any) -> Path:
        rows = self.load_family_rows(family_name, date_iso)
        rows.append(self._runtime_row(record))
        return self.write_json(self.daily_json_path(family_name, date_iso), rows)

    def upsert_runtime_record(
        self,
        family_name: str,
        date_iso: str,
        record: Any,
        *,
        key_name: str,
    ) -> Path:
        return self.upsert_runtime_row(
            family_name=family_name,
            date_iso=date_iso,
            row=record,
            match_keys=(key_name,),
        )

    def upsert_runtime_row(
        self,
        *,
        family_name: str,
        date_iso: str,
        row: Any,
        match_keys: tuple[str, ...],
    ) -> Path:
        if not match_keys:
            raise ValueError("match_keys must contain at least one key.")
        rows = self.load_family_rows(family_name, date_iso)
        runtime_row = self._runtime_row(row)
        match_values = tuple(runtime_row.get(key) for key in match_keys)
        if any(value is None for value in match_values):
            missing = ", ".join(key for key, value in zip(match_keys, match_values) if value is None)
            raise KeyError(f"Runtime row is missing required upsert keys: {missing}")
        for index, existing in enumerate(rows):
            if tuple(existing.get(key) for key in match_keys) == match_values:
                rows[index] = runtime_row
                break
        else:
            rows.append(runtime_row)
        return self.write_json(self.daily_json_path(family_name, date_iso), rows)

    def store_runtime_snapshot(
        self,
        family_name: str,
        date_iso: str,
        payload: dict[str, Any],
    ) -> Path:
        return self.write_json(self.daily_json_path(family_name, date_iso), payload)

    def replace_family_rows(
        self,
        family_name: str,
        rows: list[dict[str, Any]],
    ) -> list[Path]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(resolve_row_date(row), []).append(row)
        written: list[Path] = []
        keep_dates: set[str] = set()
        for date_iso, date_rows in sorted(grouped.items()):
            path = self.daily_json_path(family_name, date_iso)
            if not mirror_document_safely(
                system=self.system,
                family=family_name,
                date_iso=date_iso,
                payload=date_rows,
                source_path=path,
            ):
                raise RuntimeError(f"Failed to store runtime family: {self.system}/{family_name}/{date_iso}")
            keep_dates.add(date_iso)
            written.append(path)
        remove_family_documents_except(
            system=self.system,
            family=family_name,
            keep_dates=keep_dates,
        )
        return written

    def upsert_family_rows(
        self,
        family_name: str,
        rows: list[dict[str, Any]],
        *,
        key_field: str = "timestamp_ms",
    ) -> list[Path]:
        existing = self.load_family_rows_all(family_name)
        merged: dict[str, dict[str, Any]] = {}
        for row in [*existing, *rows]:
            value = row.get(key_field)
            if value not in (None, ""):
                merged[str(value)] = row
        return self.replace_family_rows(family_name, list(merged.values()))

    def missing_required_keys(self, family_name: str, payload: dict[str, Any]) -> list[str]:
        return find_missing_required_keys(
            family_name,
            payload,
            family_by_name=self.family_by_name,
        )

    def validate_runtime_record(self, family_name: str, payload: Any) -> list[str]:
        return validate_record(
            family_name,
            payload,
            family_by_name=self.family_by_name,
        )

    @staticmethod
    def _runtime_row(record: Any) -> dict[str, Any]:
        runtime_row = to_runtime_dict(record)
        if not isinstance(runtime_row, dict):
            raise TypeError("Runtime record must serialize to a dictionary.")
        return runtime_row
