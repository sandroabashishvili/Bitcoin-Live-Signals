"""File: image_processor.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Download, validate, resize, and map news images into V2 frontend-owned assets.
"""

from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path
from urllib.error import URLError

from PIL import Image, UnidentifiedImageError

from .config import V2NewsPipelineConfig
from .http_client import urlread
from .paths import daily_news_assets_dir, news_frontend_dir
from .utils import ensure_dirs, safe_name


logger = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = 50_000_000

try:
    RESAMPLE = Image.Resampling.LANCZOS
except (AttributeError, ImportError):
    RESAMPLE = 1


def _open_rgb_image(raw_bytes: bytes) -> Image.Image | None:
    """Validate and convert downloaded bytes into an RGB Pillow image."""

    image: Image.Image | None = None
    try:
        image = Image.open(BytesIO(raw_bytes))
        image.verify()
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        logger.warning("Failed to verify downloaded image: %s", exc)
        image = None
    return image


def _build_resized_image(image: Image.Image, target_width: int) -> tuple[Image.Image, int]:
    """Resize an image to a target width while preserving aspect ratio."""

    ratio = target_width / image.width
    target_height = max(1, int(image.height * ratio))
    return image.resize((target_width, target_height), RESAMPLE), target_height


def _to_frontend_relative(asset_path: Path, frontend_root: Path) -> str:
    relative_path = asset_path.relative_to(frontend_root).as_posix()
    return f"../{relative_path}"


def download_and_resize(url: str, day_iso: str, config: V2NewsPipelineConfig) -> dict[str, object] | None:
    """Download an image, create base/thumb JPGs, and return page-ready metadata."""

    image_data: dict[str, object] | None = None
    try:
        out_dir = daily_news_assets_dir(config, day_iso)
        ensure_dirs(out_dir)
        image = _open_rgb_image(urlread(url))
        if image is None:
            return None

        base_width = min(max(image.width, config.thumb_width), config.max_image_width)
        thumb_width = config.thumb_width

        base_image, base_height = _build_resized_image(image, base_width)
        base_path = out_dir / f"{safe_name(url)}_base.jpg"
        base_image.save(base_path, "JPEG", quality=config.image_quality)

        thumb_image, thumb_height = _build_resized_image(image, thumb_width)
        thumb_path = out_dir / f"{safe_name(url)}_thumb.jpg"
        thumb_image.save(thumb_path, "JPEG", quality=config.image_quality)

        frontend_root = news_frontend_dir(config).parent
        base_web_path = _to_frontend_relative(base_path, frontend_root)
        thumb_web_path = _to_frontend_relative(thumb_path, frontend_root)

        image_data = {
            "src_jpg": base_web_path,
            "srcset_jpg": f"{thumb_web_path} {thumb_width}w, {base_web_path} {base_width}w",
            "width": base_width,
            "height": base_height,
            "thumb_width": thumb_width,
            "thumb_height": thumb_height,
        }
    except (OSError, URLError, UnidentifiedImageError, ValueError) as exc:
        logger.warning("Failed to process image %s: %s", url, exc)
    return image_data
