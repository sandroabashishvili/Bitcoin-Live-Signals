"""Action catalog for assistant-triggered SmartSignalHub tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_v2.tools.ai_assistant.runtime_readers import PLATFORM_ROOT


@dataclass(frozen=True)
class AssistantAction:
    key: str
    title: str
    command: tuple[str, ...]
    risk: str
    confirmation: str
    assistant_scope: str
    writes_to: tuple[Path, ...]
    purpose: str
    required_input: str = ""

    @property
    def command_text(self) -> str:
        return " ".join(self.command)


ACTIONS: tuple[AssistantAction, ...] = (
    AssistantAction(
        key="diagnostics_operational",
        title="Run operational diagnostics",
        command=("python3", "-m", "platform_v2.tools.diagnostics", "--profile", "operational"),
        risk="low_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "artifacts" / "diagnostics",),
        purpose="Generate the normal operational diagnostics report.",
    ),
    AssistantAction(
        key="diagnostics_full",
        title="Run full diagnostics",
        command=("python3", "-m", "platform_v2.tools.diagnostics", "--profile", "full"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "artifacts" / "diagnostics",),
        purpose="Generate the full diagnostics report, including heavier code scans.",
    ),
    AssistantAction(
        key="backup_system",
        title="Run backup system",
        command=("python3", "-m", "platform_v2.tools.backup_system"),
        risk="medium_write",
        confirmation="manual_only",
        assistant_scope="manual_owner_action",
        writes_to=(PLATFORM_ROOT.parent.parent / "runtime_archives",),
        purpose="Create a project/runtime backup archive. This remains owner-run from terminal.",
    ),
    AssistantAction(
        key="sitemap_system",
        title="Run sitemap generation",
        command=("python3", "-m", "platform_v2.tools.sitemap_system"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "public_site",),
        purpose="Regenerate sitemap/public-site discovery assets.",
    ),
    AssistantAction(
        key="news_generation_system",
        title="Run news generation",
        command=("python3", "-m", "platform_v2.tools.news_generation_system"),
        risk="medium_write_or_network",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "public_site" / "news", PLATFORM_ROOT / "runtime" / "logs" / "tools"),
        purpose="Generate/update local public news content.",
    ),
    AssistantAction(
        key="analytics_futures_audit_suite",
        title="Run Futures analytics audit suite",
        command=("python3", "-m", "platform_v2.tools.analytics_system", "futures-audit-suite", "--date", "<YYYY-MM-DD>"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "futures" / "data",),
        purpose="Generate the standard Futures analytics reports and indicator snapshots for one date.",
        required_input="one report date, for example --date 2026-06-03",
    ),
    AssistantAction(
        key="analytics_futures_gates",
        title="Run Futures gate effectiveness analytics",
        command=("python3", "-m", "platform_v2.tools.analytics_system", "futures-gates", "--date", "<YYYY-MM-DD>"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "futures" / "data",),
        purpose="Generate Futures strategy/trade gate effectiveness reports for one date.",
        required_input="one report date, for example --date 2026-06-03",
    ),
    AssistantAction(
        key="analytics_futures_tuning",
        title="Run Futures tuning analytics",
        command=("python3", "-m", "platform_v2.tools.analytics_system", "futures-tuning", "--date", "<YYYY-MM-DD>"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "futures" / "data" / "futures_tuning_audit_reports",),
        purpose="Generate the compact Futures tuning audit report for one date.",
        required_input="one report date, for example --date 2026-06-03",
    ),
    AssistantAction(
        key="analytics_futures_short_failure",
        title="Run Futures SHORT failure analytics",
        command=("python3", "-m", "platform_v2.tools.analytics_system", "futures-short-failure", "--date", "<YYYY-MM-DD>"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "futures" / "data" / "futures_short_failure_reports",),
        purpose="Generate the Futures SHORT failure attribution report for one date.",
        required_input="one report date, for example --date 2026-06-03",
    ),
    AssistantAction(
        key="analytics_futures_indicators",
        title="Run Futures indicator analytics",
        command=("python3", "-m", "platform_v2.tools.analytics_system", "futures-indicators", "--symbol", "BTCUSDT", "--timeframes", "5m", "15m", "4h"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "futures" / "data" / "indicator_snapshots_futures",),
        purpose="Rebuild Futures indicator snapshots for the standard BTCUSDT timeframes.",
    ),
    AssistantAction(
        key="analytics_spot_indicators",
        title="Run Spot indicator analytics",
        command=("python3", "-m", "platform_v2.tools.analytics_system", "spot-indicators", "--symbol", "BTCUSDT", "--timeframes", "5m", "15m", "4h"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "spot" / "data" / "indicator_snapshots",),
        purpose="Rebuild Spot indicator snapshots for the standard BTCUSDT timeframes.",
    ),
    AssistantAction(
        key="research_futures_entry_quality",
        title="Run Futures entry-quality research replay",
        command=("python3", "-m", "platform_v2.tools.research.replay.futures_entry_quality_block_what_if", "--dates", "<YYYY-MM-DD ...>"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "artifacts" / "research" / "replay",),
        purpose="Generate a report-only Futures entry-quality denied-signal what-if audit.",
        required_input="one or more dates, for example --dates 2026-06-01 2026-06-02",
    ),
    AssistantAction(
        key="research_futures_short_zone",
        title="Run Futures SHORT-zone research replay",
        command=("python3", "-m", "platform_v2.tools.research.replay.futures_short_zone_block_what_if", "--dates", "<YYYY-MM-DD ...>"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "artifacts" / "research" / "replay",),
        purpose="Generate a report-only Futures SHORT market-plan zone denied-signal what-if audit.",
        required_input="one or more dates, for example --dates 2026-06-01 2026-06-02",
    ),
    AssistantAction(
        key="research_spot_entry_quality",
        title="Run Spot entry-quality research replay",
        command=("python3", "-m", "platform_v2.tools.research.replay.spot_entry_quality_what_if", "--dates", "<YYYY-MM-DD ...>"),
        risk="medium_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "artifacts" / "research" / "replay",),
        purpose="Generate a report-only Spot entry-quality what-if audit.",
        required_input="one or more dates, for example --dates 2026-06-01 2026-06-02",
    ),
    AssistantAction(
        key="telegram_poll_once",
        title="Run Telegram poll once",
        command=("python3", "-m", "platform_v2.tools.telegram_bot_system", "--poll-once"),
        risk="external_api_read_and_state_update",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "tools" / "telegram_bot_system" / "state",),
        purpose="Poll Telegram updates once and update local Telegram state if needed.",
    ),
    AssistantAction(
        key="telegram_set_commands",
        title="Set Telegram bot command menu",
        command=("python3", "-m", "platform_v2.tools.telegram_bot_system", "--set-commands"),
        risk="external_api_write",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "tools" / "telegram_bot_system" / "state",),
        purpose="Push the Telegram bot command menu to Telegram.",
    ),
    AssistantAction(
        key="telegram_run_forever",
        title="Run Telegram bot listener",
        command=("python3", "-m", "platform_v2.tools.telegram_bot_system", "--run-forever"),
        risk="long_running_external_poll",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "tools" / "telegram_bot_system" / "state",),
        purpose="Start the Telegram bot listener. This is long-running and must be stopped manually.",
    ),
    AssistantAction(
        key="video_reels_generate",
        title="Generate video reel",
        command=("python3", "-m", "platform_v2.tools.video_reels", "--date", "<YYYY-MM-DD>", "--export-srt"),
        risk="medium_write_and_heavy_render",
        confirmation="required",
        assistant_scope="assistant_confirm_candidate",
        writes_to=(PLATFORM_ROOT / "runtime" / "artifacts" / "video_reels",),
        purpose="Generate a vertical news reel and optional captions from local news data.",
        required_input="one date with existing news JSON, for example --date 2026-06-03",
    ),
    AssistantAction(
        key="github_publish_system",
        title="Run GitHub publish",
        command=("python3", "-m", "platform_v2.tools.github_publish_system"),
        risk="high_external_publish",
        confirmation="manual_only",
        assistant_scope="manual_owner_action",
        writes_to=(PLATFORM_ROOT / "runtime" / "logs" / "tools",),
        purpose="Publish/sync public artifacts to GitHub. This remains owner-run from terminal.",
    ),
    AssistantAction(
        key="runtime_reset_system",
        title="Run runtime reset",
        command=("python3", "-m", "platform_v2.tools.runtime_reset_system"),
        risk="high_runtime_state_change",
        confirmation="manual_only",
        assistant_scope="manual_owner_action",
        writes_to=(PLATFORM_ROOT / "runtime" / "spot", PLATFORM_ROOT / "runtime" / "futures", PLATFORM_ROOT.parent.parent / "runtime_archives"),
        purpose="Archive and reset Spot/Futures runtime state. This remains owner-run from terminal.",
    ),
    AssistantAction(
        key="runtime_start_system",
        title="Start runtime system",
        command=("python3", "-m", "platform_v2.tools.runtime_start_system"),
        risk="long_running_process",
        confirmation="manual_only",
        assistant_scope="manual_owner_action",
        writes_to=(PLATFORM_ROOT / "runtime" / "spot", PLATFORM_ROOT / "runtime" / "futures"),
        purpose="Start Spot and Futures runtime loops. This remains owner-run from terminal.",
    ),
)


def action_by_key(key: str) -> AssistantAction | None:
    for action in ACTIONS:
        if action.key == key:
            return action
    return None


def match_action(question: str) -> AssistantAction | None:
    text = question.casefold()
    for action in ACTIONS:
        if action.key in text:
            return action
    aliases = {
        "diagnostics_operational": ("diagnostics", "diagnostic", "დიაგნოსტ"),
        "backup_system": ("backup", "ბექაფ"),
        "sitemap_system": ("sitemap", "საიტმაპ"),
        "news_generation_system": ("news generation", "news tool", "ნიუს"),
        "analytics_futures_audit_suite": ("analytics audit suite", "futures audit suite", "analytics system", "run analytics", "ანალიტიკ"),
        "analytics_futures_gates": ("analytics gates", "futures gates analytics", "gate analytics"),
        "analytics_futures_tuning": ("analytics tuning", "futures tuning analytics", "tuning analytics"),
        "analytics_futures_short_failure": ("short failure analytics", "futures short failure"),
        "analytics_futures_indicators": ("futures indicator analytics", "futures indicators"),
        "analytics_spot_indicators": ("spot indicator analytics", "spot indicators"),
        "research_futures_entry_quality": ("research entry quality", "entry quality replay", "research replay", "what-if", "what if"),
        "research_futures_short_zone": ("short zone research", "short zone replay", "short zone what"),
        "research_spot_entry_quality": ("spot research", "spot replay", "spot what-if", "spot what if"),
        "telegram_poll_once": ("telegram poll", "poll once"),
        "telegram_set_commands": ("telegram set commands", "set commands"),
        "telegram_run_forever": ("telegram run forever", "telegram listener", "telegram bot run"),
        "video_reels_generate": ("video reels generate", "generate video", "video reel", "reels generate"),
        "github_publish_system": ("github publish", "publish", "პაბლიშ"),
        "runtime_reset_system": ("runtime reset", "reset", "რესეტ"),
        "runtime_start_system": ("runtime start", "start system", "გაშვება", "გაუშვი"),
    }
    for key, tokens in aliases.items():
        if any(token in text for token in tokens):
            return action_by_key(key)
    return None
