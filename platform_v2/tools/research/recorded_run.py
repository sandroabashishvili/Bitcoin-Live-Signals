"""Snapshot-only replay launcher with explicit provenance; never starts live loops."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
from uuid import uuid4

from platform_v2.tools.research.paths import PROJECT_ROOT

MODULES = (
    "portfolio_state_replay", "candidate_signal_outcome_replay",
    "gate_ablation_audit", "indicator_calibration_audit", "tp_touch_fidelity_audit",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_identity(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("A nonempty snapshot manifest is required")
    inventory, coverage = {}, {}
    for item in entries:
        relative = item["path"]
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Snapshot path escapes root or is missing")
        checksum = digest(path)
        if checksum != item["sha256"]:
            raise ValueError(f"Snapshot hash mismatch: {relative}")
        if relative in inventory:
            raise ValueError("Duplicate snapshot manifest entry")
        inventory[relative] = checksum
        timestamps = []
        def visit(value):
            if isinstance(value, dict):
                stamp = value.get("timestamp_ms")
                if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
                    timestamps.append(stamp)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(json.loads(path.read_text()))
        coverage[relative] = {
            "timestamp_field": "timestamp_ms", "count": len(timestamps),
            "min": min(timestamps) if timestamps else None,
            "max": max(timestamps) if timestamps else None,
        }
    actual = {str(p.relative_to(root)) for p in root.rglob("*.json") if p != root / "manifest.json"}
    if actual != set(inventory):
        raise ValueError("Snapshot has unlisted or missing JSON inputs")
    return {"root": str(root), "manifest_sha256": digest(root / "manifest.json"),
            "files": inventory, "coverage": coverage,
            "coverage_note": "Observed timestamp_ms bounds, not usable decision counts; null means unavailable"}


def source_identity() -> dict:
    def git(*args):
        try:
            result = subprocess.run(["git", "-C", str(PROJECT_ROOT), *args], capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return None
        return result.stdout.strip() if result.returncode == 0 else None
    files = {}
    for area in ("spot", "futures", "futures_hedge", "shared", "tools/research"):
        for path in (PROJECT_ROOT / "platform_v2" / area).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json"} and "artifacts" not in path.parts:
                files[str(path.relative_to(PROJECT_ROOT))] = digest(path)
    return {"revision": git("rev-parse", "HEAD"), "working_tree_status": git("status", "--porcelain"),
            "file_sha256": files, "python": sys.version}


def effective_parameters() -> dict:
    from platform_v2.spot.config import settings as spot
    from platform_v2.futures.config import settings as futures
    from platform_v2.tools.research.replay.candidate_profiles import PROFILES
    result = {}
    for name, module in (("spot", spot), ("futures", futures)):
        values = {}
        for key, value in vars(module).items():
            if not key.isupper() or any(word in key for word in ("SECRET", "TOKEN", "PASSWORD", "API_KEY", "CREDENTIAL")):
                continue
            try:
                json.dumps(value, allow_nan=False)
            except (ValueError, TypeError):
                continue
            values[key] = value
        result[name] = values
    result["candidate_profiles"] = {key: asdict(value) for key, value in PROFILES.items()}
    return result


def run_recorded(module: str, snapshot: Path, output_parent: Path) -> Path:
    if module not in MODULES:
        raise ValueError("Unsupported replay module")
    snapshot, output_parent = snapshot.resolve(), output_parent.resolve()
    live = PROJECT_ROOT / "platform_v2/runtime"
    if snapshot.is_relative_to(live) or output_parent.is_relative_to(live):
        raise ValueError("Use external frozen snapshots and external research output")
    if output_parent.is_relative_to(snapshot) or snapshot.is_relative_to(output_parent):
        raise ValueError("Snapshot and output trees must be separate")
    inputs = snapshot_identity(snapshot)
    source = source_identity()
    parameters = effective_parameters()
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    output = output_parent / f"{stamp}_{uuid4().hex[:8]}"
    output.mkdir(parents=True, exist_ok=False)
    command = [f"platform_v2.tools.research.replay.{module}", str(snapshot), "--output-root", str(output)]
    metadata = {"format": "smartsignalhub-research-run-v1", "started_at": datetime.now(UTC).isoformat(),
                "source": source, "parameters": parameters, "dataset": inputs,
                "command": command, "status": "running", "limitations": [
                    "Only listed snapshot replay modules and their default options are supported",
                    "Source files and snapshot must be retained separately for exact reproduction",
                    "Coverage does not establish decision-time availability or snapshot transaction consistency"]}
    path = output / "run_metadata.json"
    def save():
        path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    save()
    argv = sys.argv
    try:
        sys.argv = command
        try:
            runpy.run_module(command[0], run_name="__main__")
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
        if snapshot_identity(snapshot) != inputs or source_identity()["file_sha256"] != source["file_sha256"]:
            raise ValueError("Inputs or source changed during the run")
        metadata["status"] = "completed"
    except BaseException as exc:
        metadata["status"] = "failed"
        metadata["error_type"] = type(exc).__name__
        raise
    finally:
        sys.argv = argv
        metadata["finished_at"] = datetime.now(UTC).isoformat()
        save()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", choices=MODULES)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(run_recorded(args.module, args.snapshot, args.output_root))


if __name__ == "__main__":
    main()
