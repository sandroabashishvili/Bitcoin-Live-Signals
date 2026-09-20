"""Explanation builders for Overview metric details."""

from __future__ import annotations

from typing import Any

from platform_v2.spot.dashboard.explanation_system import (
    ExplanationItem,
    ExplanationRegistry,
    load_explanation_map,
)


def build_overview_explanations(payload: dict[str, Any]) -> ExplanationRegistry:
    registry = ExplanationRegistry(load_explanation_map().values())
    denied_entry = payload.get("latest_denied_entry") or {}
    order = payload.get("latest_order") or {}
    signal = payload.get("latest_signal") or {}

    base_item = registry.get("overview.primary_signal.entry_status")
    title = base_item.title if base_item else "Entry Status"
    summary = (
        base_item.summary
        if base_item
        else "Shows whether the latest BUY setup opened, was denied, or never became actionable."
    )
    details = (
        base_item.details
        if base_item
        else (
            "Opened means an order was actually filled and turned into a live position.",
            "Denied means the signal passed strategy logic but failed at least one execution permission rule.",
            "Blocked by Logic means market conditions were not ready for an actionable entry.",
            "No Action means there was no live trade event to execute or reject.",
        )
    )

    if denied_entry:
        reason_text = str(
            denied_entry.get("denial_reason")
            or (denied_entry.get("permission") or {}).get("reason")
            or "unknown"
        ).replace("_", " ")
        summary = f"Latest entry was denied by the execution layer. Main reason: {reason_text}."
        details = _build_denied_entry_rules(fallback_details=details)
    elif order.get("status") == "FILLED":
        summary = "Latest entry status is Opened because the most recent BUY setup became a filled order."
        details = (
            "This setup passed both strategy logic and execution permission checks.",
            "A filled order means the setup became a real live position.",
            *details,
        )
    elif str(signal.get("side") or "").upper() == "NO_SIGNAL":
        summary = "The latest setup is blocked by strategy logic before execution permission is even considered."
        details = (
            "No actionable BUY exists at the moment, so execution never gets a chance to open a trade.",
            *details,
        )
    else:
        summary = "No trade was opened or denied on the latest visible setup."
        details = (
            "This usually means the page is showing a neutral or non-actionable moment rather than an active entry event.",
            *details,
        )

    registry.register(
        ExplanationItem(
            key="overview.primary_signal.entry_status",
            title=title,
            summary=summary,
            details=details,
            severity="neutral",
            cta_label=base_item.cta_label if base_item else None,
            cta_href=base_item.cta_href if base_item else None,
            secondary_cta_label=base_item.secondary_cta_label if base_item else None,
            secondary_cta_href=base_item.secondary_cta_href if base_item else None,
        )
    )
    return registry


def _build_denied_entry_rules(*, fallback_details: tuple[str, ...]) -> tuple[str, ...]:
    opened_rule = fallback_details[0] if len(fallback_details) > 0 else "Opened means an order was actually filled and turned into a live position."
    denied_rule = fallback_details[1] if len(fallback_details) > 1 else "Denied means the signal passed strategy logic but failed execution permission."
    blocked_rule = fallback_details[2] if len(fallback_details) > 2 else "Blocked by Logic means market conditions were not ready for an actionable entry."
    no_action_rule = fallback_details[3] if len(fallback_details) > 3 else "No Action means there was no live trade event to execute or reject."
    return (
        "Status rules:",
        opened_rule,
        denied_rule,
        blocked_rule,
        no_action_rule,
    )
