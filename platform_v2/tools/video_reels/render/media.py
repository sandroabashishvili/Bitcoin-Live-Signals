from __future__ import annotations

import os
from importlib import import_module
from typing import Any, Optional

import numpy as np

from .text_layout import fit_text


def _moviepy_classes():
    editor = import_module("moviepy.editor")
    return editor.ColorClip, editor.CompositeVideoClip, editor.ImageClip, editor.TextClip


def scale_px(px: int, base_w: int, width: int) -> int:
    return max(1, int(px * (width / float(base_w))))


def hex_to_rgb(hexstr: str) -> tuple[int, int, int]:
    value = hexstr.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def animated_bg(width: int, height: int, duration: float):
    ColorClip, _, _, _ = _moviepy_classes()
    return ColorClip((width, height), color=(5, 5, 7)).set_duration(duration)


def translucent_panel(width: int, height: int, duration: float, *, opacity: float = 0.72, color: tuple[int, int, int] = (7, 11, 18)):
    ColorClip, _, _, _ = _moviepy_classes()
    return ColorClip((width, height), color=color).set_opacity(opacity).set_duration(duration)


def progress_line(width: int, height: int, duration: float, *, color: str, reveal_time: float | None = None):
    """Small animated raster only; no expensive full-screen generated background."""
    VideoClip = import_module("moviepy.editor").VideoClip
    base = np.full((height, width, 3), 28, dtype=np.uint8)
    rgb = hex_to_rgb(color)
    period = reveal_time or duration

    def frame(t):
        result = base.copy()
        fraction = min(1.0, max(0.0, t / period))
        if reveal_time:
            fraction = 1 - (1 - fraction) ** 3
        result[:, :round(width * fraction)] = rgb
        return result

    return VideoClip(frame, duration=duration)


def enter_text(clip, x: int, y: int, *, distance: int = 16):
    crossfadein = import_module("moviepy.video.compositing.transitions").crossfadein
    result = clip.fx(crossfadein, 0.3)
    return result.set_position(lambda t: (x, y + round(distance * (1 - min(1.0, max(0.0, t / 0.35))) ** 3)))


def caption_block(
    text: str,
    width: int,
    max_h: int,
    base_fontsize: int,
    font: str,
    duration: float,
    *,
    align: str = "center",
    min_font: int = 28,
    stroke: int = 0,
    color: str = "#ffffff",
    stroke_color: str = "black",
    max_width_ratio: float = 0.90,
    interline: int = 2,
) -> Optional[Any]:
    if not text:
        return None

    txt = "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())
    box_w = int(width * max_width_ratio)
    padding = max(4, stroke + 2)
    layout = fit_text(
        txt, font_path=font, width=box_w - 2 * padding,
        height=max_h - 2 * padding, base_fontsize=base_fontsize,
        min_font=min_font, stroke=stroke, spacing=interline, align=align,
        color=color, stroke_color=stroke_color,
    )
    left, top, right, bottom = layout.bounds
    x = (box_w - (right - left)) / 2 - left
    if align == "left":
        x = padding - left
    elif align == "right":
        x = box_w - padding - right
    y = (max_h - (bottom - top)) / 2 - top
    canvas = np.zeros((max_h, box_w, 4), dtype=np.uint8)
    x, y = int(x), int(y)
    canvas[y:y + bottom - top, x:x + right - left] = layout.image
    ImageClip = import_module("moviepy.editor").ImageClip
    clip = ImageClip(canvas).set_duration(duration)
    clip.text_layout = layout
    return clip


def make_qr_clip(url: str, size_px: int, duration: float):
    try:
        qrcode = import_module("qrcode")
        PilImage = import_module("qrcode.image.pil").PilImage
        from PIL import Image
        ImageClip = import_module("moviepy.editor").ImageClip
    except Exception:
        return None

    qr = qrcode.QRCode(border=1, box_size=10)
    qr.add_data(url)
    qr.make(fit=True)
    img_obj = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")
    try:
        pil_img = img_obj.convert("RGB")
    except AttributeError:
        pil_img = img_obj.get_image().convert("RGB")
    try:
        resampling_nearest = Image.Resampling.NEAREST
    except AttributeError:
        # Pillow<9 fallback without direct attribute access (keeps static analyzers happy).
        resampling_nearest = getattr(Image, "NEAREST", 0)
    pil_img = pil_img.resize((size_px, size_px), resampling_nearest)
    arr = np.array(pil_img)
    arr = np.pad(arr, ((12, 12), (12, 12), (0, 0)), mode="constant", constant_values=255)
    return ImageClip(arr).set_duration(duration)


def ensure_fonts(font_regular: str, font_bold: str) -> tuple[str, str]:
    regular = font_regular if os.path.exists(font_regular) else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold = font_bold if os.path.exists(font_bold) else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return regular, bold
