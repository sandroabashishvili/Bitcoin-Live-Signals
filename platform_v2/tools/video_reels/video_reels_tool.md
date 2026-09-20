# Video Reels

Updated: 2026-08-26 · Local news excerpts with lightweight motion.

## Daily workflow — no prepared text

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.video_reels \
  --date 2026-08-24 \
  --news-indexes 1 6 9 \
  --duration 23 \
  --audio-vol 0.5 \
  --out runtime/artifacts/video_reels/auto-motion \
  --export-srt
```

Change the date and selected indexes for another edition. Without indexes the
first three valid stories are selected, not automatically ranked for importance.
No AI service, manual rewrite or editorial JSON is needed. Original news stays
unchanged. Existing videos outside `auto-motion` are not overwritten; rerunning
the same date inside that directory replaces that edition there.

Defaults: 1080x1920, 30 FPS, CRF 17, slow preset, 8 threads, 3 items, 23 seconds.
Add `--preview` for PNG frames and a preview SRT without MP4 encoding.

## Fixed duration

`--duration 23` means 23 seconds, not a target that expands with more text.
Timeline: 1.5-second intro, 18 seconds for three stories (6 each), 3.5-second outro.
Frame counts are distributed to preserve the total (rounded to one video frame).
The CLI accepts only 10–60 seconds, 1–5 stories, at least 3 seconds per story.
Invalid timing is rejected; long article text never lengthens the video.

## Automatic text handling

- Normalize whitespace and remove the recognized trailing syndication footer.
- Hide a summary that repeats the title exactly.
- Use verbatim prefixes from the headline and summary; never keyword-based
  rewrites or newly invented claims.
- Allocate a rough skim budget of 3.5 words per story-second (max 42), reserving
  some words for the summary. This is a heuristic, not a readability guarantee.
- Every shortened prefix ends in `…`, in both the image and SRT.
- Measure natural pixel height. Reduce type size only to a readable minimum,
  then shorten with `…` if still needed. Never silently crop letters.
- Normal text overflow continues rendering. Invalid boxes, missing data/tools
  and encoding failures remain genuine errors, not hidden successes.

These are excerpts, not complete summaries or verified reporting. An omitted
qualifier can matter: check the preview and link viewers to the original story.

## Visuals

Compact fixed story slots, larger body text, muted-amber story count, eased title and
summary entrance, orange revealing divider, and soft-white elapsed-time line.
Intro heading/date are fully visible at frame zero (no black fade-in); the outro
remains visible to the end. Social platforms still control their cover selection.
No expensive generated footage/backgrounds. Outro keeps the QR, then SmartSignalHub
above the full product address. Both QR and address use `--site-url`, default:
https://sandro-abashishvili.de/Bitcoin-Live-Signals/
Fonts/images are local. Existing background music is optional.

## Checks

```bash
python3 -m pytest platform_v2/tools/video_reels/tests -q
```

Tests cover raster correctness, marked overflow, fixed timing/caps, source/SRT
consistency, motion, 720p/1080p slots and input safeguards. MoviePy's ImageIO
deprecation warnings are non-blocking. Full 1080p publication encoding remains
user-run; use `--preview` first when changing the template or selected articles.

`--story-overrides` remains for compatibility with old commands, but is optional
and unused in the daily workflow. Historical `editorial/` files are not loaded
automatically. Invalid/stale explicit overrides are rejected.

Key modules: `sources/news_source.py` (input), `render/text_layout.py` (fitting),
`render/slides.py` (excerpts/layout), `render/media.py` (graphics/motion),
`render/builder.py` (bounded timeline/encoding), `output/srt.py` (subtitles).

No public publishing or migration backup is performed by this workflow.
