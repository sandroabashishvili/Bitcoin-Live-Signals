"""Shared linked media for latest and archive news cards."""
import html
from .editorial_visuals import render_editorial_visual


def render_card_media(*, title: str, link: str, source: str, image_path: str | None, asset_prefix: str) -> str:
    label = html.escape(f"Read at {source}: {title} (opens in a new tab)", quote=True)
    href = html.escape(link, quote=True)
    if image_path:
        src = html.escape(asset_prefix + image_path.removeprefix("../"), quote=True)
        content = f'<img src="{src}" alt="" loading="lazy" />'
        css = "news-card-media"
    else:
        content = render_editorial_visual(source, title=title, identity=link)
        css = "news-card-illustration-link"
    return f'<a class="{css}" href="{href}" target="_blank" rel="noopener" aria-label="{label}">{content}</a>'

