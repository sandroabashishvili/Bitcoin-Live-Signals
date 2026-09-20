"""Detect byte-equivalent runtime rows stored in more than one family."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store import system_runtime_root
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


def runtime_cross_family_duplication_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    for system in ("spot", "futures", "hedge"):
        data_root = system_runtime_root(system) / "data"
        hashes: dict[str, list[tuple[str, Path]]] = defaultdict(list)
        if not data_root.exists():
            continue
        for family_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
            for path in sorted(family_dir.glob("*.json")):
                payload = _load_json(path)
                rows = payload if isinstance(payload, list) else [payload]
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                    hashes[digest].append((family_dir.name, path))
        duplicate_groups = [
            group for group in hashes.values() if len({family for family, _ in group}) > 1
        ]
        if duplicate_groups:
            sample = duplicate_groups[0]
            families = sorted({family for family, _ in sample})
            add_finding(
                findings,
                str(data_root),
                "cross_family_exact_duplicate_rows",
                f"groups={len(duplicate_groups)} sample_families={','.join(families)}",
                "medium",
            )
    return findings


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
