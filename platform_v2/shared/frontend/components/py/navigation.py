"""Shared site navigation for SmartSignalHub frontend pages."""

from __future__ import annotations

import html


_PRIMARY_NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("overview_spot", "Overview"),
    ("portfolio", "Portfolio"),
    ("trade_outcomes", "Trade"),
    ("strategy_edge", "Strategy"),
    ("orderbook", "Orderbook"),
)

_FUTURES_NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("overview_futures", "Overview"),
    ("portfolio_futures", "Portfolio"),
    ("trade_outcomes_futures", "Trade"),
    ("strategy_edge_futures", "Strategy"),
    ("orderbook_futures", "Orderbook"),
)

_DASHBOARD_PAGES = {"overview_spot", "portfolio", "trade_outcomes", "strategy_edge", "orderbook"}
_FUTURES_DASHBOARD_PAGES = {
    "overview_futures",
    "portfolio_futures",
    "trade_outcomes_futures",
    "strategy_edge_futures",
    "orderbook_futures",
}
_FUTURES_HEDGE_PAGES = {"futures_hedge"}


def _clean_href(value: str) -> str:
    return value.replace("/index.html", "/")


def _join_href(prefix: str, suffix: str = "") -> str:
    base = _clean_href(prefix.rstrip("/"))
    if not suffix:
        return f"{base}/"
    return f"{base}/{suffix.strip('/')}/"


