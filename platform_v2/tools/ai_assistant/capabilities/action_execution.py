"""Prepare, confirm, cancel, and run assistant actions."""

from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

from platform_v2.tools.ai_assistant.runtime_readers import REPO_ROOT

from .action_audit import ACTION_AUDIT_DIR, build_audit_record, find_latest_pending_action, write_action_audit_record
from .action_catalog import AssistantAction, action_by_key
from .contracts import CapabilityAnswer


ACTION_TIMEOUT_SECONDS = 600


def render_action(action: AssistantAction) -> str:
    return "\n".join(
        [
            f"Action proposal: {action.title}",
            "Current mode: read-only planning. No command was executed.",
            f"Action key: {action.key}",
            f"Risk: {action.risk}",
            f"Confirmation: {action.confirmation}",
            f"Assistant scope: {action.assistant_scope}",
            f"Command: {action.command_text}",
            f"Required input: {action.required_input or '--'}",
            f"Writes to: {join_paths(action.writes_to)}",
            f"Audit log target: {ACTION_AUDIT_DIR}",
            f"Purpose: {action.purpose}",
            _next_step_text(action),
        ]
    )


def prepare_action(*, action: AssistantAction, question: str) -> CapabilityAnswer:
    if action.confirmation == "manual_only":
        return CapabilityAnswer("action_confirm", render_action(action), tuple(str(path) for path in action.writes_to))
    command, missing = _resolve_command(action=action, question=question)
    if missing:
        lines = [
            f"Action proposal: {action.title}",
            "Current mode: pending action was not created because required input is missing.",
            f"Action key: {action.key}",
            f"Required input: {action.required_input}",
            f"Missing: {', '.join(missing)}",
            f"Command template: {action.command_text}",
            "Ask again with the required input, for example with a date.",
        ]
        return CapabilityAnswer("action_confirm", "\n".join(lines), tuple(str(path) for path in action.writes_to))

    action_id = uuid.uuid4().hex[:12]
    record = build_audit_record(action=action, status="pending", question=question, note="awaiting explicit confirmation")
    record["action_id"] = action_id
    record["resolved_command"] = command
    audit_path = write_action_audit_record(record)
    lines = [
        f"Pending action created: {action.title}",
        f"Action ID: {action_id}",
        f"Action key: {action.key}",
        f"Risk: {action.risk}",
        f"Command: {' '.join(command)}",
        f"Writes to: {join_paths(action.writes_to)}",
        f"Audit log: {audit_path}",
        "No command was executed yet.",
        f"To run it, send exactly: confirm action {action_id}",
    ]
    return CapabilityAnswer("action_confirm", "\n".join(lines), (str(audit_path), *tuple(str(path) for path in action.writes_to)))


def confirm_pending_action(question: str) -> CapabilityAnswer:
    action_id = extract_action_id(question)
    if not action_id:
        return CapabilityAnswer("action_confirm", "Confirmation rejected.\nMissing action id. Use: confirm action <action_id>", (str(ACTION_AUDIT_DIR),))
    pending = find_latest_pending_action(action_id)
    if not pending:
        return CapabilityAnswer("action_confirm", f"Confirmation rejected.\nNo pending action found for id: {action_id}", (str(ACTION_AUDIT_DIR),))
    action = action_by_key(str(pending.get("action_key") or ""))
    if action is None:
        return CapabilityAnswer("action_confirm", f"Confirmation rejected.\nUnknown action key for id: {action_id}", (str(ACTION_AUDIT_DIR),))
    if action.confirmation == "manual_only":
        return CapabilityAnswer("action_confirm", f"Confirmation rejected.\n{action.key} is manual-only.", (str(ACTION_AUDIT_DIR),))
    if action.risk.startswith("long_running"):
        return CapabilityAnswer("action_confirm", f"Confirmation rejected.\n{action.key} needs a background runner, not the blocking chat runner.", (str(ACTION_AUDIT_DIR),))
    command = pending.get("resolved_command")
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        return CapabilityAnswer("action_confirm", f"Confirmation rejected.\nPending action has no resolved command: {action_id}", (str(ACTION_AUDIT_DIR),))

    started = build_audit_record(action=action, status="started", question=question, note=f"confirmed action_id={action_id}")
    started["action_id"] = action_id
    started["resolved_command"] = command
    write_action_audit_record(started)
    status, note, stdout, stderr = _run_command(command)

    outcome = build_audit_record(action=action, status=status, question=question, note=note)
    outcome["action_id"] = action_id
    outcome["resolved_command"] = command
    outcome["stdout_tail"] = stdout
    outcome["stderr_tail"] = stderr
    audit_path = write_action_audit_record(outcome)

    lines = [
        f"Action outcome: {action.title}",
        f"Action ID: {action_id}",
        f"Status: {status}",
        f"Note: {note}",
        f"Command: {' '.join(command)}",
        f"Audit log: {audit_path}",
    ]
    if stdout:
        lines.extend(["Stdout tail:", stdout])
    if stderr:
        lines.extend(["Stderr tail:", stderr])
    return CapabilityAnswer("action_confirm", "\n".join(lines), (str(audit_path), *tuple(str(path) for path in action.writes_to)))


