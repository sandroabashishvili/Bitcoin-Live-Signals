# Content rights review — 2026-09-18

User confirmed no separate publisher permissions/licenses. This is an engineering rights inventory, not a legal clearance. Germany/EU is the working jurisdiction assumption; contractual applicability and the operator's exact circumstances require professional review.

## Findings and primary sources

- Cointelegraph: https://cointelegraph.com/terms-and-privacy — section 3 expressly restricts redistribution, reproduction, automated scraping/content pipelines without prior written authorization; also restricts AI use. Do not infer permission from the RSS endpoint.
- CoinDesk: https://www.coindesk.com/terms — no specific license for this site's automated public reuse established in this audit.
- Decrypt: https://decrypt.co/terms-of-service — terms cover RSS and protected content; no permission for this site's republication established.
- CryptoSlate: https://cryptoslate.com/terms-and-conditions/ — no permission for this site's republication established.
- German law: https://www.gesetze-im-internet.de/urhg/__87g.html and https://www.gesetze-im-internet.de/urhg/BJNR012730965.html — hyperlinks/very short extracts under the publisher right are not a blanket license for photos, protected text or contractual access. Citation rules require a valid citation purpose; attribution alone is not enough. No universal safe character count was assumed.

## Implemented source policy — 2026-09-18

Default generation is enabled only for the reviewed source registry in `source_policy.py`. Unknown sources or changed feed URLs fail validation before collection. The explicit `publication_rights_reviewed=False` kill switch remains available.

### Federal Reserve Board — monetary-policy releases

- Feed: https://www.federalreserve.gov/feeds/press_monetary.xml
- RSS documentation: https://www.federalreserve.gov/feeds/feeds.htm
- Terms: https://www.federalreserve.gov/disclaimer.htm (Copyright/trademark and Seals/Logos)
- Reviewed 2026-09-18: Board information may be copied/distributed unless otherwise indicated; attribute the Board. No separate noncommercial-only condition is stated for this scope.
- Scope: feed titles and short feed excerpts, source name, publication date, direct original link. Only HTTPS Board `/newsevents/pressreleases/monetary*.htm` entries. No article scraping, attached third-party documents, authored research, photos or official seals/logos.
- Entries carrying a separate rights/copyright field are skipped. This is a technical safeguard, not proof that all future content lacks exceptions; review changes in source terms/content periodically.
- Publisher images remain disabled, including cached images. Plain source-name placeholders are used. Excerpts may be shortened; page notes explain independent aggregation and no endorsement.
- Public terms provide the basis; no individual license email was sent. No expiry is specified by these terms; no perpetual legal guarantee is inferred.

CoinDesk, Cointelegraph, Decrypt and CryptoSlate are removed from the active feed list. A global configuration flag cannot admit an unreviewed source.

Live validation: official RSS retrieved successfully; two eligible September 16 FOMC releases. Normal CLI rebuilt September 18 local HTML/JSON and the content news batch. Trading databases/services were not reset. 14 isolated tests passed.

## Remaining work before describing the site as reviewed

- The current local news page and September 18 batch now contain reviewed-source items. Older daily archives, old image assets and deployed copies still require cleanup. A 741-file inventory and private rollback copy are at `/home/sandro/runtime_archives/news_rights_20260918T202302Z/cleanup_manifest.json`. This directory is outside the public site. No remote deployment or historical content DB deletion was performed.
- Verify site operator/jurisdiction and commercial use; review Impressum, privacy/external requests and provider attribution requirements separately.
- No licensing emails were sent and no license was purchased.
- Existing WebP environment limitation remains; fixing image decoding is deferred until approved/owned image usage is defined.
- Develop the next visual preview using invented sample headlines and original CSS/SVG graphics, without publisher photos/text.

Validation: 14 isolated news tests passed; live generation succeeded.

## 2026-09-19 cleanup and Bitcoin Optech

