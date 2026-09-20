"""File: cli.py
Folder: platform_v2/tools/video_reels/app
Created date: 2026-05-19
Last updated date: 2026-08-26
Author: Codex
Purpose: CLI for generating video reel artifacts under platform_v2 runtime artifacts.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime

from ..output.srt import write_srt
from ..sources.news_source import parse_news_json


def _default_audio_path(repo_root: str) -> str:
    return os.path.join(repo_root, "tools", "video_reels", "assets", "music", "ambient.mp3")


def _resolve_audio_path(repo_root: str, audio_arg: str | None) -> str | None:
    candidate = os.path.expanduser(audio_arg) if audio_arg else _default_audio_path(repo_root)
    if not candidate:
        return None
    if not os.path.exists(candidate):
        print(f"[!] Audio file not found, continuing without music: {candidate}", file=sys.stderr)
        return None
    return candidate


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Generate vertical V2 news reels video.")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--repo-root", default="~/SmartSignalHub/platform_v2", help="Path to platform_v2")
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "Output dir. If omitted, writes to platform_v2/runtime/artifacts/video_reels. "
            "Relative paths are resolved under repo-root."
        ),
    )
    parser.add_argument("--max-items", type=int, default=3)
    parser.add_argument("--duration", type=float, default=23.0, help="Fixed total seconds (10–60); never extended for text")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--preset", default="slow")
    parser.add_argument("--bitrate", default="", help="Optional fixed bitrate (e.g. 8M). Leave empty to use CRF quality mode.")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--font_regular", default="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    parser.add_argument("--font_bold", default="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    parser.add_argument("--accent", default="#ff9900")
    parser.add_argument("--site-url", default="https://sandro-abashishvili.de/Bitcoin-Live-Signals/")
    parser.add_argument("--handles", nargs="*", default=["@SAbashishvili"])
    parser.add_argument("--audio", default=None, help="Optional audio path. If omitted, default ambient track is used when present.")
    parser.add_argument("--audio-vol", type=float, default=0.15)
    parser.add_argument("--export-srt", action="store_true")
    parser.add_argument("--out-res", default="1080x1920")
    parser.add_argument("--caption-reserve", type=int, default=180)
    parser.add_argument("--crf", type=int, default=17)
    parser.add_argument("--news-indexes", nargs="*", type=int, default=None)
    parser.add_argument("--story-overrides", help="Reviewed headline/summary JSON; original news stays unchanged")
    parser.add_argument("--preview", action="store_true", help="Render PNG frames and optional SRT, without encoding video")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    os.environ.setdefault("IMAGEMAGICK_FONT_RENDERING_DPI", "300")
    from ..render import RenderConfig, build_video, ensure_fonts
    from ..render.builder import reel_timing

    try:
        reel_timing(len(args.news_indexes) if args.news_indexes else args.max_items, args.duration, args.fps)
    except ValueError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        date_value = datetime.strptime(args.date, "%Y-%m-%d")
    except Exception as exc:
        print(f"[!] invalid --date: {exc}", file=sys.stderr)
        sys.exit(1)

    repo_root = os.path.expanduser(args.repo_root)
    default_out_dir = os.path.join(repo_root, "runtime", "artifacts", "video_reels")
    if args.out:
        out_dir = args.out if os.path.isabs(args.out) else os.path.join(repo_root, args.out)
    else:
        out_dir = default_out_dir
    os.makedirs(out_dir, exist_ok=True)
    audio_path = _resolve_audio_path(repo_root, args.audio)

    try:
        width_str, height_str = args.out_res.lower().split("x")
        width, height = int(width_str), int(height_str)
    except Exception:
        print("[!] --out-res must be like 1080x1920 or 720x1280", file=sys.stderr)
        sys.exit(2)

    news_json = os.path.join(repo_root, "public_site", "news", "data", f"news_items_{args.date}.json")
    if not os.path.exists(news_json):
        print(f"[!] Not found: {news_json}", file=sys.stderr)
        sys.exit(4)

    stories = parse_news_json(
        news_json, args.max_items, args.news_indexes,
        overrides_path=os.path.expanduser(args.story_overrides) if args.story_overrides else None,
    )
    if not stories:
        print("[!] No stories found.", file=sys.stderr)
        sys.exit(5)

    font_regular, font_bold = ensure_fonts(args.font_regular, args.font_bold)
    pretty_date = date_value.strftime("%B %d, %Y").replace(" 0", " ")
    safe_date = re.sub(r"[\\\\/:*?\"<>|]", "-", pretty_date)
    out_name = f"Crypto News Highlights - {safe_date}.mp4"
    out_path = os.path.join(out_dir, out_name)

    config = RenderConfig(
        date_label=pretty_date,
        width=width,
        height=height,
        duration=args.duration,
        fps=args.fps,
        preset=args.preset,
        bitrate=args.bitrate,
        threads=args.threads,
        audio=audio_path,
        audio_vol=args.audio_vol,
        site_url=args.site_url,
        accent=args.accent,
        crf=args.crf,
        caption_reserve=args.caption_reserve,
        font_regular=font_regular,
        font_bold=font_bold,
    )
    preview_dir = os.path.join(out_dir, f"preview-{args.date}") if args.preview else None
    srt_segments = build_video(
        stories=stories, config=config, out_path=out_path, preview_dir=preview_dir,
    )
    print(f"[OK] {'Preview created: ' + preview_dir if preview_dir else 'Video created: ' + out_path}")

    if args.export_srt:
        srt_path = os.path.join(preview_dir, "captions.srt") if preview_dir else os.path.splitext(out_path)[0] + ".srt"
        write_srt(srt_path, srt_segments)
        print(f"[OK] Captions exported: {srt_path}")
