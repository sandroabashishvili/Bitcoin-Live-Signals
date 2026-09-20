# SEO and Publishing

Updated: 2026-09-12.

Public base: https://sandro-abashishvili.de/Bitcoin-Live-Signals/
Repository: https://github.com/sandroabashishvili/Bitcoin-Live-Signals
Local publication checkout: `/home/sandro/SmartSignalHub/publish/Bitcoin-Live-Signals`.

The public remote's default branch `main` contains application source, tests and documentation. `gh-pages` contains generated static publication output. The local source checkout and nested publication checkout share the remote but use different branches. Runtime/database backups remain separate. See [source repository](../operations/source_repository.md).

## Build and publish

`python3 -m platform_v2.tools.sitemap_system` rebuilds the local source sitemap using the custom domain. `python3 -m platform_v2.tools.github_publish_system --dry-run` previews publication. The command without `--dry-run` can update the publication checkout, commit and push; it is a publishing action.

The publisher updates origin/gh-pages, syncs public_site to root, Spot/Futures/Hedge dashboards to their respective `*/dashboard/` paths, and shared/frontend to shared/. It rewrites local links, cleans compatibility directories and builds the final sitemap before commit/push. Default sync is incremental, without general `--delete`.

Canonical, Open Graph URL and JSON-LD page identity must match the final published path. Spot pages belong below `/spot/dashboard/`. September 12 fixed four renderer templates that retained old root-level identities. Diagnostics now checks published dashboard canonicals too.

The domain-root robots.txt points to `/sitemap_index.xml`, which includes the project sitemap. A project-subdirectory robots.txt is not the domain-wide robots policy.

## News and retention

Local generation retains ten date-scoped news days (HTML, public JSON and image assets), as configured in news_pipeline/config.py. Content SQLite stores normalized news history; public JSON is a deliberate render-ready snapshot. A full database reset can leave older public snapshots without corresponding content rows; recovery must be content-only and must not reimport old trades.

Incremental publishing can retain older public archive pages after local retention removes them. The public sitemap currently includes these reachable pages. Do not blindly delete indexed pages/assets to force the public archive to match local retention; decide public URL retention/redirect policy separately.

## Verification limits

September 12 live audit: 65 sitemap URLs returned HTTP 200; four Spot canonicals were stale. The domain sitemap index includes this project. Local source sitemap has 27 current URLs; the difference includes retained public news archives.

Search Console was not inspected in this pass. URL accessibility and corrected sitemap/canonical signals do not prove indexing or ranking. See Google's [sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) and [indexing FAQ](https://developers.google.com/search/help/crawling-index-faq).

Use [system review](../current/system_review_20260912.md) for local fix/test status and the separate deployment boundary.
