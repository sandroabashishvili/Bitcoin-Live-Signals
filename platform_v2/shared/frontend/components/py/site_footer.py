"""Shared site footer markup for SmartSignalHub frontend pages."""


def render_site_footer(legal_prefix: str = "../../../public_site/legal") -> str:
    return f"""
    <footer class="site-footer" aria-label="Site footer">
      <div class="site-footer-inner">
        <div class="footer-socials">
          <a class="social-facebook" href="https://www.facebook.com/CryptoNewsGeorgia" target="_blank" rel="noopener noreferrer" aria-label="Facebook">Facebook</a>
          <a class="social-linkedin" href="https://www.linkedin.com/in/aleksandre-abashishvili-03417617a/" target="_blank" rel="noopener noreferrer" aria-label="LinkedIn">LinkedIn</a>
          <a class="social-x" href="https://x.com/SAbashishvili" target="_blank" rel="noopener noreferrer" aria-label="X">X</a>
          <a class="social-github" href="https://github.com/sandroabashishvili" target="_blank" rel="noopener noreferrer" aria-label="GitHub">GitHub</a>
          <a class="social-portfolio" href="https://sandro-abashishvili.de/" target="_blank" rel="noopener noreferrer" aria-label="Portfolio">Portfolio</a>
          <a class="social-telegram" href="https://t.me/bitcoin_live_signals_bot" target="_blank" rel="noopener noreferrer" aria-label="Telegram">Telegram</a>
          <a class="social-youtube" href="https://youtube.com/@cryptonewsgeorgia?si=7yyT10A9UzRlBY6E" target="_blank" rel="noopener noreferrer" aria-label="YouTube">YouTube</a>
        </div>
        <p class="footer-copy">© 2026 Smart Signal Hub • Educational use only. Not financial advice.</p>
        <nav class="footer-legal" aria-label="Legal links">
          <a href="{legal_prefix}/impressum.html">Impressum</a>
          <a href="{legal_prefix}/datenschutz.html">Datenschutz</a>
        </nav>
      </div>
    </footer>
"""
