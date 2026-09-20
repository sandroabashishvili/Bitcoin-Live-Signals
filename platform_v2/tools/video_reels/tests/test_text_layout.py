import json
from pathlib import Path

import pytest

from platform_v2.tools.video_reels.app.cli import build_arg_parser
from platform_v2.tools.video_reels.render.media import caption_block
from platform_v2.tools.video_reels.render.slides import _story_headline, _story_summary
from platform_v2.tools.video_reels.render.slides import build_story_clip, build_intro_clip, build_outro_clip
from platform_v2.tools.video_reels.render.slides import prepare_story
from platform_v2.tools.video_reels.render.builder import reel_timing
from platform_v2.tools.video_reels.render.media import progress_line
from platform_v2.tools.video_reels.render.config import RenderConfig
from platform_v2.tools.video_reels.render.text_layout import TextLayoutError, fit_text
from platform_v2.tools.video_reels.sources.news_source import parse_news_json


FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
pytestmark = pytest.mark.skipif(not Path(FONT).exists(), reason="DejaVu font required")


def fit(text, **kwargs):
    params = dict(font_path=FONT, width=880, height=380, base_fontsize=70, min_font=36)
    return fit_text(text, **(params | kwargs))


@pytest.mark.parametrize("text", [
    "Bitcoin ETF inflows hit $1.9B in strongest week since October 2025",
    "Bitcoin weekend blip wiped out $250M in over leveraged long traders while open interest weakens",
    "Banks, regulators join quantum-resistant crypto transfer pilot",
    "U.S. ETF inflows grew 2.65%. Banks will test transfers.",
    "Short title",
])
def test_whole_text_is_retained_and_measured(text):
    layout = fit(text)
    assert " ".join(layout.text.split()) == text
    left, top, right, bottom = layout.bounds
    assert right - left <= 880
    assert bottom - top <= 380


def test_long_word_keeps_every_character():
    text = "quantum" * 12
    layout = fit(text)
    assert layout.text.replace("\n", "") == text


def test_minimum_font_is_tried():
    assert fit("Fits", base_fontsize=36, min_font=36).font_size == 36


def test_raster_is_actual_text_not_temporary_filename():
    import numpy as np
    from moviepy.editor import TextClip

    layout = fit("Hello Bitcoin", base_fontsize=36, min_font=36)
    expected = TextClip("Hello Bitcoin", method="caption", size=(880, None),
                        fontsize=36, font=FONT, color="#ffffff", align="center",
                        interline=2, stroke_width=0, stroke_color=None)
    try:
        assert layout.image.shape[:2] == (expected.h, expected.w)
        assert np.array_equal(layout.image[:, :, :3], expected.get_frame(0))
    finally:
        expected.close()


def test_overflow_is_marked_instead_of_failing():
    text = "A very long paragraph " * 100
    result = fit(text, height=60)
    assert result.text.endswith("…")
    assert text.startswith(result.text[:-1])
    assert result.bounds[3] <= 60


def test_impossible_box_is_a_configuration_error():
    with pytest.raises(TextLayoutError, match="ellipsis"):
        fit("Text", width=1, height=1)


def test_long_headline_has_no_market_specific_rewrite():
    title = "Bitcoin falls below $80,000 as ETF outflows increase"
    assert _story_headline(title) == title


def test_summary_removes_only_syndication_footer():
    summary = "Open interest fell 2.65%. Funding stayed near baseline."
    assert _story_summary(summary + " The post Some story appeared first on CryptoSlate.") == summary
    assert _story_summary(summary) == summary


def test_fixed_caption_box_and_pixel_padding():
    for text in ["Short title", "A much longer title that must wrap but keep the same box height"]:
        clip = caption_block(text, 1080, 300, 70, FONT, 1, min_font=36, stroke=2)
        try:
            assert clip.h == 300
            mask = clip.mask.get_frame(0)
            assert mask.max() > 0
            assert not mask[0].any() and not mask[-1].any()
            assert not mask[:, 0].any() and not mask[:, -1].any()
        finally:
            clip.close()


