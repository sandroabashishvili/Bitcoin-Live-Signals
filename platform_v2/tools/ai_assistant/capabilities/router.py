"""Capability dispatcher for assistant questions."""

from __future__ import annotations

from platform_v2.tools.ai_assistant.intents import AssistantIntent

from .action_confirm import answer_action_confirm
from .changes import answer_changes
from .code_search import answer_code_search
from .contracts import CapabilityAnswer
from .artifact_index import answer_artifact_index
from .audit_recommendations import answer_audit_recommendations
from .blocker_statistics import answer_blocker_statistics
from .denied_deep_analysis import answer_denied_deep_analysis
from .diagnostics import answer_diagnostics, answer_file_inventory
from .docs_compare import answer_docs_compare
from .docs_search import answer_docs_search
from .github_status import answer_github_status
from .general import answer_greeting, answer_identity
from .metrics import answer_metrics, answer_why_winning_or_losing
from .news import answer_news
from .runtime_access import answer_runtime_access
from .runtime_health import answer_runtime_health
from .runtime import answer_latest_signal_compare, answer_runtime
from .site_analytics import answer_site_analytics
from .strategy_audit import answer_strategy_audit
from .trade_analysis import answer_trade_analysis
from .trade_analysis import answer_biggest_weakness, answer_side_outperformance, answer_side_performance
from .trade_lifecycle import answer_trade_lifecycle
from .tool_runner import answer_tool_runner_policy
from .tools_registry import answer_tools_registry
from .tools_status import answer_tools_status
from .tool_details import answer_tool_detail
from .unsupported import answer_unsupported
from .window_analysis import answer_denied_reason_window, answer_signal_permission_window


def dispatch(intent: AssistantIntent) -> CapabilityAnswer:
    if intent.capability == "general":
        if intent.topic == "identity":
            return answer_identity()
        return answer_greeting()
    if intent.capability == "artifact_index":
        return answer_artifact_index()
    if intent.capability == "runtime_access":
        return answer_runtime_access()
    if intent.capability == "action_confirm":
        return answer_action_confirm(intent.question)
    if intent.capability == "tools":
        if intent.topic == "tools_status":
            return answer_tools_status()
        if intent.topic == "tool_runner":
            return answer_tool_runner_policy()
        return answer_tools_registry()
    if intent.capability == "tool_details":
        return answer_tool_detail(intent.question)
    if intent.capability == "denied_deep_analysis":
        return answer_denied_deep_analysis(intent)
    if intent.capability == "blocker_statistics":
        return answer_blocker_statistics(intent)
    if intent.capability == "trade_lifecycle":
        return answer_trade_lifecycle(intent)
    if intent.capability == "audit_recommendations":
        return answer_audit_recommendations(intent)
    if intent.capability == "metrics":
        if intent.topic == "win_loss":
            return answer_why_winning_or_losing(intent.market)
        return answer_metrics(intent.market)
    if intent.capability == "runtime_health":
        return answer_runtime_health(intent.market)
    if intent.capability == "strategy_audit":
        return answer_strategy_audit(intent.market)
    if intent.capability == "trade_analysis":
        if intent.topic == "side_performance":
            return answer_side_performance()
        if intent.topic == "side_outperformance":
            return answer_side_outperformance()
        if intent.topic == "biggest_weakness":
            return answer_biggest_weakness()
        return answer_trade_analysis(intent.market)
    if intent.capability == "window_analysis":
        if intent.topic == "signal_permission_window":
            return answer_signal_permission_window(intent)
        return answer_denied_reason_window(intent)
    if intent.capability == "docs_search":
        return answer_docs_search(intent.question)
    if intent.capability == "diagnostics":
        if intent.topic == "file_inventory":
            return answer_file_inventory()
        return answer_diagnostics(intent.question)
    if intent.capability == "changes":
        return answer_changes()
    if intent.capability == "code_search":
        return answer_code_search(intent)
    if intent.capability == "docs_compare":
        return answer_docs_compare()
    if intent.capability == "site_analytics":
        return answer_site_analytics()
    if intent.capability == "github_status":
        return answer_github_status()
    if intent.capability == "news":
        return answer_news()
    if intent.capability == "unsupported":
        return answer_unsupported(intent.question)
    if intent.topic == "signal_compare":
        return answer_latest_signal_compare(intent.market)
    return answer_runtime(intent)
