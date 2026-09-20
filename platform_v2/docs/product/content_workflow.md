# Content Workflow

Status: `active baseline - artifact paths updated on 2026-06-02`  
Created: `2026-05-19`  
Updated: `2026-09-12`  
Author: Codex  
Purpose: News, posts, reels, and public content workflow.

## Current Content Types

- daily news page/archive
- short video reels
- social post text
- Telegram alerts

## News Retention

Public news keeps a rolling `10` day window.

The retention rule applies to:

- `platform_v2/public_site/news/archive/YYYY-MM-DD.html`
- `platform_v2/public_site/news/data/news_items_YYYY-MM-DD.json`
- `platform_v2/public_site/assets/news/YYYY-MM-DD/`

The pipeline keeps non-date files such as `archive/index.html`, `news/index.html`, CSS, favicons, and shared assets. The goal is to keep GitHub Pages light while preserving enough recent context for reels, posts, and manual review.

Retention runs from the news generation pipeline after the latest daily page is built. The archive index is then rebuilt from the remaining dates.

## Video Reels Example

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.video_reels \
  --date YYYY-MM-DD \
  --repo-root ~/SmartSignalHub/platform_v2 \
  --max-items 3 \
  --news-indexes 3 7 11
```

If `--out` is omitted, reels are written under runtime artifacts:

```text
/home/sandro/SmartSignalHub/platform_v2/runtime/artifacts/video_reels/
```

## To Verify

- current reel command options
- output paths
- news index source
- subtitle generation
- social text style

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

Normalized items also live in content SQLite. The daily public JSON is a deliberate render-ready snapshot used by content/reel consumers. Local retention does not remove older public files during incremental publishing; see [SEO/publishing](seo_and_publishing.md).
