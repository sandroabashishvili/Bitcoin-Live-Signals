from __future__ import annotations

from importlib import import_module
from math import isfinite
from pathlib import Path

from .config import RenderConfig
from .slides import build_intro_clip, build_outro_clip, build_story_clip


def _moviepy_builders():
    editor = import_module("moviepy.editor")
    return editor.AudioFileClip, editor.concatenate_videoclips


def _moviepy_audio_fx():
    audio_fadeout = import_module("moviepy.audio.fx.audio_fadeout").audio_fadeout
    volumex = import_module("moviepy.audio.fx.volumex").volumex
    return audio_fadeout, volumex


def _attach_audio(final_clip, config: RenderConfig):
    if not config.audio:
        return final_clip

    AudioFileClip, _ = _moviepy_builders()
    audio_fadeout, volumex = _moviepy_audio_fx()
    try:
        bed = AudioFileClip(config.audio).fx(volumex, max(0.0, min(1.0, config.audio_vol))).fx(audio_fadeout, 0.4)
        return final_clip.set_audio(bed.set_duration(final_clip.duration))
    except Exception as exc:
        print(f"[!] Audio attach skipped: {exc}")
        return final_clip


def reel_timing(count: int, duration: float, fps: int) -> list[float]:
    """Frame-aligned fixed timeline; text and item count cannot extend it."""
    if not isfinite(duration) or not 10 <= duration <= 60:
        raise ValueError("--duration must be between 10 and 60 seconds; it never grows automatically")
    if fps < 1 or not 1 <= count <= 5:
        raise ValueError("Use 1–5 news items and a positive FPS")
    total = round(duration * fps)
    intro, outro = round(1.5 * fps), round(3.5 * fps)
    each, extra = divmod(total - intro - outro, count)
    if each < 3 * fps:
        raise ValueError("Too many stories for this duration: allow at least 3 seconds per story")
    return [intro / fps, *[(each + (i < extra)) / fps for i in range(count)], outro / fps]


def build_video(
    *,
    stories: list[tuple[str, str, str]],
    config: RenderConfig,
    out_path: str,
    preview_dir: str | None = None,
) -> list[tuple[float, float, str]]:
    durations = reel_timing(len(stories), config.duration, config.fps)
    title_duration, outro_duration = durations[0], durations[-1]
    base_w = 1080
    srt_segments: list[tuple[float, float, str]] = []
    timeline = 0.0

    intro, intro_text = build_intro_clip(config, title_duration=title_duration, base_w=base_w)
    srt_segments.append((timeline, timeline + title_duration, intro_text))
    timeline += title_duration

    story_clips = []
    for number, (title, desc, source) in enumerate(stories, 1):
        per_story_duration = durations[number]
        clip, story_text = build_story_clip(
            title,
            desc,
            source,
            config=config,
            per_story_duration=per_story_duration,
            base_w=base_w,
            story_number=number,
            story_count=len(stories),
        )
        story_clips.append(clip)
        srt_segments.append((timeline, timeline + per_story_duration, story_text))
        timeline += per_story_duration

    outro, outro_text = build_outro_clip(config, outro_duration=outro_duration, base_w=base_w)
    srt_segments.append((timeline, timeline + outro_duration, outro_text))

    shortened = sum("…" in text for _, _, text in srt_segments[1:-1])
    print(f"[i] Fixed timeline: {sum(durations):g}s; {shortened} story frame(s) contain marked excerpts (…).")

    clips = [intro, *story_clips, outro]
    if preview_dir:
        directory = Path(preview_dir)
        directory.mkdir(parents=True, exist_ok=True)
        try:
            for number, clip in enumerate(clips, 1):
                clip.save_frame(str(directory / f"{number:02d}.png"), t=clip.duration / 2)
        finally:
            for clip in clips:
                clip.close()
        return srt_segments

    _, concatenate_videoclips = _moviepy_builders()
    final = concatenate_videoclips(clips, method="compose")
    final = _attach_audio(final, config)

    ffmpeg_params = ["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-profile:v", "high"]
    if not config.bitrate:
        ffmpeg_params += ["-crf", str(config.crf)]

    try:
        final.write_videofile(
            out_path,
            fps=config.fps,
            codec="libx264",
            audio=(final.audio is not None),
            audio_codec="aac",
            audio_bitrate="256k",
            preset=config.preset,
            bitrate=(config.bitrate or None),
            threads=config.threads,
            ffmpeg_params=ffmpeg_params,
        )
    finally:
        if final.audio is not None:
            final.audio.close()
        final.close()
        for clip in clips:
            clip.close()
    return srt_segments
