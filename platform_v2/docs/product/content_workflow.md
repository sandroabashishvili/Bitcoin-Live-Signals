# Content Workflow

Status: `active baseline - implementation reviewed 2026-10-08`

Created: `2026-05-19`

Updated: `2026-10-08`

Author: Codex

Purpose: News, posts, reels, and public content workflow.

## Current Content Types

- daily news page/archive
- short video reels
- social post text
- Telegram alerts

## News Retention

Local generated news keeps a rolling `10` calendar-day window, including the
generation date. The configured limit is in
`platform_v2/public_site/news/py/news_pipeline/config.py`.

The retention rule applies to:

- `platform_v2/public_site/news/archive/YYYY-MM-DD.html`
- `platform_v2/public_site/news/data/news_items_YYYY-MM-DD.json`
- `platform_v2/public_site/assets/news/YYYY-MM-DD/`

The pipeline keeps non-date files such as `archive/index.html`, `news/index.html`, CSS, favicons, and shared assets. The goal is to keep GitHub Pages light while preserving enough recent context for reels, posts, and manual review.

Retention runs from the news generation pipeline after the latest daily page is built. The archive index is then rebuilt from the remaining dates.

The publisher also mirrors deletions for generated news artifacts. It removes
date-scoped archive HTML, daily JSON and news image files from the publication
checkout when those files no longer exist in the local source. This cleanup
runs even with incremental publishing; it requires a replacement local
`news/index.html`. General site synchronization does not use `--delete` by
default. See [SEO/publishing](seo_and_publishing.md).

## News Source and Media Policy

The news pipeline records normalized items in content SQLite and exports a
render-ready daily JSON snapshot. Feed URLs and allowed article scopes are
checked against `public_site/news/py/news_pipeline/source_policy.py`, including
source-specific host/path, topic, category and attribution rules.

The current default configuration enables the recorded publication review and
summary reuse, subject to each source's policy. Publisher-image reuse and image
downloads are disabled. Source review dates and permitted scope belong to the
source policy; adding a feed URL alone does not establish permission to reuse
its content. This document records the configured behavior, not a fresh review
of external terms. Editorial media helpers are in the same news pipeline.

## Video Reels Example

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.video_reels \
  --date YYYY-MM-DD \
  --repo-root ~/SmartSignalHub/platform_v2 \
  --max-items 3 \
  --news-indexes 3 7 11 \
  --export-srt
```

If `--out` is omitted, reels are written under runtime artifacts:

```text
/home/sandro/SmartSignalHub/platform_v2/runtime/artifacts/video_reels/
```

## Reel Inputs and Outputs

Implementation checked: `tools/video_reels/app/cli.py` and
`tools/video_reels/sources/news_source.py` on 2026-10-08.

- Input: `public_site/news/data/news_items_YYYY-MM-DD.json` under `--repo-root`.
- `--news-indexes` uses one-based indexes after invalid/no-title items are
  filtered. Supplied indexes select those items in the requested order; without
  indexes, `--max-items` selects the first items. Check the selected date's JSON
  before reusing indexes because that day's batch can be regenerated.
- `--out` selects the output directory. Relative paths resolve under
  `--repo-root`; the default is the runtime artifact directory shown above.
- The video filename is `Crypto News Highlights - <Month day, year>.mp4`.
  Reusing the same date/output directory targets the same filename.
- `--export-srt` writes a same-basename `.srt` beside the MP4.
- `--preview` renders PNG frames without video encoding into
  `preview-YYYY-MM-DD/`; with `--export-srt`, it writes `captions.srt` there.
- `--story-overrides` reads a reviewed JSON object with a `stories` list.
  Each override has a one-based `index`, an exact `expected_title`, and optional
  `title`/`summary`. Duplicate or invalid indexes and changed source titles are
  rejected. The source news JSON is not edited.
- Resolution, duration, FPS, CRF, audio and caption reserve are CLI options.
  Refer to the CLI for defaults and validation; visual review of a generated
  reel remains separate from this source check.

## Social Post Style

Current preferred post format is short:

```text
Crypto market ...
• point one
• point two
• point three
Signals:
...
News:
...
#Bitcoin #BTC #Crypto
```

The post should tease the video/news, not repeat every detail.

Use timestamps and the selected news batch when writing a social post. Check
the generated reel and subtitles before publishing. The post format above is
editorial guidance; it does not describe an automatic social upload.
