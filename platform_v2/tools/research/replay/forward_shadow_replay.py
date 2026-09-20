"""Evaluate the frozen forward-shadow candidate set on strictly later data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from platform_v2.tools.research.paths import CANONICAL_OUTPUT_ROOT
from platform_v2.tools.research.replay.candidate_profiles import PROFILES, CandidateProfile
from platform_v2.tools.research.replay.portfolio_replay_report import write_report
from platform_v2.tools.research.replay.portfolio_state_replay import build_report


DEFAULT_SPEC = Path(__file__).with_name("shadow_candidate_set_v2.json")


def load_spec(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "approved_for_forward_shadow_main_baseline_unchanged":
        raise ValueError("Shadow candidate set is not approved for forward evaluation.")
    return payload


def profile_pairs(spec: dict[str, Any]) -> tuple[tuple[CandidateProfile, CandidateProfile], ...]:
    pairs = [
        (PROFILES["futures_long_baseline_v1"], PROFILES["futures_short_baseline_v1"])
    ]
    for arm in spec.get("candidate_arms", []):
        pairs.append((PROFILES[str(arm["long_profile"])], PROFILES[str(arm["short_profile"])]))
    return tuple(pairs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen Futures forward-shadow arms.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUTPUT_ROOT)
    args = parser.parse_args()

    spec = load_spec(args.spec.expanduser().resolve())
    report = build_report(
        args.snapshot.expanduser().resolve(),
        evaluation_start_ms=int(spec["evaluation_cutoff_ms_exclusive"]),
        spot_profiles=(PROFILES["spot_baseline_v1"],),
        futures_profile_pairs=profile_pairs(spec),
    )
    report["shadow_candidate_set_version"] = spec["candidate_set_version"]
    report["shadow_candidate_spec"] = str(args.spec.expanduser().resolve())
    for path in write_report(report, args.output_root.expanduser().resolve()):
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