def render_site_navigation(*, active_page: str, base_prefix: str = "..") -> str:
    normalized_prefix = base_prefix.rstrip("/")
    public_root = normalized_prefix
    spot_root = f"{public_root}/../spot/dashboard"
    futures_root = f"{public_root}/../futures/dashboard"
    hedge_root = f"{public_root}/../futures_hedge/dashboard"
    subnav_root = normalized_prefix

    if active_page in _DASHBOARD_PAGES:
        public_root = "../../../public_site"
        spot_root = ".."
        futures_root = "../../../futures/dashboard"
        hedge_root = "../../../futures_hedge/dashboard"
        subnav_root = ".."
    elif active_page in _FUTURES_DASHBOARD_PAGES:
        public_root = "../../../public_site"
        spot_root = "../../../spot/dashboard"
        futures_root = ".."
        hedge_root = "../../../futures_hedge/dashboard"
        subnav_root = ".."
    elif active_page in _FUTURES_HEDGE_PAGES:
        public_root = "../../../public_site"
        spot_root = "../../../spot/dashboard"
        futures_root = "../../../futures/dashboard"
        hedge_root = ".."

    escaped_public_root = html.escape(public_root, quote=True)
    active_global = (
        "Spot"
        if active_page in _DASHBOARD_PAGES
        else "Futures"
        if active_page in _FUTURES_DASHBOARD_PAGES
        else "Hedge"
        if active_page in _FUTURES_HEDGE_PAGES
        else "News"
        if active_page == "news"
        else "Resources"
        if active_page == "resources"
        else "Home"
    )
    strategy_links = (
        ("Spot", _join_href(spot_root, "overview_spot")),
        ("Futures", _join_href(futures_root, "overview_futures")),
        ("Hedge", _join_href(hedge_root, "overview_hedge")),
    )
    strategies_active = active_global in {"Spot", "Futures", "Hedge"}
    strategy_links_html = "".join(
        (
            f'<a class="global-nav-menu-link{" active" if label == active_global else ""}" '
            f'href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
        )
        for label, href in strategy_links
    )
    home_class = ' class="active"' if active_global == "Home" else ""
    news_class = ' class="active"' if active_global == "News" else ""
    resources_class = ' class="active"' if active_global == "Resources" else ""
    strategies_class = " active" if strategies_active else ""
    home_href = html.escape(_join_href(public_root), quote=True)
    news_href = html.escape(_join_href(public_root, "news"), quote=True)
    resources_href = html.escape(_join_href(public_root, "resources"), quote=True)
    global_links_html = (
        f'<a{home_class} href="{home_href}">Home</a>'
        f'<details class="global-nav-menu{strategies_class}">'
        '<summary aria-haspopup="true" aria-expanded="false">Strategies</summary>'
        f'<div class="global-nav-menu-panel">{strategy_links_html}</div>'
        "</details>"
        f'<a{news_class} href="{news_href}">News</a>'
        f'<a{resources_class} href="{resources_href}">Resources</a>'
    )
    global_navigation_html = f"""
      <div class="global-nav-shell">
        <nav class="global-nav" aria-label="Primary navigation">
          <a class="global-brand" href="{escaped_public_root}/">SmartSignalHub</a>
          <div class="global-nav-links">{global_links_html}</div>
        </nav>
      </div>
      <script>
        (() => {{
          const menus = document.querySelectorAll(".global-nav-menu");
          const hoverCapable = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
          menus.forEach((menu) => {{
            const summary = menu.querySelector("summary");
            if (!summary) return;
            let closeTimer = 0;
            const setOpen = (open) => {{
              menu.open = open;
              summary.setAttribute("aria-expanded", open ? "true" : "false");
            }};
            const openMenu = () => {{
              window.clearTimeout(closeTimer);
              setOpen(true);
            }};
            const closeMenu = () => {{
              window.clearTimeout(closeTimer);
              closeTimer = window.setTimeout(() => {{
                setOpen(false);
              }}, 180);
            }};
            if (hoverCapable) {{
              summary.addEventListener("click", (event) => event.preventDefault());
              menu.addEventListener("mouseenter", openMenu);
              menu.addEventListener("mouseleave", closeMenu);
            }} else {{
              summary.addEventListener("click", (event) => {{
                event.preventDefault();
                const shouldOpen = !menu.open;
                menus.forEach((otherMenu) => {{
                  if (otherMenu === menu) return;
                  otherMenu.open = false;
                  otherMenu.querySelector("summary")?.setAttribute("aria-expanded", "false");
                }});
                setOpen(shouldOpen);
              }});
            }}
            menu.addEventListener("focusin", openMenu);
            menu.addEventListener("focusout", () => {{
              window.setTimeout(() => {{
                if (!menu.contains(document.activeElement)) menu.open = false;
              }}, 0);
            }});
          }});
          document.addEventListener("click", (event) => {{
            menus.forEach((menu) => {{
              if (menu.contains(event.target)) return;
              menu.open = false;
              menu.querySelector("summary")?.setAttribute("aria-expanded", "false");
            }});
          }});
          document.addEventListener("keydown", (event) => {{
            if (event.key !== "Escape") return;
            menus.forEach((menu) => {{
              menu.open = false;
              menu.querySelector("summary")?.setAttribute("aria-expanded", "false");
            }});
          }});
        }})();
      </script>
"""
    if active_page not in _DASHBOARD_PAGES and active_page not in _FUTURES_DASHBOARD_PAGES:
        return global_navigation_html

    nav_items = _FUTURES_NAV_ITEMS if active_page in _FUTURES_DASHBOARD_PAGES else _PRIMARY_NAV_ITEMS
    primary_links = []
    for slug, label in nav_items:
        active_class = " active" if slug == active_page else ""
        href = _join_href(subnav_root, slug)
        primary_links.append(
            f'<a class="subnav-link subnav-link-primary{active_class}" href="{href}">{html.escape(label)}</a>'
        )
    return f"""
      {global_navigation_html}
      <div class="subnav-shell">
        <nav class="subnav-mobile-menu" data-subnav-menu>
          {''.join(primary_links)}
        </nav>
        <nav class="subnav">
          <div class="subnav-row subnav-row-primary">{''.join(primary_links)}</div>
        </nav>
      </div>
      <script>
        (() => {{
          const shell = document.querySelector(".subnav-shell");
          const menu = shell?.querySelector("[data-subnav-menu]");
          if (!shell || !menu) return;
          let toggle = document.querySelector("[data-subnav-toggle]");
          if (!toggle) {{
            const heroMain = document.querySelector(".hero-main");
            if (heroMain) {{
              toggle = document.createElement("button");
              toggle.className = "subnav-toggle";
              toggle.type = "button";
              toggle.setAttribute("data-subnav-toggle", "");
              toggle.setAttribute("aria-expanded", "false");
              toggle.setAttribute("aria-label", "Open navigation menu");
              toggle.textContent = "☰";
              heroMain.appendChild(toggle);
            }}
          }}
          if (!toggle) return;
          menu.setAttribute("aria-hidden", "true");
          const setMenuPosition = () => {{
            const rect = toggle.getBoundingClientRect();
            const top = Math.round(rect.bottom);
            menu.style.top = `${{top}}px`;
            menu.style.maxHeight = `calc(100vh - ${{top}}px)`;
            menu.style.right = "16px";
            menu.style.left = "auto";
          }};
          const closeMenu = () => {{
            shell.classList.remove("subnav-open");
            toggle.setAttribute("aria-expanded", "false");
            menu.setAttribute("aria-hidden", "true");
          }};
          toggle.addEventListener("click", (event) => {{
            event.stopPropagation();
            const isOpen = shell.classList.toggle("subnav-open");
            toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
            menu.setAttribute("aria-hidden", isOpen ? "false" : "true");
            if (isOpen) setMenuPosition();
          }});
          document.addEventListener("click", (event) => {{
            if (!shell.classList.contains("subnav-open")) return;
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (toggle.contains(target) || menu.contains(target)) return;
            closeMenu();
          }});
          menu.addEventListener("click", (event) => {{
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (target.closest("a, button")) closeMenu();
          }});
          document.addEventListener("keydown", (event) => {{
            if (event.key === "Escape") closeMenu();
          }});
        }})();
      </script>
"""
