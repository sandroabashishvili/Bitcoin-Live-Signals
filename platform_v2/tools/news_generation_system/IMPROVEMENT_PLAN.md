# News page — current implementation and acceptance status

Updated 2026-09-20. Scope: trader-facing news and market context only. No strategy/Gate/sentiment changes.

## Implemented and verified

- Latest 48 hours, up to 12 stories. Round-robin selection prefers up to 4 per publisher, then fills spare places with the freshest remaining eligible stories. Tests cover 2+7=9 and 3 equally productive publishers receiving 4 each.
- Factual price analysis is allowed; explicit prediction/buying-guide/promotional titles and advertorial/presale/gambling categories remain excluded. Rights, host/path, date and topic checks remain in force.
- 9 enabled publishers / 13 feeds. Fed coverage expanded from monetary releases to relevant banking, capital, liquidity, payments and financial-stability announcements through its official all-press feed. Multiple feeds remain one publisher. No newly licensed independent publisher was added in this checkpoint.
- Canonical URLs and punctuation/case-normalized duplicate titles collapse; different figures are preserved. This is conservative headline deduplication, not semantic same-event clustering.
- Per-feed diagnostics record availability, dates, rejected/eligible counts and selected publisher counts. Last live collection returned 13 usable feeds and 12 selected stories (NewsBTC 7, Cryptonews 4, ECB 1).
- Displayed collection timestamp is passed from the persisted batch, not invented during HTML rendering. Original publication dates retained; future-dated entries excluded from news. Successful empty collections and total feed failure are distinguished.
- Economic-calendar section links to official BLS, BEA and FOMC schedules. It does not copy events, imply a live countdown or treat scheduled events as published news.
- Shared linked SVG banners, hover, keyboard focus, reduced-motion support; consistent title/description regions. Earlier cleanup removed unused preview_count, obsolete backoff loop, duplicate renderers and superseded CSS.
- 38 isolated news/publisher tests pass. Desktop/mobile interaction checks use Chromium at 1440/390 pixels.

## Existing automation audit

Cron service is active. Existing generation and publication jobs run separately, four times daily. Observed 2026-09-20 successful collection at 04:05 UTC and publish/push at 04:19 UTC. Although crontab contains CRON_TZ=UTC, observed generation follows the host's Berlin wall time: do not describe it as verified UTC scheduling. Configured local generation hours are 00/06/12/18, publication 06/12/18/23 (minutes 05 and 19). This can delay the midnight edition until morning publication. No schedule modified and no duplicate jobs created. Logs reside in platform_v2/runtime/logs/tools; compatibility redirects may be moved there by logging helpers.

## Explicit remaining product/engineering limitations

- More independent, frequently publishing sources still require a compatible redistribution basis. See RIGHTS_REVIEW.md for reviewed/rejected candidates. Adding a feed does not grant a license.
- An embedded event calendar, semantic same-event grouping with material-update handling, and coordinated generation/publication scheduling are not implemented.
- Multi-file publication is not transactional; overlapping invocations are not yet guarded by a shared generation/publisher lock.
- Cleanup was limited to news; no claim that the whole SmartSignalHub system is free of unused code. Image download/resize paths still have callers and were retained.
- Reels licensing/attribution integration remains separate. A website RSS permission is not assumed to authorize video adaptations.

## 2026-09-20 compact-layout correction

Supersedes the equal-reserved-text-regions layout: user screenshots showed that reserving three title/four summary lines and a 252px body created excessive whitespace. Removed fixed/minimum text/body heights and line clamps; cards now follow natural text length with a 9px content gap and top alignment. No source text fabricated or fetched to pad cards. NewsBTC feed descriptions often repeat their headlines; this is a content-quality limitation, not justification to invent summaries.

Removed selection algorithm text from the hero; retain an Updated label using the actual stored collection timestamp. Economic-calendar explanation simplified for readers. Operational window/cap rules remain documented here and in collection diagnostics. No new RSS fetch or falsely fresh timestamp for this presentation-only rebuild. 38 tests passed. Two regular editorial publishers remain an unresolved diversity limitation; this visual correction does not claim to expand them.

## 2026-09-20 responsive editorial grid and SEO audit

After user review of uneven cards, use three columns above 1100px, two through tablet widths, and one at 640px and below. Desktop/tablet cards have equal grid heights without clipping text; mobile cards retain natural height. Increase gutters to 28px and illustration proportion to 16:9. Real excerpts may show up to 320 characters (within existing stored source-policy limits). Omit feed filler that only repeats the headline; add an explicit publisher link to every card. Missing factual summaries remain a source-quality limitation. Existing archive cards receive the same presentation, preserving collection timestamps.

Live audit: main news page, archive index and all three current daily editions return HTTP 200, each has one H1, index/follow robots and a self-consistent canonical matching the sitemap. Domain-root robots.txt permits crawling and points to sitemap_index.xml, which includes the project sitemap. Social preview PNG returns 200. Main-page JSON-LD parses as a CollectionPage/Organization graph; corrected outdated organization wording that described spot-only execution. Meta description now reflects the broader financial-market coverage. No fabricated NewsArticle markup for externally published stories. Daily archives currently have no JSON-LD; optional CollectionPage/ItemList enrichment remains possible, not a crawling blocker.

Actual Google indexing, Google-selected canonicals, search impressions and ranking are NOT verified: they require the owner's Search Console URL Inspection/Pages reports. Technical eligibility and sitemap discovery do not guarantee indexing. Reference: https://developers.google.com/search/help/crawling-index-faq . No Search Console submission claimed.

## 2026-09-20 headline-only cards (accepted user direction)

Supersedes the equal-height excerpt layout: main and archived cards now show linked illustration, date/source, and full linked headline. Removed visible summaries and separate publisher CTA; retain source license attribution where applicable. Headline size 22px desktop / 20px mobile, natural card heights, existing 3/2/1 columns. Source summaries remain in the data for filtering and other consumers. Removed unused summary-rendering helper and imports. Preserved collection timestamps. Verified 1440/900/390px without horizontal overflow; 34 news tests pass.