def source_file(tmp_path):
    source = tmp_path / "news.json"
    source.write_text(json.dumps({"items": [{"title": "Original title", "summary": "Complete summary.", "source": "News"}]}))
    return source


def test_override_keeps_raw_source_unchanged(tmp_path):
    source = source_file(tmp_path)
    before = source.read_bytes()
    overrides = tmp_path / "reviewed.json"
    overrides.write_text(json.dumps({"stories": [{"index": 1, "expected_title": "Original title", "title": "Reviewed title", "summary": ""}]}))
    assert parse_news_json(str(source), 1, [1], overrides_path=str(overrides)) == [("Reviewed title", "", "News")]
    assert source.read_bytes() == before


def test_stale_override_is_rejected(tmp_path):
    source = source_file(tmp_path)
    overrides = tmp_path / "reviewed.json"
    overrides.write_text(json.dumps({"stories": [{"index": 1, "expected_title": "Different title"}]}))
    with pytest.raises(ValueError, match="changed"):
        parse_news_json(str(source), 1, [1], overrides_path=str(overrides))


def test_invalid_index_is_not_silently_ignored(tmp_path):
    with pytest.raises(ValueError, match="indexes"):
        parse_news_json(str(source_file(tmp_path)), 3, [1, 6, 9])


def test_cli_new_domain_and_preview():
    args = build_arg_parser().parse_args(["--date", "2026-08-24", "--preview"])
    assert args.preview
    assert args.site_url == "https://sandro-abashishvili.de/Bitcoin-Live-Signals/"
    assert args.duration == 23 and args.max_items == 3
    assert args.story_overrides is None


def config(width=1080, height=1920, reserve=180):
    return RenderConfig("August 24, 2026", width, height, 23, 30, "ultrafast", "", 2,
                        None, 0.5, "https://sandro-abashishvili.de/Bitcoin-Live-Signals/",
                        "#ff9900", 17, reserve, FONT, FONT.replace(".ttf", "-Bold.ttf"))


@pytest.mark.parametrize("width,height", [(1080, 1920), (720, 1280)])
def test_story_slots_stay_aligned_and_srt_complete(width, height):
    positions = []
    for title, summary in [("Short title", ""), ("Banks join quantum-resistant crypto pilot", "Banks will test wallets and transfers; regulators initially observe.")]:
        clip, srt = build_story_clip(title, summary, "Cointelegraph", config=config(width, height),
                                    per_story_duration=6, base_w=1080)
        try:
            assert srt == (f"{title}\n{summary}" if summary else title)
            captions = [layer for layer in clip.clips if hasattr(layer, "text_layout")]
            positions.append((captions[1].pos(1), captions[-1].pos(1)))
            frame = clip.get_frame(3)
            for layer in captions:
                top = int(layer.pos(1)[1])
                assert top + layer.h < height - 180
                region = frame[top:top + layer.h]
                assert (region > 200).sum() > 100  # Not invisible black glyphs.
        finally:
            clip.close()
    assert positions[0] == positions[1]


def test_excessive_caption_reserve_fails():
    with pytest.raises(ValueError, match="content area"):
        build_story_clip("Title", "Summary.", "Source", config=config(reserve=1900),
                         per_story_duration=6, base_w=1080)


@pytest.mark.parametrize("width,height", [(720,1280), (1080,1920)])
def test_first_frame_has_readable_heading_and_date(width, height):
    import numpy as np
    clip, _ = build_intro_clip(config(width, height), title_duration=1.5, base_w=1080)
    try:
        frame = clip.get_frame(0)
        captions = [layer for layer in clip.clips if hasattr(layer, "text_layout")]
        assert len(captions) == 3
        for layer in captions:
            x, y = layer.pos(0)
            region = frame[y:y + layer.h, x:x + layer.w]
            assert (region > 160).sum() > 200
            assert np.array_equal(layer.get_frame(0), layer.get_frame(0.5))
        assert "Crypto News" in captions[1].text_layout.text
    finally:
        clip.close()


