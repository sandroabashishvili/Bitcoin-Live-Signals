"""Natural-language intent routing for the SmartSignalHub assistant."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantIntent:
    market: str | None
    topic: str
    capability: str
    question: str = ""


def detect_intent(question: str) -> AssistantIntent:
    text = question.casefold()
    market = _detect_market(text)
    topic = _detect_topic(text)
    capability = _detect_capability(text, topic)
    return AssistantIntent(market=market, topic=topic, capability=capability, question=question)


def _detect_market(text: str) -> str | None:
    has_futures = any(token in text for token in ("futures", "future", "ფუჩ", "ფიუჩ", "ფუც"))
    has_spot = any(token in text for token in ("spot", "სპოტ"))
    if has_futures and has_spot:
        return None
    if has_futures:
        return "futures"
    if has_spot:
        return "spot"
    return None


def _detect_topic(text: str) -> str:
    if text.strip().startswith(("confirm action", "cancel action")) or text.strip().startswith(("დაადასტურე action", "გააუქმე action")):
        return "action_confirm"
    if any(token in text for token in ("prepare", "create pending", "მოამზადე")) and any(
        token in text for token in ("action", "diagnostics", "analytics", "research", "telegram", "video", "sitemap", "news", "დიაგნოსტ", "ანალიტიკ")
    ):
        return "action_confirm"
    if any(token in text for token in ("backup status", "backup detail", "ბექაფ")):
        return "tool_detail"
    if any(token in text for token in ("analytics status", "analytics detail", "analytics system", "ანალიტიკ")) and any(token in text for token in ("status", "detail", "რას ამბობს", "tool", "system", "სტატუს")):
        return "tool_detail"
    if any(token in text for token in ("research status", "research detail", "replay status", "what-if status", "what if status")):
        return "tool_detail"
    if any(token in text for token in ("video reels", "reels status", "video status", "ვიდეო")):
        return "tool_detail"
    if any(token in text for token in ("diagnostics action", "diagnostics status", "diagnostic action")):
        return "tool_detail"
    if any(token in text for token in ("news generation", "news tool", "ნიუს", "ახალი ამბ")) and any(token in text for token in ("status", "detail", "რას ამბობს", "რა შეიქმნა", "tool")):
        return "tool_detail"
    if any(token in text for token in ("github publish", "publish status", "publish detail", "პაბლიშ")):
        return "tool_detail"
    if any(token in text for token in ("sitemap status", "sitemap detail", "საიტმაპ")):
        return "tool_detail"
    if any(token in text for token in ("telegram status", "telegram detail", "ტელეგრამ")) and any(token in text for token in ("status", "detail", "subscriber", "მუშაობ", "რას ამბობს")):
        return "tool_detail"
    if text.strip() in {"გამარჯობა", "გამარჯობა.", "hello", "hi", "hey"}:
        return "greeting"
    if any(token in text for token in ("what is your name", "who are you", "what model", "who am i", "ვინ ხარ", "რა მოდელი", "სახელი", "ვინ ვარ")):
        return "identity"
    if any(token in text for token in ("artifact index", "არტიფაქტ", "სად ინახება", "სად ცხოვრობს artifacts")):
        return "artifact_index"
    if any(token in text for token in ("runtime access", "runtime roots", "runtime coverage", "მეტრიკაზე წვდომ", "მეტრიკებზე წვდომ", "ყველა მეტრიკ", "runtime ფოლდერ")):
        return "runtime_access"
    if "action" in text and "pending" in text:
        return "action_confirm"
    if any(token in text for token in ("action confirm", "action-confirm", "action audit", "audit log", "confirm policy", "confirmation policy", "action proposal", "pending action", "pending actions", "actions pending")):
        return "action_confirm"
    if any(token in text for token in ("internal tools", "tool registry", "რა tools", "რა ტულ", "ინსტრუმენტ")):
        return "tools_registry"
    if any(token in text for token in ("tools status", "tool status", "ტულების სტატუს", "tools წესრიგ")):
        return "tools_status"
    if any(token in text for token in ("tool runner", "action mode", "confirm-required", "confirm required")):
        return "tool_runner"
    if any(token in text for token in ("can assistant run", "run backup", "run reset", "run diagnostics", "execute tool", "execute command", "generate video", "run video", "run analytics", "analytics system", "analytics audit", "გაუშვას", "გაშვება")):
        return "action_confirm"
    if any(token in text for token in ("deeply explain", "deep denied", "denied analysis", "ღრმად", "დეტალურად")) and any(token in text for token in ("denied", "deny", "blocked", "block", "დაბლოკ", "არ გაიხსნა")):
        return "denied_deep_analysis"
    if any(token in text for token in ("blocker statistics", "blocker stats", "top blockers", "permission statistics", "სტატისტიკ")) and any(token in text for token in ("block", "permission", "ბლოკ", "denied")):
        return "blocker_statistics"
    if any(token in text for token in ("trade lifecycle", "position lifecycle", "lifecycle", "სიცოცხლის ციკლ")):
        return "trade_lifecycle"
    if any(token in text for token in ("audit recommendation", "audit recommendations", "candidate rule", "candidate rules", "strongest evidence", "რეკომენდაცი")):
        return "audit_recommendations"
    if any(token in text for token in ("permission_reason", "permission reason")) and any(token in text for token in ("signal", "signals", "სიგნალ")):
        return "signal_permission_window"
    if any(token in text for token in ("capital", "balance", "equity", "available", "კაპიტალ", "ბალანს")) and any(
        token in text for token in ("spot", "futures", "current", "snapshot", "now", "დღეს", "ახლა")
    ):
        return "capital_snapshot"
    if any(token in text for token in ("permission_reason", "permission reason")) and any(token in text for token in ("group", "count", "გვხვდება", "ხშირ")):
        return "denied_reason_window"
    if any(token in text for token in ("last 20 denied", "denied futures entries", "denied entries")) and any(token in text for token in ("group", "count", "permission")):
        return "denied_reason_window"
    if any(token in text for token in ("allowed", "denied")) and any(token in text for token in ("last 20", "ბოლო 20", "რამდენი")):
        return "signal_permission_window"
    if any(token in text for token in ("long and short performance", "long vs short", "compare long", "compare short")):
        return "side_performance"
    if any(token in text for token in ("short trades outperform", "short vs long", "short outperforming", "long trades")):
        return "side_outperformance"
    if any(token in text for token in ("biggest weakness", "ყველაზე დიდი პრობლემა", "weakness")):
        return "biggest_weakness"
    if any(token in text for token in ("files related to futures permissions", "futures permission", "permission logic")) and any(token in text for token in ("file", "path", "სად ცხოვრობს", "ფაილ")):
        return "permission_files"
    if any(token in text for token in ("older short position", "same-direction position", "open same-direction", "ძველი short", "ღია short")):
        return "denied_vs_open_position"
    if any(token in text for token in ("შეადარე", "compare", "შედარ")) and any(token in text for token in ("სიგნალ", "signal", "signals")):
        return "signal_compare"
    if any(token in text for token in ("რამდენი ფაილ", "file count", "ფაილია")):
        return "file_inventory"
    if any(token in text for token in ("მუშაობს", "გაჭედ", "health", "loop", "ციკლი", "runtime")):
        return "runtime_health"
    if any(token in text for token in ("ბოლოს რა შევცვალ", "რა შევცვალ", "change", "changed", "ცვლილებ")):
        return "changes"
    if any(token in text for token in ("ბოლო 10 trade", "ბოლო 10 ტრეიდ", "ბოლო trade", "დახურული trade", "trade რატომ", "ტრეიდ")):
        return "trade_analysis"
    if any(token in text for token in ("რომელი gate", "რომელი გეით", "რომელი blocker", "რომელი ბლოკ", "ჭარბობს", "ხშირად", "strategy audit")):
        return "strategy_audit"
    if any(token in text for token in ("დოკუმენტში რა წერია", "docs-ში", "დოკებში", "მაჩვენე", "runbook", "backup", "reset", "telegram")):
        return "docs_search"
    if any(token in text for token in ("დოკუმენტ", "დოკომენტ", "docs")) and any(
        token in text for token in ("კოდ", "code", "შეადარე", "შეუსაბამ")
    ):
        return "docs_compare"
    if any(token in text for token in ("შეადარე", "compare", "შედარ")) and any(
        token in text for token in ("სტოპ", "stop", "sl/tp", "რისკ", "სიგნალ")
    ):
        return "docs_compare"
    if any(token in text for token in ("მეტრიკ", "metric")):
        return "metrics"
    if any(token in text for token in ("რატო ვაგ", "რატომ ვაგ", "რატო ვიგ", "რატომ ვიგ", "ვაგებთ", "ვიგებთ")):
        return "win_loss"
    if "mtf" in text or "მტფ" in text:
        return "mtf"
    if "proximity" in text or "პროქსიმ" in text:
        return "proximity"
    if "entry_quality" in text or "entry quality" in text or "ენტრი" in text:
        return "entry_quality"
    if any(token in text for token in ("სტოპ", "stop loss", "sl/tp", "take profit", "რისკ")):
        return "sl_tp" if any(token in text for token in ("სტოპ", "stop loss", "sl/tp", "take profit")) else "risk_logic"
    if any(token in text for token in ("სიგნალის ლოგიკა", "signal logic", "გეითის ლოგიკა", "gate logic")):
        return "signal_logic"
    if any(token in text for token in ("საიტზე", "visitor", "analytics", "ვიზიტ", "seo", "public site", "resources", "published", "github pages")):
        return "site_analytics"
    if any(token in text for token in ("github", "გეთჰაბ", "გიტჰაბ")):
        return "github_status"
    if any(token in text for token in ("პოლიტიკ", "ახალი ამბ", "news")):
        return "news"
    if any(token in text for token in ("დიაგნოსტ", "diagnostic")):
        return "diagnostics"
    if any(token in text for token in ("დუმ", "ჩუმ", "silent", "quiet")):
        return "spot_silence"
    if any(token in text for token in ("რატომ არ გაიხსნა", "დაბლოკ", "blocker", "denied", "deny")):
        return "denied_entry"
    if any(token in text for token in ("მოგებაში", "მინუსში", "profit", "loss", "pnl")):
        return "position_pnl"
    if any(token in text for token in ("პოზიცი", "position", "trade")):
        return "position"
    if any(token in text for token in ("სიგნალ", "signal")):
        return "signal"
    if any(token in text for token in ("დღეს", "today", "overview", "მიმოხილ")):
        return "overview"
    return "unsupported"


def _detect_capability(text: str, topic: str) -> str:
    if topic == "tool_detail":
        return "tool_details"
    if topic == "runtime_access":
        return "runtime_access"
    if topic == "action_confirm":
        return "action_confirm"
    if topic in {"greeting", "identity"}:
        return "general"
    if topic == "artifact_index":
        return "artifact_index"
    if topic in {"tools_registry", "tools_status", "tool_runner"}:
        return "tools"
    if topic == "denied_deep_analysis":
        return "denied_deep_analysis"
    if topic == "blocker_statistics":
        return "blocker_statistics"
    if topic == "trade_lifecycle":
        return "trade_lifecycle"
    if topic == "audit_recommendations":
        return "audit_recommendations"
    if topic in {"metrics", "win_loss"}:
        return "metrics"
    if topic in {"side_performance", "side_outperformance", "biggest_weakness"}:
        return "trade_analysis"
    if topic in {"denied_reason_window", "signal_permission_window"}:
        return "window_analysis"
    if topic == "runtime_health":
        return "runtime_health"
    if topic == "strategy_audit":
        return "strategy_audit"
    if topic == "trade_analysis":
        return "trade_analysis"
    if topic == "docs_search":
        return "docs_search"
    if topic in {"diagnostics", "file_inventory"}:
        return "diagnostics"
    if topic == "changes":
        return "changes"
    if topic in {"signal_logic", "risk_logic", "mtf", "proximity", "entry_quality", "sl_tp", "permission_files"}:
        return "code_search"
    if topic == "docs_compare":
        return "docs_compare"
    if topic == "site_analytics":
        return "site_analytics"
    if topic == "github_status":
        return "github_status"
    if topic == "news":
        return "news"
    if topic == "unsupported":
        return "unsupported"
    return "runtime"