def cancel_pending_action(question: str) -> CapabilityAnswer:
    action_id = extract_action_id(question)
    if not action_id:
        return CapabilityAnswer("action_confirm", "Cancel rejected.\nMissing action id. Use: cancel action <action_id>", (str(ACTION_AUDIT_DIR),))
    pending = find_latest_pending_action(action_id)
    if not pending:
        return CapabilityAnswer("action_confirm", f"Cancel rejected.\nNo pending action found for id: {action_id}", (str(ACTION_AUDIT_DIR),))
    action = action_by_key(str(pending.get("action_key") or ""))
    if action is None:
        return CapabilityAnswer("action_confirm", f"Cancel rejected.\nUnknown action key for id: {action_id}", (str(ACTION_AUDIT_DIR),))
    record = build_audit_record(action=action, status="canceled", question=question, note=f"canceled action_id={action_id}")
    record["action_id"] = action_id
    record["resolved_command"] = pending.get("resolved_command")
    audit_path = write_action_audit_record(record)
    return CapabilityAnswer(
        "action_confirm",
        "\n".join([f"Pending action canceled: {action.title}", f"Action ID: {action_id}", f"Audit log: {audit_path}", "No command was executed."]),
        (str(audit_path),),
    )


def extract_action_id(question: str) -> str:
    match = re.search(r"\b([a-f0-9]{12})\b", question.casefold())
    return match.group(1) if match else ""


def join_paths(paths: tuple[Path, ...]) -> str:
    return ", ".join(str(path) for path in paths) if paths else "--"


def _run_command(command: list[str]) -> tuple[str, str, str, str]:
    try:
        completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, timeout=ACTION_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "").strip()[-2000:] if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "").strip()[-2000:] if isinstance(exc.stderr, str) else ""
        return "timeout", f"timeout_after_seconds={ACTION_TIMEOUT_SECONDS}", stdout, stderr
    status = "completed" if completed.returncode == 0 else "failed"
    stdout = (completed.stdout or "").strip()[-2000:]
    stderr = (completed.stderr or "").strip()[-2000:]
    return status, f"returncode={completed.returncode}", stdout, stderr


def _next_step_text(action: AssistantAction) -> str:
    if action.confirmation == "manual_only":
        return "This action is manual-only: the assistant may inspect status/artifacts, but it must not execute it from chat."
    return "Next execution layer must write a pending audit row, run only after explicit confirmation, then write the outcome row."


def _resolve_command(*, action: AssistantAction, question: str) -> tuple[list[str], list[str]]:
    command: list[str] = []
    dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", question)
    missing: list[str] = []
    for token in action.command:
        if token == "<YYYY-MM-DD>":
            if dates:
                command.append(dates[0])
            else:
                missing.append("YYYY-MM-DD")
                command.append(token)
        elif token == "<YYYY-MM-DD ...>":
            if dates:
                command.extend(dates)
            else:
                missing.append("YYYY-MM-DD ...")
                command.append(token)
        else:
            command.append(token)
    return command, missing
