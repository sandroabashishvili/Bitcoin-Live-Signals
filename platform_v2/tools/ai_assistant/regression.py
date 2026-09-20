"""Regression checks for assistant routing and deterministic answers."""

from __future__ import annotations

from dataclasses import dataclass

from .engine import answer_question


@dataclass(frozen=True)
class RegressionCase:
    question: str
    expected: tuple[str, ...]


CASES: tuple[RegressionCase, ...] = (
    RegressionCase("ბოლო 20 Futures სიგნალიდან რამდენი იყო ALLOWED და რამდენი DENIED?", ("Last Futures signals by permission status", "Permission status counts")),
    RegressionCase("Show the last 20 denied futures entries. Group by permission_reason. Count each reason.", ("Last Futures denied entries grouped", "Counts")),
    RegressionCase("Compare LONG and SHORT performance. Show trade count, win rate, net pnl.", ("Futures LONG vs SHORT performance", "net_pnl")),
    RegressionCase("Based on current audit data, what is the biggest weakness of the futures system? Use evidence.", ("Biggest Futures weakness", "Trade audit sample size")),
    RegressionCase("Show all files related to futures permissions. Return paths only.", ("futures_permission_decision_service.py", "risk_and_permissions.md")),
    RegressionCase("Why was the latest SHORT denied while an older SHORT position is still open? Explain step by step.", ("Latest denied Futures signal vs open same-direction position", "does not close or modify")),
    RegressionCase("Why are SHORT trades outperforming LONG trades? Use audit evidence only.", ("Evidence-only explanation", "SHORT")),
    RegressionCase("Deeply explain why the latest Futures signal was denied.", ("Latest denied Futures signal analysis", "Failed checks")),
    RegressionCase("Show trade lifecycle of FUT-000005", ("Futures trade lifecycle", "FUT-000005")),
    RegressionCase("What internal tools do we have?", ("SmartSignalHub internal tools registry", "diagnostics")),
    RegressionCase("Show artifact index.", ("SmartSignalHub artifact index", "diagnostics")),
    RegressionCase("ბოლო 20 Spot სიგნალიდან რამდენი იყო ALLOWED და რამდენი DENIED?", ("Last Spot signals by permission status", "NO_SIGNAL")),
    RegressionCase("Show spot blocker statistics.", ("Spot blocker statistics", "Top failed gates")),
    RegressionCase("Deeply explain why latest Spot signal was blocked.", ("Latest Spot signal block analysis", "Failed gates")),
    RegressionCase("Show Spot trade lifecycle.", ("Spot trade lifecycle", "Facts")),
    RegressionCase("Spot audit recommendations.", ("Spot audit recommendations snapshot", "Trades opened since start")),
    RegressionCase("გამარჯობა.", ("SmartSignalHub Assistant", "Python readers")),
    RegressionCase("What is your name? What model are you?", ("SmartSignalHub Assistant", "source of truth")),
    RegressionCase("what is the capital of France?", ("Unsupported question yet",)),
    RegressionCase("სისტემა მუშაობს?", ("Verdict", "Facts", "Sources", "Limitations")),
    RegressionCase("news generation status რას ამბობს?", ("News generation detail", "Item count")),
    RegressionCase("github publish status", ("GitHub publish detail", "Latest push event")),
    RegressionCase("sitemap status", ("Sitemap detail", "URL count")),
    RegressionCase("telegram status", ("Telegram bot detail", "Subscribers active")),
    RegressionCase("backup status", ("Backup detail", "Action-safe status")),
    RegressionCase("research status", ("Research/replay detail", "Latest summary")),
    RegressionCase("video reels status", ("Video reels detail", "Action-safe status")),
    RegressionCase("diagnostics action status", ("Diagnostics action-safe detail", "Running diagnostics from chat is not enabled yet")),
    RegressionCase("analytics system status", ("Analytics system detail", "futures-audit-suite")),
    RegressionCase("runtime access coverage ყველა მეტრიკაზე", ("Runtime access coverage", "futures_runtime", "spot_runtime")),
    RegressionCase("action confirm status", ("Action-confirm foundation", "Audit log target", "manual_only")),
    RegressionCase("diagnostics full report summary", ("Diagnostics report", "Profile: full", "Assistant summary")),
    RegressionCase("public site seo audit", ("Public site and analytics capability", "Local public-site audit", "Sitemap archive coverage issues")),
    RegressionCase("can assistant run diagnostics?", ("Action proposal: Run operational diagnostics", "No command was executed", "--profile operational")),
    RegressionCase("can assistant run backup?", ("Action proposal: Run backup system", "manual-only", "must not execute")),
    RegressionCase("can assistant run research replay?", ("Action proposal: Run Futures entry-quality research replay", "Required input", "--dates")),
    RegressionCase("can assistant run telegram poll once?", ("Action proposal: Run Telegram poll once", "--poll-once", "confirmation")),
    RegressionCase("can assistant generate video reel?", ("Action proposal: Generate video reel", "Required input", "--date")),
    RegressionCase("can assistant run analytics audit suite?", ("Action proposal: Run Futures analytics audit suite", "Required input", "futures-audit-suite")),
    RegressionCase("What internal tools do we have?", ("analytics_system", "diagnostics")),
    RegressionCase("confirm action", ("Confirmation rejected", "Missing action id")),
    RegressionCase("cancel action", ("Cancel rejected", "Missing action id")),
    RegressionCase("prepare analytics audit suite", ("required input is missing", "YYYY-MM-DD")),
)


def run_regression() -> str:
    lines = ["AI assistant regression"]
    failed = 0
    for index, case in enumerate(CASES, start=1):
        answer = answer_question(case.question)
        missing = [token for token in case.expected if token not in answer]
        if missing:
            failed += 1
            lines.append(f"FAIL {index}: {case.question}")
            lines.append(f"  missing={missing}")
        else:
            lines.append(f"PASS {index}: {case.question}")
    lines.append(f"Result: passed={len(CASES) - failed}, failed={failed}, total={len(CASES)}")
    return "\n".join(lines)
