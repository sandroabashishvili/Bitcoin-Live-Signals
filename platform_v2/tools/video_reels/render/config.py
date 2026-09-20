from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RenderConfig:
    date_label: str
    width: int
    height: int
    duration: float
    fps: int
    preset: str
    bitrate: str
    threads: int
    audio: str | None
    audio_vol: float
    site_url: str
    accent: str
    crf: int
    caption_reserve: int
    font_regular: str
    font_bold: str
