"""Semantic ownership checks for runtime metric consumers."""

from __future__ import annotations

import re

from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


_RETURN_BPS_CONSUMER_PATTERN = re.compile(
    r"return_bps[\s\S]{0,240}/\s*100(?:\.0)?|/\s*100(?:\.0)?[\s\S]{0,240}return_bps"
)
_ROE_FALLBACK_PATTERN = re.compile(r"roe\s*=.*unreal.*margin.*100(?:\.0)?", re.DOTALL)

_METRIC_CONSUMER_PATH_MARKERS = (
    "tools/telegram_bot_system/",
    "services/ops/main_cycle/notifications.py",
    "futures/services/ops/telegram_notifications.py",
    "services/metrics_system/grouped_payloads.py",
    "futures/services/metrics_system/grouped_payloads.py",
)


def semantic_ownership_findings() -> list[FileFinding]:
    findings: list[FileFinding] = []
    for path in sorted(V2_ROOT.rglob("*.py")):
        path_str = str(path.relative_to(V2_ROOT.parent))
        rel = str(path.relative_to(V2_ROOT))
        if not _is_metric_consumer_path(rel):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue

        if _RETURN_BPS_CONSUMER_PATTERN.search(source):
            add_finding(
                findings,
                path_str,
                "metric_consumer_return_bps_conversion",
                "consumer must read net_return_pct from metrics, not derive it from return_bps",
                "high",
            )

        if rel == "tools/telegram_bot_system/runtime_snapshot.py" and _ROE_FALLBACK_PATTERN.search(source):
            add_finding(
                findings,
                path_str,
                "metric_consumer_roe_calculation",
                "Telegram /positions must read roe_pct from position state, not calculate ROE",
                "high",
            )

    return findings


def _is_metric_consumer_path(rel_path: str) -> bool:
    return any(marker in rel_path for marker in _METRIC_CONSUMER_PATH_MARKERS)
