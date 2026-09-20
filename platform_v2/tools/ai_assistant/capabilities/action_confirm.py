"""Thin action-confirm router for assistant-triggered tools."""

from __future__ import annotations

from .action_audit import ACTION_AUDIT_DIR, current_audit_log_path, pending_actions
from .action_catalog import ACTIONS, match_action
from .action_execution import cancel_pending_action, confirm_pending_action, join_paths, prepare_action, render_action
from .contracts import CapabilityAnswer


def answer_action_confirm(question: str = "") -> CapabilityAnswer:
    if _is_cancel_request(question):
        return cancel_pending_action(question)
    if _is_confirm_request(question):
        return confirm_pending_action(question)

    action = match_action(question)
    if action:
        if _is_prepare_request(question):
            return prepare_action(action=action, question=question)
        text = render_action(action)
        sources = tuple(str(path) for path in action.writes_to)
        return CapabilityAnswer("action_confirm", text, sources)

    lines = [
        "Action-confirm foundation",
        "Current mode: confirm-run enabled for allowlisted non-manual actions.",
        f"Audit log target: {current_audit_log_path()}",
        "Execution rule: every non-read action must create an audit row before/after execution.",
        "Confirmation policy:",
        "- required: user must explicitly confirm the specific action.",
        "- manual_only: assistant can explain/status-check it, but the owner runs it manually from terminal.",
        "Pending actions:",
    ]
    pending = pending_actions()
    if pending:
        for row in pending:
            command = row.get("resolved_command")
            command_text = " ".join(command) if isinstance(command, list) and all(isinstance(item, str) for item in command) else "--"
            lines.append(f"- {row.get('action_id')}: {row.get('action_key')} command={command_text}")
    else:
        lines.append("- none")
    lines.append("Action candidates:")
    for item in ACTIONS:
        lines.append(f"- {item.key}: {item.confirmation}, scope={item.assistant_scope}, risk={item.risk}")
        lines.append(f"  command={item.command_text}")
        lines.append(f"  writes_to={join_paths(item.writes_to)}")
    return CapabilityAnswer("action_confirm", "\n".join(lines), (str(ACTION_AUDIT_DIR),))


def _is_confirm_request(question: str) -> bool:
    text = question.casefold().strip()
    return text.startswith("confirm action") or text.startswith("დაადასტურე action")


def _is_cancel_request(question: str) -> bool:
    text = question.casefold().strip()
    return text.startswith("cancel action") or text.startswith("გააუქმე action")


def _is_prepare_request(question: str) -> bool:
    text = question.casefold().strip()
    if text.startswith(("can ", "could ", "შეუძლია", "შეიძლება")):
        return False
    return any(
        token in text
        for token in (
            "prepare",
            "create pending",
            "run ",
            "execute",
            "generate",
            "გაუშვი",
            "გავუშვათ",
            "გაშვება",
            "მოამზადე",
        )
    )
