# Sitemap System

Updated: 2026-09-12.

Run `python3 -m platform_v2.tools.sitemap_system` from the project root. The generator combines public HTML with Spot, Futures and Hedge dashboards and writes one root sitemap using `https://sandro-abashishvili.de/Bitcoin-Live-Signals`. It excludes 404/guide compatibility paths and removes the retired overview sitemap mirror.

The publisher already calls the generator on the final publication tree after synchronization/link rewriting. No second manual publish hook is needed. Local source sitemap was regenerated September 12 (27 URLs); the public tree contains additional retained news archives (65 URLs in the live audit).

Sitemap coverage does not prove Google indexing. Canonical URLs must match final dashboard paths. See [SEO/publishing](../../docs/product/seo_and_publishing.md) and [current review](../../docs/current/system_review_20260912.md).
