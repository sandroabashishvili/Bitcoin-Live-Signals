# SEO and Publishing

Updated: 2026-10-08 (local implementation and publication-checkout review).

Public base: https://sandro-abashishvili.de/Bitcoin-Live-Signals/
Repository: https://github.com/sandroabashishvili/Bitcoin-Live-Signals
Local publication checkout: `/home/sandro/SmartSignalHub/publish/Bitcoin-Live-Signals`.

The public remote's default branch `main` contains application source, tests and documentation. `gh-pages` contains generated static publication output. The local source checkout and nested publication checkout share the remote but use different branches. Runtime/database backups remain separate. See [source repository](../operations/source_repository.md).

## Build and publish

`python3 -m platform_v2.tools.sitemap_system` rebuilds the local source sitemap using the custom domain. `~/workspace_tools/site_publish/run.sh --dry-run` previews publication. The command without `--dry-run` can update the publication checkout, commit and push; it is a publishing action.

The publisher updates origin/gh-pages, syncs public_site to root, Spot/Futures/Hedge dashboards to their respective `*/dashboard/` paths, and shared/frontend to shared/. It rewrites local links, cleans compatibility directories and builds the final sitemap before commit/push. Default sync is incremental, without general `--delete`, but generated news has a separate targeted deletion step described below.

Canonical, Open Graph URL and JSON-LD page identity must match the final published path. Spot pages belong below `/spot/dashboard/`. September 12 fixed four renderer templates that retained old root-level identities. Diagnostics now checks published dashboard canonicals too.

The domain-root robots.txt points to `/sitemap_index.xml`, which includes the project sitemap. A project-subdirectory robots.txt is not the domain-wide robots policy.

## News and retention

Local generation retains ten calendar days including the generation date (HTML, public JSON and image assets), as configured in `platform_v2/public_site/news/py/news_pipeline/config.py`. Content SQLite stores normalized news history; public JSON is a deliberate render-ready snapshot. File retention is separate from database history. A full database reset can leave older public snapshots without corresponding content rows; recovery must be content-only and must not reimport old trades.

`prune_removed_news_artifacts` in the local workspace publisher mirrors source
deletions for `news/archive/YYYY-MM-DD.html`,
`news/data/news_items_YYYY-MM-DD.json` and files below `assets/news/`. It requires
a replacement source `news/index.html` and runs during incremental publishing
as well as full sync. The final sitemap is rebuilt after cleanup. Thus the
current publisher does not preserve old news artifacts merely because general
`--delete` is off. The 2026-10-08 local source and publication checkout both
contained ten date pages, 2026-09-29 through 2026-10-08.

This is the current implementation, not a permanent public-URL retention
promise. A longer-lived archive or redirect policy would require an explicit
change to this cleanup and corresponding index/sitemap behavior.

## Verification limits

Historical September 12 live audit: 65 sitemap URLs returned HTTP 200; four Spot
canonicals were stale. The domain sitemap index included this project. At that
checkpoint, the local source sitemap had 27 URLs and public output retained
older news archives. Those counts and retention observations are historical,
not the current publisher contract. The October 8 review checked local source
and publication files; it did not repeat a full live URL/canonical audit.

Search Console was not inspected in this pass. URL accessibility and corrected sitemap/canonical signals do not prove indexing or ranking. See Google's [sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) and [indexing FAQ](https://developers.google.com/search/help/crawling-index-faq).

Use [system review](../current/system_review_20260912.md) for the historical
September fix/test checkpoint and [operating guide](../operations/runbook.md)
for current deployment, schedules and operational boundaries.