def test_outro_keeps_qr_brand_before_complete_product_link(monkeypatch):
    import numpy as np
    from platform_v2.tools.video_reels.render import slides
    target_urls = []
    actual_qr = slides.make_qr_clip
    def qr(url, size, duration):
        target_urls.append(url)
        return actual_qr(url, size, duration)
    monkeypatch.setattr(slides, "make_qr_clip", qr)
    cfg = config()
    clip, srt = build_outro_clip(cfg, outro_duration=3.5, base_w=1080)
    try:
        captions = [layer for layer in clip.clips if hasattr(layer, "text_layout")]
        assert target_urls == [cfg.site_url]
        assert captions[0].text_layout.text == "SmartSignalHub"
        assert captions[1].text_layout.text == cfg.site_url.removeprefix("https://")
        assert "…" not in captions[1].text_layout.text
        assert captions[0].pos(1)[1] < captions[1].pos(1)[1]
        assert srt.startswith("SmartSignalHub\n") and "/news" not in srt
        assert np.array_equal(clip.get_frame(1), clip.get_frame(3.49))
        # An actual black-and-white QR image is still present, not just its label.
        assert any(layer.w < 500 and layer.h > 300 for layer in clip.clips)
    finally:
        clip.close()


@pytest.mark.parametrize("count,duration,fps", [(3,23,30), (3,23,10), (1,10,30), (5,23,30), (5,60,30), (3,23.1,30)])
def test_timeline_never_grows(count, duration, fps):
    timing = reel_timing(count, duration, fps)
    assert sum(timing) == pytest.approx(round(duration * fps) / fps)
    assert len(timing) == count + 2
    assert all(t * fps == pytest.approx(round(t * fps)) for t in timing)


@pytest.mark.parametrize("count,duration,fps", [(3,600,30), (3,float("nan"),30), (0,23,30), (6,23,30), (5,10,30), (3,23,0)])
def test_invalid_timeline_cannot_create_a_long_video(count, duration, fps):
    with pytest.raises(ValueError):
        reel_timing(count, duration, fps)


def test_automatic_excerpts_are_verbatim_and_bounded():
    title = "Bitcoin weekend blip wiped out $250M in over leveraged long traders while open interest weakens during the weekend"
    summary = "Open interest fell 2.65% and funding stayed near baseline, pointing to leverage clearing rather than longs rebuilding."
    head, desc = prepare_story(title, summary, 6)
    assert head.endswith("…") and desc.endswith("…")
    assert title.startswith(head[:-1]) and summary.startswith(desc[:-1])
    assert len((head + " " + desc).split()) <= 21


def test_progress_line_actually_moves():
    import numpy as np
    clip = progress_line(100, 4, 6, color="#ff9900")
    try:
        assert not np.array_equal(clip.get_frame(1), clip.get_frame(4))
        assert (clip.get_frame(0) == 28).all()
        assert (clip.get_frame(6)[:, :, 0] == 255).all()
    finally:
        clip.close()


def test_long_story_srt_matches_visible_ellipsis_and_motion():
    import numpy as np
    clip, srt = build_story_clip("A longer headline " * 30, "A lengthy summary " * 30, "Source",
                                 config=config(), per_story_duration=6, base_w=1080)
    try:
        captions = [layer for layer in clip.clips if hasattr(layer, "text_layout")]
        assert srt == "\n".join(layer.text_layout.text for layer in captions[1:3])
        assert "…" in srt
        assert captions[1].pos(0)[1] > captions[1].pos(1)[1]
        assert not np.array_equal(clip.get_frame(1), clip.get_frame(4))
    finally:
        clip.close()


def test_story_counter_uses_muted_amber_not_grey_or_bright_accent():
    import numpy as np
    clip, _ = build_story_clip("Bitcoin market update", "A concise market summary.", "Source",
                               config=config(), per_story_duration=6, base_w=1080)
    try:
        label = next(layer for layer in clip.clips
                     if getattr(getattr(layer, "text_layout", None), "text", "").startswith("NEWS"))
        pixels = label.get_frame(1)
        visible = pixels[pixels.max(axis=2) > 80]
        median = np.median(visible, axis=0)
        assert median[0] > median[1] > median[2]
        assert median[1] > 110  # Visible amber, not the previous pale grey.
    finally:
        clip.close()
