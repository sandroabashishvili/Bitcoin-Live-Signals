"""Reviewed feed scope; adding a URL alone never grants publication rights."""
from dataclasses import dataclass
from urllib.parse import urlsplit

@dataclass(frozen=True)
class SourcePolicy:
    feed_url: str
    terms_url: str
    reviewed_on: str
    host: str
    path_prefix: str
    enabled: bool = True
    additional_feed_urls: tuple[str, ...] = ()
    topic: str = "monetary"
    keywords: tuple[str, ...] = ()
    blocked_categories: tuple[str, ...] = ()
    reject_named_authors: bool = False
    path_suffix: str = ".htm"
    license_path: str = ""
    allow_summary: bool = False
    allow_images: bool = False

    def allows_link(self, link: str) -> bool:
        parsed = urlsplit(link)
        path = "/" + parsed.path.lstrip("/")
        return (parsed.scheme == "https" and parsed.hostname == self.host
                and path.startswith(self.path_prefix)
                and parsed.path.endswith(self.path_suffix) and ".." not in parsed.path and "%" not in parsed.path)

# Explicitly reviewed text scopes; third-party documents and images excluded.
SOURCE_POLICIES = {
    "NewsBTC": SourcePolicy(
        feed_url="https://www.newsbtc.com/feed/",
        terms_url="https://www.newsbtc.com/press/",
        reviewed_on="2026-09-19", host="www.newsbtc.com",
        path_prefix="/news/", path_suffix="/",
        topic="crypto", allow_summary=True,
        blocked_categories=("press releases", "sponsored", "sponsored posts", "presales", "advertorial", "casino", "gambling"),
    ),
    "NIST": SourcePolicy(
        feed_url="https://www.nist.gov/news-events/news/rss.xml",
        terms_url="https://www.nist.gov/copyrights-disclaimers",
        reviewed_on="2026-09-19", host="www.nist.gov",
        path_prefix="/news-events/news/", path_suffix="",
        topic="bitcoin", allow_summary=True,
        keywords=("blockchain", "bitcoin", "cryptocurrency", "digital asset", "digital signature", "post-quantum", "elliptic curve"),
    ),
    "Cryptonews": SourcePolicy(
        feed_url="https://cryptonews.com/feed/",
        terms_url="https://cryptonews.com/disclaimer/",
        reviewed_on="2026-09-19", host="cryptonews.com",
        path_prefix="/news/", path_suffix="/",
        topic="crypto", allow_summary=True,
        blocked_categories=("press releases", "sponsored", "presales", "industry talk", "gambling"),
    ),
    "CFTC": SourcePolicy(
        enabled=False,  # Initial read succeeded; subsequent live requests return HTTP 403.
        feed_url="https://www.cftc.gov/RSS/RSSGP/rssgp.xml",
        terms_url="https://www.cftc.gov/WebPolicy/index.htm",
        reviewed_on="2026-09-19", host="www.cftc.gov",
        path_prefix="/PressRoom/PressReleases/", path_suffix="",
        topic="regulation", allow_summary=True,
        keywords=("bitcoin", "crypto", "digital asset", "tokeniz", "stablecoin", "blockchain", "passive software", "decentralized"),
    ),
    "U.S. Bureau of Labor Statistics": SourcePolicy(
        feed_url="https://www.bls.gov/feed/cpi.rss",
        additional_feed_urls=("https://www.bls.gov/feed/ppi.rss", "https://www.bls.gov/feed/empsit.rss", "https://www.bls.gov/feed/jolts.rss"),
        terms_url="https://www.bls.gov/opub/copyright-information.htm",
        reviewed_on="2026-09-19", host="www.bls.gov",
        path_prefix="/news.release/archives/", path_suffix=".htm",
        topic="monetary", allow_summary=True,
    ),
    "U.S. Bureau of Economic Analysis": SourcePolicy(
        feed_url="https://apps.bea.gov/rss/rss.xml",
        terms_url="https://www.bea.gov/help/faq/147",
        reviewed_on="2026-09-19", host="www.bea.gov",
        path_prefix="/news/", path_suffix="",
        topic="monetary", allow_summary=True,
        keywords=("gdp", "gross domestic", "personal income", "outlays", "international trade", "international transactions"),
    ),
    "SEC": SourcePolicy(
        feed_url="https://www.sec.gov/news/pressreleases.rss",
        terms_url="https://www.sec.gov/about/privacy-information",
        reviewed_on="2026-09-19", host="www.sec.gov",
        path_prefix="/newsroom/press-releases/", path_suffix="",
        topic="regulation", allow_summary=True,
        keywords=("bitcoin", "crypto", "digital asset", "tokeniz", "stablecoin", "blockchain", "ether"),
    ),
    "European Central Bank": SourcePolicy(
        feed_url="https://www.ecb.europa.eu/rss/press.html",
        terms_url="https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html",
        reviewed_on="2026-09-19", host="www.ecb.europa.eu",
        path_prefix="/press/pr/date/", path_suffix=".en.html",
        topic="monetary", allow_summary=True, reject_named_authors=True,
        keywords=("monetary", "interest rate", "inflation", "consumer expectations", "digital euro", "crypto", "stablecoin", "payment", "financial stability", "liquidity"),
    ),
    "Bitcoin Optech": SourcePolicy(
        feed_url="https://bitcoinops.org/feed.xml",
        terms_url="https://bitcoinops.org/en/about/",
        reviewed_on="2026-09-19",
        host="bitcoinops.org",
        path_prefix="/en/newsletters/",
        path_suffix="/",
        topic="bitcoin",
        license_path="licenses/bitcoin-optech-MIT.txt",
        allow_summary=True,
    ),
    "Federal Reserve Board": SourcePolicy(
        feed_url="https://www.federalreserve.gov/feeds/press_monetary.xml",
        additional_feed_urls=("https://www.federalreserve.gov/feeds/press_all.xml",),
        terms_url="https://www.federalreserve.gov/disclaimer.htm",
        reviewed_on="2026-09-18",
        host="www.federalreserve.gov",
        path_prefix="/newsevents/pressreleases/",
        keywords=("fomc", "monetary", "interest rate", "liquidity", "financial stability", "capital requirements", "stress test", "crypto", "digital asset", "stablecoin", "payment"),
        allow_summary=True,
    ),
}

def validate_sources(sources: dict[str, str]) -> None:
    if not sources:
        raise ValueError("No reviewed news sources configured")
    for name, url in sources.items():
        policy = SOURCE_POLICIES.get(name)
        if policy is None or not policy.enabled or policy.feed_url != url:
            raise ValueError(f"Unreviewed news source: {name}")


def render_license(source: str, prefix: str) -> str:
    import html
    policy = SOURCE_POLICIES.get(source)
    if not policy or not policy.license_path:
        return ""
    href = html.escape(prefix + policy.license_path, quote=True)
    return f'<p class="news-card-meta">Bitcoin Optech contributors · <a href="{href}">MIT license</a></p>'


def permits_entry(source: str, title: str, summary: str, entry: dict) -> bool:
    policy = SOURCE_POLICIES[source]
    if policy.reject_named_authors and (entry.get("author") or entry.get("authors")):
        return False
    categories = {str(tag.get("term", "")).strip().casefold() for tag in entry.get("tags", []) if isinstance(tag, dict)}
    if categories.intersection(policy.blocked_categories):
        return False
    text = (title + " " + summary).casefold()
    return not policy.keywords or any(word in text for word in policy.keywords)
