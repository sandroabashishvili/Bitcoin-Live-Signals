from __future__ import annotations

from importlib import import_module
import re
from urllib.parse import urlsplit

from .config import RenderConfig
from .media import (animated_bg, caption_block, enter_text, make_qr_clip,
                    progress_line, scale_px, translucent_panel)
from .text_layout import excerpt


def _story_headline(title: str) -> str:
    return " ".join((title or "").split())


def _story_summary(desc: str) -> str:
    value = " ".join((desc or "").split())
    return re.sub(r"\s+The post .+ appeared first on [^.]+\.?$", "", value).strip()


def _bottom_safe_padding(config: RenderConfig, base_w: int) -> int:
    return max(int(config.caption_reserve), scale_px(190, base_w, config.width))


def _safe_content_bounds(config, panel_top, panel_h, *, top_pad, bottom_pad, base_w):
    top = panel_top + top_pad
    bottom = min(panel_top + panel_h - bottom_pad,
                 config.height - _bottom_safe_padding(config, base_w))
    if bottom <= top:
        raise ValueError("Caption reserve leaves no usable content area")
    return top, bottom


def _caption(config, text, height, size, duration, *, bold=False, color="#ffffff", min_size=None):
    scale = lambda n: scale_px(n, 1080, config.width)
    return caption_block(text, config.width, scale(height), scale(size),
                         config.font_bold if bold else config.font_regular, duration,
                         min_font=scale(min_size or size), max_width_ratio=0.82,
                         stroke=0, color=color)


def _place(layers, clip, config, y, *, motion=False):
    if clip is None:
        return
    x = (config.width - clip.w) // 2
    layers.append(enter_text(clip, x, y, distance=scale_px(16, 1080, config.width))
                  if motion else clip.set_position((x, y)))


def _finish(layers, config, *, fade_in=True, fade_out=True):
    editor = import_module("moviepy.editor")
    fadein = import_module("moviepy.video.fx.fadein").fadein
    fadeout = import_module("moviepy.video.fx.fadeout").fadeout
    clip = editor.CompositeVideoClip(layers, size=(config.width, config.height))
    if fade_in:
        clip = clip.fx(fadein, 0.12)
    if fade_out:
        clip = clip.fx(fadeout, 0.12)
    return clip


def _panel(config, duration):
    top, height = int(config.height * 0.19), scale_px(1030, 1080, config.width)
    start, end = _safe_content_bounds(config, top, height, top_pad=0, bottom_pad=0, base_w=1080)
    if end - start < height:
        raise ValueError("Story panel does not fit the content area; check resolution/caption reserve")
    return [animated_bg(config.width, config.height, duration),
            translucent_panel(int(config.width * 0.92), height, duration, opacity=0.60,
                              color=(12, 17, 24)).set_position(("center", top))], top


def build_intro_clip(config, *, title_duration, base_w):
    layers, top = _panel(config, title_duration)
    scale = lambda n: scale_px(n, base_w, config.width)
    label = _caption(config, "SMARTSIGNALHUB", 65, 34, title_duration, color=config.accent)
    title = _caption(config, "Crypto News\nBrief", 320, 96, title_duration, bold=True, min_size=80)
    date = _caption(config, config.date_label, 90, 44, title_duration)
    _place(layers, label, config, top + scale(165))
    # The first encoded frame must already be a readable cover, not a fade
    # from black or an invisible animated heading.
    _place(layers, title, config, top + scale(270))
    _place(layers, progress_line(scale(330), scale(5), title_duration,
                               color=config.accent, reveal_time=0.65), config, top + scale(650))
    _place(layers, date, config, top + scale(715))
    return _finish(layers, config, fade_in=False), f"Crypto News Brief\n{date.text_layout.text}"


def prepare_story(title, summary, seconds):
    """Deterministic verbatim excerpts, not AI-written replacement claims."""
    title, summary = _story_headline(title), _story_summary(summary)
    if summary.casefold().rstrip(".") == title.casefold().rstrip("."):
        summary = ""
    # Budget for a quick skim, excluding the small source label. Actual reading
    # speed varies. Duration never changes to accommodate the text.
    budget = max(8, min(42, int(seconds * 3.5)))
    title_budget = max(6, budget - 6) if summary else budget
    headline = excerpt(title, title_budget)
    remaining = max(0, budget - len(headline.split()))
    description = excerpt(summary, remaining) if summary and remaining else ""
    return headline, description


def build_story_clip(title, desc, source, *, config, per_story_duration, base_w,
                     story_number=1, story_count=3):
    layers, top = _panel(config, per_story_duration)
    scale = lambda n: scale_px(n, base_w, config.width)
    headline, summary = prepare_story(title, desc, per_story_duration)
    label = _caption(config, f"NEWS  {story_number:02d} / {story_count:02d}", 64, 32,
                     per_story_duration, color="#d9a441")
    title_clip = _caption(config, headline, 320, 76, per_story_duration, bold=True, min_size=58)
    desc_clip = _caption(config, summary, 230, 56, per_story_duration, min_size=48)
    source_clip = _caption(config, f"Source: {source.strip()}" if source else "", 78, 34,
                           per_story_duration, color="#b7c0cb", min_size=30)
    _place(layers, label, config, top + scale(52))
    _place(layers, title_clip, config, top + scale(145), motion=True)
    _place(layers, progress_line(scale(320), scale(5), per_story_duration,
                               color=config.accent, reveal_time=0.65), config, top + scale(495))
    _place(layers, desc_clip, config, top + scale(535), motion=True)
    _place(layers, source_clip, config, top + scale(805))
    _place(layers, progress_line(scale(800), scale(4), per_story_duration,
                               color="#d6dce5"), config, top + scale(953))
    # Use actual displayed excerpts, including pixel-fitting ellipses, in SRT.
    shown = [clip.text_layout.text for clip in (title_clip, desc_clip) if clip is not None]
    return _finish(layers, config), "\n".join(shown)


def build_outro_clip(config, *, outro_duration, base_w):
    layers, top = _panel(config, outro_duration)
    scale = lambda n: scale_px(n, base_w, config.width)
    title = _caption(config, "SmartSignalHub", 100, 64, outro_duration, bold=True, min_size=54)
    qr = make_qr_clip(config.site_url, scale(360), outro_duration)
    url = urlsplit(config.site_url)
    address = url.netloc + url.path + ("?" + url.query if url.query else "") + ("#" + url.fragment if url.fragment else "")
    link = _caption(config, address, 100, 32, outro_duration, min_size=28)
    label = _caption(config, "Signals · Market news", 65, 34, outro_duration, color="#b7c0cb")
    _place(layers, qr, config, top + scale(120))
    _place(layers, title, config, top + scale(570), motion=True)
    _place(layers, link, config, top + scale(690))
    _place(layers, label, config, top + scale(835))
    return _finish(layers, config, fade_out=False), f"SmartSignalHub\n{link.text_layout.text}\nSignals · Market news"
