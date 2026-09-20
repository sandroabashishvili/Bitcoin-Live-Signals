from __future__ import annotations

import argparse

from .orchestrator import DEFAULT_PROFILE, SUPPORTED_PROFILES, run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SmartSignalHub diagnostics")
    parser.add_argument(
        "--profile",
        choices=SUPPORTED_PROFILES,
        default=DEFAULT_PROFILE,
        help=f"Diagnostics profile (default: {DEFAULT_PROFILE})",
    )
    args = parser.parse_args()
    raise SystemExit(run(profile=args.profile))
