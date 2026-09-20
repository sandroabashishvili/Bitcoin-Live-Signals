"""Guard the centralized runtime code and data layout."""

from __future__ import annotations

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding
from platform_v2.shared.backend.runtime_store.families.futures import ALL_FAMILY_SPECS


def runtime_layout_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    central_store = V2_ROOT / "shared" / "backend" / "runtime_store"
    if not central_store.exists():
        add_finding(
            findings,
            "platform_v2",
            "missing_central_runtime_store",
            "shared/backend/runtime_store is required",
            "high",
        )

    legacy_runtime_paths = (
        V2_ROOT / "spot" / "runtime_ledger",
        V2_ROOT / "futures" / "runtime_ledger",
        V2_ROOT / "futures_hedge" / "runtime_ledger",
        V2_ROOT / "shared" / "backend" / "runtime_ledger",
        V2_ROOT / "spot" / "runtime_spot",
        V2_ROOT / "futures" / "runtime_futures",
        V2_ROOT / "futures_hedge" / "runtime_hedge",
        V2_ROOT / "futures" / "shared",
    )
    for legacy_path in legacy_runtime_paths:
        if legacy_path.exists():
            add_finding(
                findings,
                str(legacy_path.relative_to(V2_ROOT.parent)),
                "legacy_runtime_layout",
                "use shared/backend/runtime_store and platform_v2/runtime system roots",
                "high",
            )
    for spec in ALL_FAMILY_SPECS:
        if spec.persisted:
            continue
        derived_path = V2_ROOT / "runtime" / "futures" / "data" / spec.name
        if derived_path.exists():
            add_finding(
                findings,
                str(derived_path.relative_to(V2_ROOT.parent)),
                "persisted_derived_runtime_family",
                f"derive {spec.name} from {', '.join(spec.derived_from)} instead of storing a second copy",
                "high",
            )
    legacy_database_path = V2_ROOT / "runtime" / "database" / "smartsignalhub_runtime.sqlite3"
    if legacy_database_path.exists():
        add_finding(
            findings,
            str(legacy_database_path.relative_to(V2_ROOT.parent)),
            "legacy_runtime_database_recreated",
            "an old process is still writing smartsignalhub_runtime.sqlite3; restart on the three-database code",
            "high",
        )
    return findings