- Added https://bitcoinops.org/feed.xml, restricted to `/en/newsletters/` entries. Podcasts, linked third-party publications, logos and photos are not reused.
- Publisher evidence: https://bitcoinops.org/en/about/ explicitly places Optech-produced materials under MIT. Exact license from https://github.com/bitcoinops/bitcoinops.github.io/blob/master/LICENSE.txt retained at public `news/licenses/bitcoin-optech-MIT.txt`, with contributor attribution and license link on each card; JSON also includes the license URL. Feed excerpts are shortened, not translated or AI-rewritten. Commercial reuse is permitted by MIT subject to its notice condition.
- Live generation: 3 current entries (Optech #423 plus two Fed FOMC releases). Limited source coverage, not a comprehensive crypto news service.
- Removed 648 local public files and 5 content DB news batches containing the four unreviewed publishers. Rollback copy: `/home/sandro/runtime_archives/news_cleanup_20260919T053331Z`. Trading databases untouched.
- Publish checkout contained much older orphaned news files: removed 4,056 stale news files, including 3,950 image assets. Old files remain in Git history/private backups; this does not erase third-party caches or search indexes.
- Added scoped generated-news deletion to the standard publisher; it requires a replacement index and leaves other website areas alone. 19 news/publisher tests passed.
- Website snapshot commit: `465bb39`. Updated sitemap excludes removed archive pages.

This section supersedes the earlier outstanding local-cleanup inventory. Other candidate sources (including SEC) are not enabled merely because found in research. No paid license or publisher contact was made.

Live verification 2026-09-19: news page HTTP 200 contains Optech #423; MIT notice HTTP 200; sampled removed September 10 archive and July 24 image both HTTP 404. Push to main succeeded. This verifies sampled live URLs, not every CDN cache.

## 2026-09-19 expanded primary sources and original illustrations

SEC added: official RSS https://www.sec.gov/news/pressreleases.rss, documented at https://www.sec.gov/about/rss-feeds. Reuse basis https://www.sec.gov/about/privacy-information (Website Dissemination); only SEC `/newsroom/press-releases/` text, filtered for crypto, Bitcoin, digital assets, tokenization, stablecoins, blockchain or ether. EDGAR filings, attachments and third-party materials excluded. Feed requested once per collection, with identified SmartSignalHub User-Agent; no access-block bypass or article scraping. Current 10 requests/second ceiling is far above this sequential feed-only usage, but applies to the entire originating IP.

ECB added: https://www.ecb.europa.eu/rss/press.html, documented at https://www.ecb.europa.eu/home/html/rss.en.html. Terms https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html permit accurate attributed reuse subject to conditions. Only institutional `/press/pr/date/` English releases; speeches, interviews, blog posts and working papers excluded. Entries with named author metadata are excluded. ECB source attribution and original unframed links retained, shortening disclosed. Current access is free; if excerpts become part of a sold product, the free-original disclosure requirement needs implementing before sale. No logos/photos reused. Future separately marked exceptions still require review.

Ethereum Foundation blog not enabled: its CC BY text license and separate automated-access prohibition in https://ethereum.org/terms-of-use/ need reconciling before this pipeline uses it.

Added original inline SVG topic illustrations (Bitcoin technology, digital-asset regulation, monetary policy). They contain no publisher assets, official seals, data-derived charts or purported event photos. Each is visibly labeled ILLUSTRATION. No image download/storage involved. Source/date and license attribution remain beside the article.

Live collection yielded six items from four sources. 20 tests passed. Headless Chromium review at 1440px and 390px found six rendered illustrations and no horizontal overflow; screenshots reviewed. HTTP responses now have a 2 MB bound. The page description reflects its actual coverage. Identical feed title/summary is displayed once with a source-reading prompt on the index.

Published as f46e21b; live verification found six cards/six original SVG illustrations with SEC and ECB present. Mobile footer links now wrap; direct browser bounds check passed. A repeated screenshot capture failed in Chromium after the initial desktop/mobile screenshots succeeded; final footer was checked through layout bounds instead.

## 2026-09-19 additional sources: BLS, BEA; CFTC held

Active publishers increased from four to six. BLS uses four explicitly listed RSS feeds, counted as one publisher: https://www.bls.gov/feed/cpi.rss, ppi.rss, empsit.rss, jolts.rss (same feed directory). Directory: https://www.bls.gov/feed/. Permission: https://www.bls.gov/opub/copyright-information.htm — BLS text is public domain; source attribution requested; emblem and third-party photos excluded. Only dated `/news.release/archives/` HTML releases accepted. General latest-numbers page was rejected because it is a mutable summary, not a dated news release.

BEA: https://apps.bea.gov/rss/rss.xml documented at https://www.bea.gov/resources/for-developers; permission https://www.bea.gov/help/faq/147 (public domain unless otherwise stated). Only www.bea.gov/news/ releases, filtered for GDP, personal income/outlays, international trade/transactions. No images or third-party materials. Both publishers are macro context, not crypto journalism.

CFTC: https://www.cftc.gov/RSS/RSSGP/rssgp.xml documented at https://www.cftc.gov/RSS/index.htm; terms https://www.cftc.gov/WebPolicy/index.htm permit reuse of government information with acknowledgement, excluding privately contributed material. Initial RSS fetch succeeded. Normal pipeline fetch and diagnostic retry returned HTTP 403, so entry remains enabled=False and is excluded before fetching/publication. No access-block bypass. To reactivate, verify access/conditions first. Relevant configured scope is crypto/digital assets and passive/decentralized software press releases only.

BLS CPI/PPI/employment/JOLTS latest releases and BEA latest releases are outside the unchanged seven-day selection window at this check. Source expansion therefore does not imply 12 current eligible stories. No dates changed, no duplicates inserted, and max_news_items stays 12. Multiple feeds per publisher are fetched once each and deduplicated together. Feed errors now report their concrete reason in the log. 23 news/publisher tests passed.

## Cryptonews RSS addition — 2026-09-19

The official homepage advertises https://cryptonews.com/feed/. Its https://cryptonews.com/disclaimer/ copyright section explicitly exempts publisher-provided RSS feeds from the preceding reproduction prohibition. Also reviewed https://cryptonews.com/terms-and-conditions/, which states general restrictions on site-content reuse. Engineering scope relies on the more specific RSS exception, not permission to scrape/reproduce full articles; this is a documented interpretation, not a universal legal clearance.

Only RSS title/short description and original cryptonews.com/news/ links are reused, attributed to Cryptonews. No article-body fetch, RSS content:encoded extraction, publisher photos, logos or third-party advertorial hosts. Source label and original link replace redundant syndication footer. Promotion filters reject tags Press Releases, Sponsored, presales, Price Analysis, Industry Talk and Gambling; existing title filters still apply. This does not guarantee that publisher labeling is perfect. The original abstract circuit illustration is labeled CRYPTO MARKETS, not Bitcoin-specific technology.

Initial live result: 12 stories, 9 Cryptonews + 1 ECB + 1 Bitcoin Optech + 1 SEC. Seven active publishers configured (CFTC still disabled); only four represented in this 48-hour selection. Existing selection window remains 48/72/96/168 hours and dated items are not relabeled as today. No perpetual guarantee of twelve eligible stories during feed outages or quiet periods. 25 news/publisher tests passed. Website RSS reuse does not silently authorize adaptation into video; video licensing/provenance work remains deferred.

Other research: Unlock Blockchain permits excerpts but reserves systematic extraction/commercial reuse for approval; not enabled. TechCrunch feed terms disallow modifying feed content, so current truncating renderer is not automatically compatible; not enabled. No publisher messages sent and no licenses purchased.

## 2026-09-19: scoped NIST expansion

- Official feed: https://www.nist.gov/news-events/news/rss.xml (40 dated entries on verification).
- Feed directory: https://www.nist.gov/coo/nist-rss-feeds explicitly describes reuse of RSS information by other websites.
- Terms: https://www.nist.gov/copyrights-disclaimers permit distribution/copying of information except marked copyrighted material and request credit. Publish only short attributed feed text; exclude separately rights-marked entries and all publisher images. No linked research-paper republication.
- Topic scope: blockchain, Bitcoin, cryptocurrency/digital assets, digital signatures, post-quantum and elliptic-curve cryptography. These cryptographic standards concern the signature infrastructure relevant to blockchain; they are not presented as price signals. Ordinary science and generic cybersecurity workforce announcements excluded.
- Cybersecurity-specific RSS returned a valid empty feed; use the official main news feed with narrow topic filtering instead. NIST is a specialist source, not a promise of daily crypto headlines.
- FCA (https://www.fca.org.uk/legal, sections 3.3/3.4/4.8) and Bank of England (https://www.bankofengland.co.uk/legal, Copyright) were reviewed but NOT enabled: general permissions do not cover this automated public republication workflow.

## 2026-09-19: NewsBTC RSS permission

Official press policy https://www.newsbtc.com/press/ explicitly invites use of https://www.newsbtc.com/feed/ on other websites. General disclaimer https://www.newsbtc.com/disclaimer/ reserves reproduction without express permission; this integration relies narrowly on the specific, still-published RSS invitation, not on a blanket right to copy articles. Both pages reviewed on 2026-09-19.

Scope: dated `/news/` links on `www.newsbtc.com`, feed headlines and short feed-description excerpts, visible attribution and direct original links. No full article extraction, `content:encoded`, publisher images/logos, translation or assumed video-reuse permission. Sponsored/press-release/gambling/presale categories excluded. Official feed verification: 10 entries, including same-day exchange infrastructure, regulation, mining/security and institutional-flow reporting. A maximum of 4 selected items applies to this publisher as to all others. Policy changes still require re-review.

## 2026-09-20 source expansion review (no source enabled)

- TechCrunch: https://techcrunch.com/rss-terms-of-use/ requires supplied feed content to remain unmodified. Current excerpt truncation is incompatible; a separate preserving renderer would be required. The cryptocurrency feed returned 20 entries, newest 2026-09-02 (conference promotion); main feed returned current general-technology entries. This does not currently improve the 48-hour crypto selection. Not enabled.
- CryptoSlate: https://cryptoslate.com/faq/ reserves copying/syndication without permission. No permission provided; not enabled.
- The Block: https://www.theblock.co/terms-service includes excerpt sharing but prohibits automated collection and restricts restricted-content RSS to readers. Do not interpret excerpt sharing as permission for this pipeline. Not enabled.
- Other search results/third-party RSS directories do not constitute publisher permission. No new license or paid service purchased and no publisher contacted.

## 2026-09-20 expanded Federal Reserve scope

Official feed directory https://www.federalreserve.gov/feeds/feeds.htm advertises the all-press feed https://www.federalreserve.gov/feeds/press_all.xml. Rechecked https://www.federalreserve.gov/disclaimer.htm: public-domain information may be copied/distributed with source credit except separately marked material; seals/logos and third-party material excluded. Existing dated press-release scope widened to allow relevant banking/liquidity/capital/financial-stability/payment releases through keyword filtering; unrelated staff appointments excluded. This is an additional feed of the same publisher, not an independent editorial source.

Economic calendar links verified at https://www.bls.gov/schedule/, https://www.bea.gov/news/schedule and https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm. Only link labels and our own descriptions are displayed, not copied calendar data.
