"""Canonical input and output boundaries for research tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_OUTPUT_ROOT = PROJECT_ROOT / "platform_v2" / "runtime" / "artifacts" / "research" / "replay"
DEFAULT_SNAPSHOT_PARENT = PROJECT_ROOT.parent / "research_snapshots"


@dataclass(frozen=True)
class ResearchDataRoots:
    spot: Path
    futures: Path
    hedge: Path

    @classmethod
    def live(cls) -> "ResearchDataRoots":
        return cls(
            spot=PROJECT_ROOT / "platform_v2" / "runtime" / "spot" / "data",
            futures=PROJECT_ROOT / "platform_v2" / "runtime" / "futures" / "data",
            hedge=PROJECT_ROOT / "platform_v2" / "runtime" / "hedge" / "data",
        )

    @classmethod
    def from_snapshot(cls, snapshot_root: Path) -> "ResearchDataRoots":
        root = snapshot_root.expanduser().resolve()
        return cls(
            spot=root / "spot" / "data",
            futures=root / "futures" / "data",
            hedge=root / "hedge" / "data",
        )
