"""Detailed read-only summaries for project tools."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from platform_v2.tools.ai_assistant.runtime_readers import PLATFORM_ROOT, REPO_ROOT

from .contracts import CapabilityAnswer


PUBLIC_SITE = PLATFORM_ROOT / "public_site"
NEWS_DATA_DIR = PUBLIC_SITE / "news" / "data"
NEWS_ARCHIVE_DIR = PUBLIC_SITE / "news" / "archive"
SITEMAP_PATH = PUBLIC_SITE / "sitemap.xml"
TELEGRAM_SUBSCRIBERS = PLATFORM_ROOT / "tools" / "telegram_bot_system" / "state" / "subscribers.json"
BACKUP_ROOT = REPO_ROOT.parent / "SmartSignalHub_backups"
BACKUP_LOGS = (
    BACKUP_ROOT / "logs" / "backup_log.txt",
    BACKUP_ROOT / "logs" / "backup_log.txt.1",
    BACKUP_ROOT / "logs" / "backup_log.txt.2",
)
RESEARCH_REPLAY_DIR = PLATFORM_ROOT / "runtime" / "artifacts" / "research" / "replay"
VIDEO_REELS_ARTIFACT_DIR = PLATFORM_ROOT / "runtime" / "artifacts" / "video_reels"
VIDEO_REELS_STATUS = PLATFORM_ROOT / "tools" / "video_reels" / "current_status.md"
DIAGNOSTICS_ARTIFACT_DIR = PLATFORM_ROOT / "runtime" / "artifacts" / "diagnostics"
ANALYTICS_TOOL_DIR = PLATFORM_ROOT / "tools" / "analytics_system"
FUTURES_DATA_DIR = PLATFORM_ROOT / "runtime" / "futures" / "data"
SPOT_DATA_DIR = PLATFORM_ROOT / "runtime" / "spot" / "data"
PUBLISH_LOGS = (
    PLATFORM_ROOT / "runtime" / "logs" / "tools" / "github_publish_system.log",
)
NEWS_LOGS = (
    PLATFORM_ROOT / "runtime" / "logs" / "tools" / "news_generation_system.log",
)


def answer_tool_detail(question: str) -> CapabilityAnswer:
    text = question.casefold()
    if any(token in text for token in ("analytics", "analytics system", "ანალიტიკ")):
        return answer_analytics_detail()
    if any(token in text for token in ("backup", "ბექაფ")):
        return answer_backup_detail()
    if any(token in text for token in ("research", "replay", "what-if", "what if", "აუდიტ")):
        return answer_research_detail()
    if any(token in text for token in ("video", "reel", "reels", "ვიდეო")):
        return answer_video_reels_detail()
    if any(token in text for token in ("diagnostics action", "diagnostics status", "diagnostic action", "დიაგნოსტ")):
        return answer_diagnostics_action_detail()
    if any(token in text for token in ("news", "ნიუს", "ახალი ამბ")):
        return answer_news_generation_detail()
    if any(token in text for token in ("github", "publish", "გეთჰაბ", "პაბლიშ")):
        return answer_github_publish_detail()
    if any(token in text for token in ("sitemap", "საიტმაპ")):
        return answer_sitemap_detail()
    if any(token in text for token in ("telegram", "ტელეგრამ")):
        return answer_telegram_detail()
    return CapabilityAnswer("tool_details", "No detailed tool reader matched this question.")


def answer_analytics_detail() -> CapabilityAnswer:
    futures_families = (
        "futures_strategy_gate_effectiveness_reports",
        "futures_trade_gate_effectiveness_reports",
        "futures_trade_entry_audits",
        "futures_entry_timing_summaries",
        "futures_trade_audit_reports",
        "futures_short_failure_reports",
        "futures_tuning_audit_reports",
        "futures_market_plans",
        "indicator_snapshots_futures",
    )
    spot_families = ("indicator_snapshots",)
    lines = [
        "Analytics system detail",
        f"Tool folder: {ANALYTICS_TOOL_DIR}",
        f"Tool exists: {ANALYTICS_TOOL_DIR.exists()}",
        "Action-safe status:",
        "- Read-only summary is allowed.",
        "- Running analytics reports requires explicit confirmation and action audit logging.",
        "- Safe wrapper: python3 -m platform_v2.tools.analytics_system",
        "Futures analytics families:",
    ]
    for family in futures_families:
        folder = FUTURES_DATA_DIR / family
        files = _json_files_recursive(folder)
        latest = max(files, key=lambda path: path.stat().st_mtime) if files else None
        lines.append(f"- {family}: files={len(files)}, latest={_display(latest)}")
    lines.append("Spot analytics families:")
    for family in spot_families:
        folder = SPOT_DATA_DIR / family
        files = _json_files_recursive(folder)
        latest = max(files, key=lambda path: path.stat().st_mtime) if files else None
        lines.append(f"- {family}: files={len(files)}, latest={_display(latest)}")
    lines.append("Primary command candidates:")
    lines.append("- futures-audit-suite --date YYYY-MM-DD")
    lines.append("- futures-gates --date YYYY-MM-DD")
    lines.append("- futures-tuning --date YYYY-MM-DD")
    lines.append("- futures-short-failure --date YYYY-MM-DD")
    lines.append("- futures-indicators --symbol BTCUSDT --timeframes 5m 15m 4h")
    lines.append("- spot-indicators --symbol BTCUSDT --timeframes 5m 15m 4h")
    sources = tuple(
        str(path)
        for path in (
            ANALYTICS_TOOL_DIR,
            FUTURES_DATA_DIR / "futures_trade_audit_reports",
            FUTURES_DATA_DIR / "futures_tuning_audit_reports",
            FUTURES_DATA_DIR / "indicator_snapshots_futures",
            SPOT_DATA_DIR / "indicator_snapshots",
        )
        if path.exists()
    )
    return CapabilityAnswer("tool_details", "\n".join(lines), sources)


def answer_backup_detail() -> CapabilityAnswer:
    backup_dirs = [path for path in BACKUP_ROOT.glob("full_*") if path.is_dir()] if BACKUP_ROOT.exists() else []
    backup_zips = [path for path in BACKUP_ROOT.glob("full_*.zip") if path.is_file()] if BACKUP_ROOT.exists() else []
    latest_dir = max(backup_dirs, key=lambda path: path.stat().st_mtime) if backup_dirs else None
    latest_zip = max(backup_zips, key=lambda path: path.stat().st_mtime) if backup_zips else None
    manifest = latest_dir / "manifest.json" if latest_dir else None
    manifest_row = _read_json_object(manifest)
    raw_files = manifest_row.get("files")
    files = raw_files if isinstance(raw_files, list) else []
    lines = [
        "Backup detail",
        f"Backup root: {BACKUP_ROOT}",
        f"Backup folders: {len(backup_dirs)}",
        f"Backup zips: {len(backup_zips)}",
        f"Latest folder: {_display(latest_dir)}",
        f"Latest zip: {_display(latest_zip)}",
        f"Latest manifest: {_display(manifest)}",
        f"Manifest generated: {_value(manifest_row.get('generated_at'))}",
        f"Manifest file count: {len(files)}",
        "Action-safe status:",
        "- Read-only summary only. Running backup requires explicit confirmation and action audit logging.",
        "- Safe future command candidate: python3 -m platform_v2.tools.backup_system --full --sync-usb",
    ]
    lines.extend(_log_section("Backup logs", BACKUP_LOGS))
    sources = tuple(str(path) for path in (latest_dir, latest_zip, manifest, *BACKUP_LOGS) if path and path.exists())
    return CapabilityAnswer("tool_details", "\n".join(lines), sources)


def answer_research_detail() -> CapabilityAnswer:
    files = sorted(RESEARCH_REPLAY_DIR.glob("*")) if RESEARCH_REPLAY_DIR.exists() else []
    json_files = [path for path in files if path.suffix == ".json"]
    md_files = [path for path in files if path.suffix == ".md"]
    latest_json = max(json_files, key=lambda path: path.stat().st_mtime) if json_files else None
    row = _read_json_object(latest_json)
    raw_summary = row.get("summary")
    summary = raw_summary if isinstance(raw_summary, dict) else {}
    lines = [
        "Research/replay detail",
        f"Replay artifact dir: {RESEARCH_REPLAY_DIR}",
        f"JSON reports: {len(json_files)}",
        f"Markdown reports: {len(md_files)}",
        f"Latest JSON: {_display(latest_json)}",
        f"Generated: {_value(row.get('generated_at'))}",
        f"Dates: {_value(row.get('dates'))}",
        f"Symbol/timeframe/side: {_value(row.get('symbol'))} {_value(row.get('timeframe'))} {_value(row.get('side'))}",
        "Latest summary:",
    ]
    if summary:
        for key, value in summary.items():
            if key in {"blocked_rows", "outcomes", "override_candidates", "override_candidate_outcomes", "timing_counts"}:
                lines.append(f"- {key}: {value}")
    else:
        lines.append("- none found")
    lines.append("Latest report files:")
    latest_report_files = sorted(json_files + md_files, key=lambda item: item.stat().st_mtime, reverse=True)
    for path in latest_report_files[:6]:
        lines.append(f"- {_display(path)}")
    sources = tuple(str(path) for path in (latest_json, RESEARCH_REPLAY_DIR) if path and path.exists())
    return CapabilityAnswer("tool_details", "\n".join(lines), sources)


def answer_video_reels_detail() -> CapabilityAnswer:
    files = sorted(VIDEO_REELS_ARTIFACT_DIR.glob("*")) if VIDEO_REELS_ARTIFACT_DIR.exists() else []
    mp4_files = [path for path in files if path.suffix.casefold() == ".mp4"]
    srt_files = [path for path in files if path.suffix.casefold() == ".srt"]
    latest_mp4 = max(mp4_files, key=lambda path: path.stat().st_mtime) if mp4_files else None
    latest_srt = max(srt_files, key=lambda path: path.stat().st_mtime) if srt_files else None
    status_text = VIDEO_REELS_STATUS.read_text(encoding="utf-8", errors="replace") if VIDEO_REELS_STATUS.exists() else ""
    lines = [
        "Video reels detail",
        f"Artifact dir: {VIDEO_REELS_ARTIFACT_DIR}",
        f"MP4 files: {len(mp4_files)}",
        f"SRT files: {len(srt_files)}",
        f"Latest MP4: {_display(latest_mp4)}",
        f"Latest SRT: {_display(latest_srt)}",
        f"Status doc: {_display(VIDEO_REELS_STATUS)}",
    ]
    if status_text:
        lines.append("Status highlights:")
        for line in status_text.splitlines():
            clean = line.strip("- ").strip()
            if clean.startswith("#"):
                continue
            if clean and any(token in clean.casefold() for token in ("usable", "goal", "next", "generator", "blocker", "upgrade")):
                lines.append(f"- {clean}")
                if len(lines) > 15:
                    break
    lines.append("Action-safe status:")
    lines.append("- Read-only summary only. Rendering video requires explicit confirmation before running ffmpeg/movie pipeline.")
    sources = tuple(str(path) for path in (latest_mp4, latest_srt, VIDEO_REELS_STATUS) if path and path.exists())
    return CapabilityAnswer("tool_details", "\n".join(lines), sources)


def answer_diagnostics_action_detail() -> CapabilityAnswer:
    files = sorted(DIAGNOSTICS_ARTIFACT_DIR.glob("*")) if DIAGNOSTICS_ARTIFACT_DIR.exists() else []
    latest = max(files, key=lambda path: path.stat().st_mtime) if files else None
    lines = [
        "Diagnostics action-safe detail",
        f"Diagnostics artifact dir: {DIAGNOSTICS_ARTIFACT_DIR}",
        f"Reports found: {len(files)}",
        f"Latest report/artifact: {_display(latest)}",
        "Action-safe status:",
        "- Reading latest diagnostics is allowed.",
        "- Running diagnostics from chat is not enabled yet.",
        "- Safe future command candidate after confirmation: python3 -m platform_v2.tools.diagnostics --profile operational",
        "- Action audit log must be added before enabling assistant-triggered diagnostics runs.",
    ]
    sources = tuple(str(path) for path in (latest, DIAGNOSTICS_ARTIFACT_DIR) if path and path.exists())
    return CapabilityAnswer("tool_details", "\n".join(lines), sources)


def answer_news_generation_detail() -> CapabilityAnswer:
    latest_json = _latest_file(NEWS_DATA_DIR, "news_items_*.json")
    row = _read_json_object(latest_json)
    raw_items = row.get("items")
    items = raw_items if isinstance(raw_items, list) else []
    source_counts = Counter(str(item.get("source") or "unknown") for item in items if isinstance(item, dict))
    archive_files = sorted(NEWS_ARCHIVE_DIR.glob("*.html")) if NEWS_ARCHIVE_DIR.exists() else []
    lines = [
        "News generation detail",
        f"Latest data file: {_display(latest_json)}",
        f"Generated at: {_value(row.get('generated_at_utc'))}",
        f"Day: {_value(row.get('day_iso'))}",
        f"Item count: {_value(row.get('count', len(items)))}",
        f"Archive pages: {len([path for path in archive_files if path.name != 'index.html'])}",
        "Sources:",
    ]
    if source_counts:
        lines.extend(f"- {source}: {count}" for source, count in source_counts.most_common())
    else:
        lines.append("- none found")
    if items:
        lines.append("Top latest items:")
        for item in items[:5]:
            if isinstance(item, dict):
                lines.append(f"- {item.get('title')} ({item.get('source')})")
    lines.extend(_log_section("News logs", NEWS_LOGS))
    sources = tuple(str(path) for path in (latest_json, *NEWS_LOGS) if path and path.exists())
    return CapabilityAnswer("tool_details", "\n".join(lines), sources)


def answer_github_publish_detail() -> CapabilityAnswer:
    latest_log = _latest_existing(PUBLISH_LOGS)
    log_lines = _read_lines(latest_log)
    publish_events = [line for line in log_lines if "UTC]" in line or "Pushed to" in line or "Commit created" in line]
    latest_commit = _last_matching(log_lines, "Commit created")
    latest_push = _last_matching(log_lines, "Pushed to")
    sitemap_line = _last_matching(log_lines, "Sitemap rebuilt")
    pages_repo = REPO_ROOT / "publish" / "Bitcoin-Live-Signals"
    lines = [
        "GitHub publish detail",
        f"Pages repo: {pages_repo}",
        f"Pages repo exists: {pages_repo.exists()}",
        f"Latest log: {_display(latest_log)}",
        f"Latest commit event: {_value(latest_commit)}",
        f"Latest push event: {_value(latest_push)}",
        f"Latest sitemap event: {_value(sitemap_line)}",
        f"Publish event lines in latest log: {len(publish_events)}",
    ]
    lines.extend(_log_section("Publish logs", PUBLISH_LOGS))
    sources = tuple(str(path) for path in (*PUBLISH_LOGS, pages_repo) if path and path.exists())
    return CapabilityAnswer("tool_details", "\n".join(lines), sources)


def answer_sitemap_detail() -> CapabilityAnswer:
    text = SITEMAP_PATH.read_text(encoding="utf-8", errors="replace") if SITEMAP_PATH.exists() else ""
    urls = re.findall(r"<loc>(.*?)</loc>", text)
    by_area = Counter(_url_area(url) for url in urls)
    lines = [
        "Sitemap detail",
        f"Sitemap path: {SITEMAP_PATH}",
        f"Exists: {SITEMAP_PATH.exists()}",
        f"URL count: {len(urls)}",
        "URL areas:",
    ]
    if by_area:
        lines.extend(f"- {area}: {count}" for area, count in sorted(by_area.items()))
    else:
        lines.append("- none found")
    lines.append("First URLs:")
    lines.extend(f"- {url}" for url in urls[:8]) if urls else lines.append("- none found")
    return CapabilityAnswer("tool_details", "\n".join(lines), (str(SITEMAP_PATH),) if SITEMAP_PATH.exists() else ())


def answer_telegram_detail() -> CapabilityAnswer:
    rows = _read_json_list(TELEGRAM_SUBSCRIBERS)
    active = [row for row in rows if row.get("status") == "active"]
    inactive = [row for row in rows if row.get("status") == "inactive"]
    lines = [
        "Telegram bot detail",
        f"Subscribers file: {TELEGRAM_SUBSCRIBERS}",
        f"Subscribers total: {len(rows)}",
        f"Subscribers active: {len(active)}",
        f"Subscribers inactive: {len(inactive)}",
        "Active subscribers:",
    ]
    if active:
        for row in active:
            lines.append(
                f"- chat_id={row.get('chat_id')} username={row.get('username')} first_name={row.get('first_name')} updated={row.get('updated_at')}"
            )
    else:
        lines.append("- none")
    return CapabilityAnswer("tool_details", "\n".join(lines), (str(TELEGRAM_SUBSCRIBERS),) if TELEGRAM_SUBSCRIBERS.exists() else ())


def _latest_file(folder: Path, pattern: str) -> Path | None:
    if not folder.exists():
        return None
    files = [path for path in folder.glob(pattern) if path.is_file()]
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def _json_files_recursive(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(path for path in folder.rglob("*.json") if path.is_file())


def _latest_existing(paths: tuple[Path, ...]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    return max(existing, key=lambda path: path.stat().st_mtime) if existing else None


def _read_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _read_lines(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _log_section(title: str, paths: tuple[Path, ...]) -> list[str]:
    lines = [f"{title}:"]
    found = False
    for path in paths:
        if not path.exists():
            continue
        found = True
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        errors = _interesting_lines(path)
        lines.append(f"- {_display(path)} modified={modified} errors={len(errors)}")
        for item in errors[-2:]:
            lines.append(f"  error_line={item}")
    if not found:
        lines.append("- none found")
    return lines


def _interesting_lines(path: Path) -> list[str]:
    lines = _read_lines(path)
    tokens = ("error", "failed", "traceback", "exception")
    return [line.strip()[:220] for line in lines[-200:] if any(token in line.casefold() for token in tokens)]


def _last_matching(lines: list[str], pattern: str) -> str | None:
    for line in reversed(lines):
        if pattern in line:
            return line.strip()
    return None


def _url_area(url: str) -> str:
    marker = "Bitcoin-Live-Signals/"
    if marker not in url:
        return "external_or_root"
    path = url.split(marker, 1)[1].strip("/")
    if not path:
        return "home"
    return path.split("/", 1)[0]


def _display(path: Path | None) -> str:
    if path is None:
        return "--"
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _value(value: Any) -> str:
    return "--" if value in (None, "") else str(value)
