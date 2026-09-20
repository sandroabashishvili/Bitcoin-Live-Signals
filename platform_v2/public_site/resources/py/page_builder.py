"""File: page_builder.py
Folder: platform_v2/public_site/resources/py
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Build the static V2 Resources page.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from platform_v2.shared.frontend.components import (
    render_content_hero,
    render_page_head,
    render_runtime_clock_script,
    render_site_footer,
    render_site_navigation,
)


class ResourcesPageBuilder:
    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"
    _RESOURCE_CARDS_HTML = """          <article class="resource-card">
            <h2>Price Monitoring</h2>
            <p class="resource-desc">Always double-check prices across at least two sources. Use TradingView for charts; CMC and CoinGecko for aggregated market data.</p>
            <ul>
              <li><a href="https://coinmarketcap.com" target="_blank" rel="noopener"><strong>CoinMarketCap</strong>: Aggregated prices, market caps, and circulating supply.</a></li>
              <li><a href="https://www.coingecko.com" target="_blank" rel="noopener"><strong>CoinGecko</strong>: Alternative metrics, tokenomics, and categories.</a></li>
              <li><a href="https://www.tradingview.com" target="_blank" rel="noopener"><strong>TradingView</strong>: Advanced charting, alerts, and indicators.</a></li>
            </ul>
          </article>

          <article class="resource-card">
            <h2>News &amp; Analytics</h2>
            <p class="resource-desc">Stay ahead of catalysts and narratives. Read across multiple outlets to reduce bias and catch early signals.</p>
            <ul>
              <li><a href="https://cryptoslate.com" target="_blank" rel="noopener"><strong>CryptoSlate</strong>: News plus on-chain and market dashboards.</a></li>
              <li><a href="https://cointelegraph.com" target="_blank" rel="noopener"><strong>CoinTelegraph</strong>: Industry headlines and analysis.</a></li>
              <li><a href="https://decrypt.co" target="_blank" rel="noopener"><strong>Decrypt</strong>: Explainers on tech, trends, and regulation.</a></li>
            </ul>
          </article>

          <article class="resource-card">
            <h2>Macro &amp; Rates</h2>
            <p class="resource-desc">Bitcoin reacts to liquidity, rates, and major scheduled events. This category helps you catch that bigger backdrop.</p>
            <ul>
              <li><a href="https://www.cmegroup.com/fedwatch" target="_blank" rel="noopener"><strong>CME FedWatch</strong>: Tracks market-implied expectations for upcoming Fed rate decisions.</a></li>
              <li><a href="https://www.tradingeconomics.com/analytics/calendar.aspx" target="_blank" rel="noopener"><strong>Trading Economics Calendar</strong>: Useful for CPI, jobs, central-bank days, and other volatility events.</a></li>
              <li><strong>Best use:</strong> Check before major releases so a clean chart setup does not ignore macro risk.</li>
            </ul>
          </article>

          <article class="resource-card">
            <h2>Market Mood</h2>
            <p class="resource-desc">Use sentiment gauges as quick context, not as standalone trading signals. They help frame fear, heat, and crowd bias.</p>
            <ul>
              <li><a href="https://alternative.me/crypto/fear-and-greed-index/" target="_blank" rel="noopener"><strong>Fear &amp; Greed Index</strong>: Quick read on whether the market is fearful, neutral, or overheated.</a></li>
              <li><a href="https://www.blockchaincenter.net/altcoin-season-index/" target="_blank" rel="noopener"><strong>Altseason Index</strong>: Useful when you want to gauge rotation between Bitcoin dominance and altcoin strength.</a></li>
              <li><strong>Best use:</strong> Pair both with price structure and news, not with blind entries.</li>
            </ul>
          </article>

          <article class="resource-card">
            <h2>Cryptocurrency Exchanges</h2>
            <p class="resource-desc">Centralized exchanges are the usual fiat on/off ramps. Compare fees, regulation, and on-ramp methods for your region.</p>
            <ul>
              <li><a href="https://www.binance.com" target="_blank" rel="noopener"><strong>Binance</strong>: Deep liquidity, low fees, broad markets.</a></li>
              <li><a href="https://www.coinbase.com" target="_blank" rel="noopener"><strong>Coinbase</strong>: Clean UI and strong fiat rails for beginners.</a></li>
              <li><a href="https://www.kraken.com" target="_blank" rel="noopener"><strong>Kraken</strong>: Solid security, Pro terminal, robust API.</a></li>
            </ul>
          </article>

          <article class="resource-card">
            <h2>ETF Flows</h2>
            <p class="resource-desc">Spot Bitcoin ETF flows matter because they often shape short-term narrative strength and institutional participation.</p>
            <ul>
              <li><a href="https://farside.co.uk/btc/" target="_blank" rel="noopener"><strong>Farside BTC ETF Flows</strong>: Clean daily flow table across the major U.S. spot Bitcoin ETFs.</a></li>
              <li><strong>Best use:</strong> Check it alongside price action when trying to understand whether a move has broader support.</li>
              <li><strong>Why it matters:</strong> Flow data helps separate noise from real demand or persistent outflows.</li>
            </ul>
          </article>

          <article class="resource-card">
            <h2>Education &amp; Research</h2>
            <p class="resource-desc">Build your fundamentals: protocols, security models, and risk. Learn the why before you chase the yield.</p>
            <ul>
              <li><a href="https://academy.binance.com" target="_blank" rel="noopener"><strong>Binance Academy</strong>: Free crypto and blockchain courses.</a></li>
              <li><a href="https://ethereum.org" target="_blank" rel="noopener"><strong>Ethereum.org</strong>: Core docs and ecosystem resources.</a></li>
              <li><a href="https://www.cryptocompare.com" target="_blank" rel="noopener"><strong>CryptoCompare</strong>: Data, comparisons, and exchange reviews.</a></li>
            </ul>
          </article>

          <article class="resource-card">
            <h2>Security Tools</h2>
            <p class="resource-desc">Treat security as a stack: hardware wallet, cautious approvals, and on-chain data to verify flows.</p>
            <ul>
              <li><a href="https://www.ledger.com" target="_blank" rel="noopener"><strong>Ledger</strong>: Hardware wallets for long-term storage.</a></li>
              <li><a href="https://metamask.io" target="_blank" rel="noopener"><strong>MetaMask</strong>: Browser wallet with dApp support.</a></li>
              <li><a href="https://glassnode.com" target="_blank" rel="noopener"><strong>Glassnode</strong>: On-chain analytics and alerts.</a></li>
            </ul>
          </article>

          <article class="resource-card">
            <h2>Communities &amp; Forums</h2>
            <p class="resource-desc">Curate your feeds. Follow credible developers and analysts and keep a separate low-noise research account.</p>
            <ul>
              <li><a href="https://www.reddit.com/r/cryptocurrency/" target="_blank" rel="noopener"><strong>Reddit — r/Cryptocurrency</strong>: Broad community discussions.</a></li>
              <li><a href="https://bitcointalk.org" target="_blank" rel="noopener"><strong>BitcoinTalk</strong>: The classic forum for deep dives.</a></li>
              <li><a href="https://discord.com" target="_blank" rel="noopener"><strong>Discord</strong>: Join vetted crypto servers and project channels.</a></li>
            </ul>
          </article>"""

    def build_and_store(self) -> Path:
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(self.render(), encoding="utf-8")
        return self._TARGET_PATH

    def _render_head(self) -> str:
        return render_page_head(
            title="Best Crypto Tools And Resources | SmartSignalHub",
            description="Curated crypto tools, market resources, charts, research links, and practical references for SmartSignalHub Bitcoin Live Signals.",
            canonical_path="/resources/index.html",
            css_href="./css/styles.css",
            schema_json_ld="""      {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/resources/#webpage",
        "url": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/resources/",
        "name": "Best Crypto Tools And Resources | SmartSignalHub",
        "description": "Curated crypto tools, market resources, charts, research links, and practical references for SmartSignalHub Bitcoin Live Signals.",
        "isPartOf": {
          "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization"
        },
        "about": {
          "@id": "https://sandro-abashishvili.de/Bitcoin-Live-Signals/#organization"
        }
      }""",
        )

    def _render_header(self) -> str:
        return f"""      <header class="page-chrome">
        {render_content_hero(
            title="Bitcoin Tools And Market Research Resources",
            href="../resources/index.html",
            intro="A practical toolbox for checking price, narrative, macro risk, exchange access, flows, security, and research before making Bitcoin trading decisions.",
            subline=None,
            note="",
            show_runtime=False,
        )}
        {render_site_navigation(active_page="resources")}
      </header>"""

    def _render_resources_section(self) -> str:
        return f"""      <section class="resources-scope" aria-label="Resources page">
        <section class="resources-grid" aria-label="Tool categories">
{self._RESOURCE_CARDS_HTML}
        </section>
      </section>"""

    def render(self) -> str:
        generated_at = datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S UTC")
        return f"""<!DOCTYPE html>
<!-- ssh-generator: resources.py.page_builder.v2026-03-29a -->
<html lang="en">
  <head>
{self._render_head()}
  </head>
  <body>
    <main class="page">
{self._render_header()}
{self._render_resources_section()}
    </main>
    {render_site_footer(legal_prefix="../legal")}
    {render_runtime_clock_script()}
  </body>
</html>
"""
