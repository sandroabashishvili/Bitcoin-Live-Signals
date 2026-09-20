"""Pixel-measured text fitting using the existing ImageMagick/MoviePy backend."""

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


class TextLayoutError(ValueError):
    """Even an ellipsis cannot fit in the configured caption box."""


@dataclass(frozen=True)
class TextLayout:
    text: str
    font_size: int
    bounds: tuple[int, int, int, int]
    image: np.ndarray


def excerpt(text: str, max_words: int) -> str:
    """Keep a verbatim word prefix, marking every omission explicitly."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(".,;:!?") + "…"


def fit_text(text: str, *, font_path: str, width: int, height: int,
             base_fontsize: int, min_font: int, stroke: int = 0,
             spacing: int = 2, align: str = "center",
             color: str = "#ffffff", stroke_color: str = "black") -> TextLayout:
    if min(width, height, min_font) < 1 or base_fontsize < min_font:
        raise ValueError("Invalid caption box or font range")
    TextClip = import_module("moviepy.editor").TextClip
    sizes = list(range(base_fontsize, min_font - 1, -2))
    if sizes[-1] != min_font:
        sizes.append(min_font)
    # Bound pathological feed payloads before passing them to ImageMagick.
    # This is an excerpt, never an unmarked or generated replacement headline.
    if len(text) > 4096:
        text = text[:4096].rsplit(" ", 1)[0].rstrip(".,;:!?") + "…"

    def render(candidate, size):
        # Height MUST be natural, not fixed. Otherwise clip.h always reports the
        # assigned box height even when ImageMagick has cropped the actual text.
        with TemporaryDirectory(prefix="reel-caption-") as scratch:
            # MoviePy does not populate temptxt when the caller supplies it.
            Path(scratch, "text.txt").write_text(candidate, encoding="utf-8")
            try:
                clip = TextClip(
                    candidate, method="caption", size=(width, None), fontsize=size,
                    font=font_path, color=color, align=align, interline=spacing,
                    stroke_width=stroke, stroke_color=stroke_color if stroke else None,
                    temptxt=str(Path(scratch) / "text.txt"),
                    tempfilename=str(Path(scratch) / "caption.png"),
                )
            except OSError as exc:
                if "width or height exceeds limit" in str(exc):
                    return None
                raise
        try:
            if clip.w <= width and clip.h <= height:
                pixels = clip.get_frame(0).astype(np.uint8)
                alpha = np.rint(clip.mask.get_frame(0) * 255).astype(np.uint8)
                image = np.dstack((pixels, alpha))
                return TextLayout(candidate, size, (0, 0, clip.w, clip.h), image)
        finally:
            clip.close()
        return None

    for size in sizes:
        result = render(text, size)
        if result is not None:
            return result

    # Find the longest fitting prefix at the readable minimum. Prefer whole
    # words; use character prefixes only for a single oversized token/URL.
    best = render("…", min_font)
    if best is not None:
        words = text.split()
        prefixes = ([" ".join(words[:n]) for n in range(1, len(words) + 1)]
                    if len(words) > 1 else [text[:n] for n in range(1, len(text) + 1)])
        low, high = 0, len(prefixes) - 1
        while low <= high:
            middle = (low + high) // 2
            candidate = prefixes[middle].rstrip(".,;:!?…") + "…"
            result = render(candidate, min_font)
            if result is not None:
                best, low = result, middle + 1
            else:
                high = middle - 1
        return best
    raise TextLayoutError(
        f"Caption box {width}x{height} is too small even for an ellipsis at {min_font}px."
    )
