"""Render Futures Portfolio page from normalized payload data."""

from __future__ import annotations

import html
import json
from typing import Any

from platform_v2.futures.dashboard.explanation_system import (
    load_explanation_map,
    render_explanation_anchor,
    render_explanation_host,
    render_explanation_payload,
)
from platform_v2.futures.dashboard.components import render_futures_runtime_hero
from platform_v2.shared.frontend.components import (
    metric_value_class,
    render_page_head,
    render_runtime_clock_script,
    render_site_footer,
    render_site_navigation,
)


class PortfolioFuturesPageRenderer:
    """Render Futures Portfolio page from prepared payload."""

    def render(self, payload: dict[str, Any]) -> str:
        metrics = payload["metrics"] or {}
        capital_snapshot_items = payload.get("capital_snapshot_items") or []
        open_positions_section = payload["open_positions_section"]
        closed_positions_section = payload["closed_positions_section"]
        closed_chart_json = json.dumps(payload.get("closed_trade_chart_rows") or [], ensure_ascii=True).replace("</", "<\\/")

        explanation_payload = render_explanation_payload(self._explanations_for_prefix("portfolio."))
        return f"""<!DOCTYPE html>
<!-- ssh-generator: portfolio_futures.py.renderer.v2026-04-18a -->
<html lang="en">
  <head>
{render_page_head(
    title="Bitcoin Futures Portfolio And Positions | SmartSignalHub",
    description="Live Bitcoin futures capital state, open positions, confirmed exits, and realized portfolio outcomes inside SmartSignalHub.",
    canonical_path="/futures/dashboard/portfolio_futures/index.html",
    css_href="./css/styles.css",
    extra_css_hrefs=(
        "../../../shared/frontend/charts/charts.css",
        "../../../shared/frontend/explanation_system/css/drawer.css",
    ),
    favicon_prefix="../../../public_site/",
    og_description="Track futures capital state, open Bitcoin futures exposure, confirmed exits, and realized outcomes for SmartSignalHub.",
    twitter_description="Track futures capital state, open Bitcoin futures exposure, confirmed exits, and realized outcomes for SmartSignalHub.",
)}
    <style>
      .futures-nav {{
        max-width: 1040px;
        margin: 0 auto;
        padding: 4px 18px 8px;
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }}
      .futures-nav a {{
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 6px 12px;
        text-decoration: none;
        color: var(--text);
        background: color-mix(in oklab, var(--bg-soft) 86%, #050a13 14%);
        font-size: 13px;
      }}
      .futures-nav a.active {{
        border-color: var(--amber);
        color: var(--amber);
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <header class="page-chrome">
        {self._render_hero(metrics)}
        {self._render_navigation()}
      </header>
      {self._render_portfolio_content(capital_snapshot_items=capital_snapshot_items, open_positions_section=open_positions_section, closed_positions_section=closed_positions_section)}
    </main>
    {render_site_footer()}
    {explanation_payload}
    {render_explanation_host(base_prefix="../")}
    <script>window.__SSH_PORTFOLIO_CLOSED__ = {closed_chart_json};</script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script type="module" src="../../../shared/frontend/charts/portfolio_pnl_charts.js"></script>
    {render_runtime_clock_script()}
    {self._render_table_pagination_script()}
  </body>
</html>
"""

    @staticmethod
    def _escape(value: Any) -> str:
        return html.escape(str(value))

    @staticmethod
    def _value_class(value: Any, *, kind: str = "generic") -> str:
        return metric_value_class(value, kind=kind)

    def _strong(self, value: Any, *, kind: str = "generic") -> str:
        klass = self._value_class(value, kind=kind)
        safe = self._escape(value if value not in (None, "") else "—")
        if klass:
            return f'<strong class="{klass}">{safe}</strong>'
        return f"<strong>{safe}</strong>"

    def _render_kpi_grid(self, items: tuple[tuple[str, str], ...]) -> str:
        return "".join(
            f'<div class="metric-card"><span>{self._escape(label)}</span>{value_html}</div>'
            for label, value_html in items
        )

    @staticmethod
    def _explanations_for_prefix(prefix: str) -> dict[str, Any]:
        return {key: item for key, item in load_explanation_map().items() if key.startswith(prefix)}

    @staticmethod
    def _render_panel_heading(title: str, explanation_key: str) -> str:
        return (
            f'<h2 class="panel-title-with-action"><span>{html.escape(title)}</span>'
            f'{render_explanation_anchor(key=explanation_key, label_html="")}</h2>'
        )

    def _render_metric_items(self, items: list[dict[str, Any]]) -> str:
        prepared: tuple[tuple[str, str], ...] = tuple(
            (
                self._escape(item.get("label", "—")),
                self._strong(item.get("value", "—"), kind=str(item.get("kind") or "generic")),
            )
            for item in items
        )
        return self._render_kpi_grid(prepared)

    def _render_capital_panel(self, items: list[dict[str, Any]]) -> str:
        return f"""
        <section class="panel panel-wide portfolio-panel portfolio-panel-capital">
          <div class="panel-head">
            {self._render_panel_heading("Capital Snapshot", "portfolio.capital_snapshot.panel")}
          </div>
          <p class="panel-intro">Live futures capital, realized results, reserved funds, and current exposure.</p>
          <div class="kpi-grid portfolio-kpi-grid portfolio-kpi-grid-capital">
            {self._render_metric_items(items)}
          </div>
        </section>
"""

    def _render_table(self, headers: list[Any], rows: list[Any], empty_text: str, *, table_id: str) -> str:
        if not rows:
            return f'<div class="stack-list empty">{self._escape(empty_text)}</div>'
        head = "".join(
            self._render_table_header_cell(header, index=index, table_id=table_id)
            for index, header in enumerate(headers)
        )
        body = "".join(self._render_table_row(row, column_count=len(headers)) for row in rows)
        page_size_control = self._render_page_size_control(table_id=table_id)
        return f"""
        <div class="table-controls" data-table-controls="{self._escape(table_id)}">
          <div class="table-controls-group">
            <button class="table-control-button" type="button" data-table-back="{self._escape(table_id)}">Back</button>
            <button class="table-control-button" type="button" data-table-next="{self._escape(table_id)}">Next</button>
            {page_size_control}
          </div>
        </div>
        <table class="runtime-table">
          <thead><tr>{head}</tr></thead>
          <tbody data-table-body="{self._escape(table_id)}">{body}</tbody>
        </table>
        """

    def _render_page_size_control(self, *, table_id: str) -> str:
        return (
            f'<select class="table-page-size-select" data-page-size="{self._escape(table_id)}">'
            '<option value="5">5</option>'
            '<option value="10">10</option>'
            '<option value="25">25</option>'
            '<option value="50">50</option>'
            '</select>'
        )

    def _header_label(self, header: Any) -> str:
        if isinstance(header, dict):
            return str(header.get("label") or "")
        return str(header)

    def _render_table_row(self, row: Any, *, column_count: int) -> str:
        if not isinstance(row, dict):
            return f"<tr data-table-item>{''.join(f'<td>{cell}</td>' for cell in row)}</tr>"

        cells = list(row.get("cells") or [])
        details = list(row.get("details") or [])
        main_row = (
            '<tr class="expandable-table-row" data-table-item data-expandable-row tabindex="0" '
            'role="button" aria-expanded="false">'
            f"{''.join(f'<td>{cell}</td>' for cell in cells)}"
            "</tr>"
        )
        if not details:
            return main_row

        detail_items = "".join(
            '<div class="position-detail-item">'
            f'<span>{self._escape(item.get("label", "—"))}</span>'
            f'{self._strong(item.get("value", "—"), kind=str(item.get("kind") or "generic"))}'
            "</div>"
            for item in details
        )
        detail_row = (
            '<tr class="position-detail-row" data-detail-row hidden>'
            f'<td colspan="{max(1, column_count)}">'
            '<div class="position-detail-grid">'
            f"{detail_items}"
            "</div>"
            "</td>"
            "</tr>"
        )
        return main_row + detail_row

    def _render_table_header_cell(self, header: Any, *, index: int, table_id: str) -> str:
        if isinstance(header, dict):
            label = self._escape(header.get("label", "—"))
            explanation_key = str(header.get("explanation_key") or "").strip()
            if explanation_key:
                return (
                    '<th><span class="metric-label-with-action">'
                    f"<span>{label}</span>"
                    f'{render_explanation_anchor(key=explanation_key, label_html="")}'
                    "</span></th>"
                )
            return self._render_filterable_header(label=label, index=index, table_id=table_id)
        return self._render_filterable_header(label=self._escape(header), index=index, table_id=table_id)

    def _render_filterable_header(self, *, label: str, index: int, table_id: str) -> str:
        if table_id != "closed-positions" or label not in {"Symbol", "Side", "Result"}:
            return f"<th>{label}</th>"
        return (
            '<th class="filterable-header">'
            f'<button class="table-header-filter-button" type="button" data-filter-toggle="{self._escape(table_id)}" '
            f'data-filter-index="{index}" aria-expanded="false">{label}<span class="filter-arrow"></span></button>'
            f'<div class="table-filter-menu" data-table-filter="{self._escape(table_id)}" '
            f'data-filter-index="{index}" data-filter-value="" aria-label="Filter {label}" hidden>'
            f'<button type="button" data-filter-option="" class="active">All {label}</button>'
            '</div>'
            '</th>'
        )

    def _render_hero(self, metrics: dict[str, Any]) -> str:
        return render_futures_runtime_hero(
            title="Bitcoin Futures Portfolio Capital And Positions",
            href="../portfolio_futures/",
            intro="",
            subline=None,
        )

    @staticmethod
    def _render_navigation() -> str:
        return render_site_navigation(active_page="portfolio_futures")
        return """
      <div class="global-nav-shell">

        <nav class="global-nav" aria-label="Primary navigation">

          <a class="global-brand" href="../../../public_site/">SmartSignalHub</a>

          <div class="global-nav-links"><a href="../../../public_site/">Home</a><a href="../../../spot/dashboard/overview_spot/">Spot</a><a class="active" href="../overview_futures/">Futures</a><a href="../../../futures_hedge/dashboard/overview_hedge/">Hedge</a><a href="../../../public_site/news/">News</a><a href="../../../public_site/resources/">Resources</a></div>

        </nav>

      </div>

      <div class="subnav-shell">
        <nav class="subnav-mobile-menu" data-subnav-menu>
          <a class="subnav-link subnav-link-primary" href="../overview_futures/">Overview</a><a class="subnav-link subnav-link-primary active" href="../portfolio_futures/">Portfolio</a><a class="subnav-link subnav-link-primary" href="../trade_outcomes_futures/">Trade</a><a class="subnav-link subnav-link-primary" href="../strategy_edge_futures/">Strategy</a><a class="subnav-link subnav-link-primary" href="../orderbook_futures/">Orderbook</a>
        </nav>
        <nav class="subnav">
          <div class="subnav-row subnav-row-primary"><a class="subnav-link subnav-link-primary" href="../overview_futures/">Overview</a><a class="subnav-link subnav-link-primary active" href="../portfolio_futures/">Portfolio</a><a class="subnav-link subnav-link-primary" href="../trade_outcomes_futures/">Trade</a><a class="subnav-link subnav-link-primary" href="../strategy_edge_futures/">Strategy</a><a class="subnav-link subnav-link-primary" href="../orderbook_futures/">Orderbook</a></div>
        </nav>
      </div>
      <script>
        (() => {
          const shell = document.querySelector(".subnav-shell");
          const menu = shell?.querySelector("[data-subnav-menu]");
          if (!shell || !menu) return;
          let toggle = document.querySelector("[data-subnav-toggle]");
          if (!toggle) {
            const note = document.querySelector(".hero-note");
            if (note) {
              let row = note.closest(".hero-note-row");
              if (!row) {
                row = document.createElement("div");
                row.className = "hero-note-row";
                note.parentNode?.insertBefore(row, note);
                row.appendChild(note);
              }
              toggle = document.createElement("button");
              toggle.className = "subnav-toggle";
              toggle.type = "button";
              toggle.setAttribute("data-subnav-toggle", "");
              toggle.setAttribute("aria-expanded", "false");
              toggle.setAttribute("aria-label", "Open navigation menu");
              toggle.textContent = "☰";
              row.appendChild(toggle);
            }
          }
          if (!toggle) return;
          menu.setAttribute("aria-hidden", "true");
          const setMenuPosition = () => {
            const rect = toggle.getBoundingClientRect();
            const top = Math.round(rect.bottom);
            menu.style.top = `${top}px`;
            menu.style.maxHeight = `calc(100vh - ${top}px)`;
            menu.style.right = "16px";
            menu.style.left = "auto";
          };
          const closeMenu = () => {
            shell.classList.remove("subnav-open");
            toggle.setAttribute("aria-expanded", "false");
            menu.setAttribute("aria-hidden", "true");
          };
          toggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const isOpen = shell.classList.toggle("subnav-open");
            toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
            menu.setAttribute("aria-hidden", isOpen ? "false" : "true");
            if (isOpen) setMenuPosition();
          });
          document.addEventListener("click", (event) => {
            if (!shell.classList.contains("subnav-open")) return;
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (toggle.contains(target) || menu.contains(target)) return;
            closeMenu();
          });
          menu.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (target.closest("a, button")) closeMenu();
          });
          const marketButtons = Array.from(document.querySelectorAll("[data-market-href]"));
          marketButtons.forEach((button) => {
            button.addEventListener("click", (event) => {
              event.preventDefault();
              const href = button.getAttribute("data-market-href");
              if (!href) return;
              window.location.href = href;
            });
          });
          document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeMenu();
          });
        })();
      </script>
"""

    @staticmethod
    def _render_table_pagination_script() -> str:
        return """
    <script>
      (() => {
        document.querySelectorAll('[data-table-body]').forEach((tbody) => {
          const tableId = tbody.getAttribute('data-table-body');
          const rows = Array.from(tbody.querySelectorAll('tr[data-table-item]'));
          const backButton = document.querySelector(`[data-table-back="${tableId}"]`);
          const nextButton = document.querySelector(`[data-table-next="${tableId}"]`);
          const pageSizeSelect = document.querySelector(`[data-page-size="${tableId}"]`);
          const filters = Array.from(document.querySelectorAll(`[data-table-filter="${tableId}"]`));
          const toggles = Array.from(document.querySelectorAll(`[data-filter-toggle="${tableId}"]`));
          let page = 0;

          const pageSize = () => {
            const parsed = Number.parseInt(pageSizeSelect?.value || '5', 10);
            return Number.isFinite(parsed) && parsed > 0 ? parsed : 5;
          };

          const populateFilters = () => {
            filters.forEach((menu) => {
              const index = Number.parseInt(menu.getAttribute('data-filter-index') || '-1', 10);
              const values = Array.from(new Set(rows.map((row) => {
                const cells = Array.from(row.querySelectorAll('td'));
                return String(cells[index]?.textContent || '').trim();
              }).filter(Boolean))).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
              values.forEach((value) => {
                const option = document.createElement('button');
                option.type = 'button';
                option.setAttribute('data-filter-option', value);
                option.textContent = value;
                menu.appendChild(option);
              });
            });
          };

          const rowMatchesFilters = (row) => {
            if (!filters.length) return true;
            const cells = Array.from(row.querySelectorAll('td'));
            return filters.every((menu) => {
              const selected = String(menu.getAttribute('data-filter-value') || '').trim();
              if (!selected) return true;
              const index = Number.parseInt(menu.getAttribute('data-filter-index') || '-1', 10);
              const value = String(cells[index]?.textContent || '').trim();
              return value === selected;
            });
          };

          const hideRowPair = (row) => {
            row.style.display = 'none';
            const detailRow = row.nextElementSibling;
            if (detailRow?.matches('[data-detail-row]')) {
              detailRow.hidden = true;
              detailRow.style.display = 'none';
              row.setAttribute('aria-expanded', 'false');
            }
          };

          const renderPage = () => {
            const filteredRows = rows.filter(rowMatchesFilters);
            const total = filteredRows.length;
            const size = pageSize();
            const maxPage = Math.max(0, Math.ceil(total / size) - 1);
            if (page > maxPage) page = maxPage;
            const start = page * size;
            const end = Math.min(start + size, total);
            rows.forEach(hideRowPair);
            filteredRows.forEach((row, index) => {
              const visible = index >= start && index < end;
              row.style.display = visible ? '' : 'none';
              const detailRow = row.nextElementSibling;
              if (detailRow?.matches('[data-detail-row]')) {
                if (!visible) {
                  detailRow.hidden = true;
                  row.setAttribute('aria-expanded', 'false');
                }
                detailRow.style.display = visible && !detailRow.hidden ? '' : 'none';
              }
            });
            if (backButton) backButton.disabled = page === 0;
            if (nextButton) nextButton.disabled = end >= total;
          };

          backButton?.addEventListener('click', () => {
            if (page > 0) {
              page -= 1;
              renderPage();
            }
          });

          nextButton?.addEventListener('click', () => {
            const total = rows.filter(rowMatchesFilters).length;
            const maxPage = Math.max(0, Math.ceil(total / pageSize()) - 1);
            if (page < maxPage) {
              page += 1;
              renderPage();
            }
          });

          pageSizeSelect?.addEventListener('change', () => {
            page = 0;
            renderPage();
          });

          filters.forEach((menu) => {
            menu.addEventListener('click', (event) => {
              const option = event.target instanceof Element ? event.target.closest('[data-filter-option]') : null;
              if (!(option instanceof HTMLElement)) return;
              const selected = option.getAttribute('data-filter-option') || '';
              menu.setAttribute('data-filter-value', selected);
              menu.querySelectorAll('[data-filter-option]').forEach((item) => item.classList.toggle('active', item === option));
              page = 0;
              renderPage();
              menu.hidden = true;
              const toggle = toggles.find((button) => button.getAttribute('data-filter-index') === menu.getAttribute('data-filter-index'));
              toggle?.setAttribute('aria-expanded', 'false');
            });
          });

          toggles.forEach((button) => {
            button.addEventListener('click', (event) => {
              event.stopPropagation();
              const index = button.getAttribute('data-filter-index');
              const menu = filters.find((item) => item.getAttribute('data-filter-index') === index);
              if (!menu) return;
              const willOpen = menu.hidden;
              filters.forEach((item) => {
                item.hidden = true;
              });
              toggles.forEach((item) => item.setAttribute('aria-expanded', 'false'));
              menu.hidden = !willOpen;
              button.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
            });
          });

          document.addEventListener('click', (event) => {
            const target = event.target;
            if (!(target instanceof Element)) return;
            if (target.closest('.filterable-header')) return;
            filters.forEach((item) => {
              item.hidden = true;
            });
            toggles.forEach((item) => item.setAttribute('aria-expanded', 'false'));
          });

          populateFilters();
          renderPage();
        });

        document.querySelectorAll('[data-expandable-row]').forEach((row) => {
          const detailRow = row.nextElementSibling;
          if (!detailRow?.matches('[data-detail-row]')) return;
          const toggle = () => {
            const isOpen = row.getAttribute('aria-expanded') === 'true';
            row.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
            detailRow.hidden = isOpen;
            detailRow.style.display = isOpen ? 'none' : '';
          };
          row.addEventListener('click', toggle);
          row.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            toggle();
          });
        });
      })();
    </script>
"""

    def _render_main_tables(self, *, open_positions_section: dict[str, Any], closed_positions_section: dict[str, Any]) -> str:
        return f"""
      <section class="panel panel-wide runtime-panel">
          <div class="panel-head">
            {self._render_panel_heading(
                str(open_positions_section.get("title", "Open Positions")),
                "portfolio.open_positions.panel",
            )}
            <span class="badge neutral">{self._escape(open_positions_section.get("badge", "0"))}</span>
          </div>
          <p class="panel-intro">{self._escape(open_positions_section.get("intro", ""))}</p>
          <div class="table-shell">
            {self._render_table(
                list(open_positions_section.get("headers") or []),
                list(open_positions_section.get("rows") or []),
                str(open_positions_section.get("empty_text") or "No open positions recorded yet."),
                table_id=str(open_positions_section.get("table_id") or "open-positions"),
            )}
          </div>
        </section>

      <section class="panel panel-wide runtime-panel">
          <div class="panel-head">
            {self._render_panel_heading(
                str(closed_positions_section.get("title", "Closed Positions")),
                "portfolio.closed_positions.panel",
            )}
            <span class="badge neutral">{self._escape(closed_positions_section.get("badge", "0"))}</span>
          </div>
          <p class="panel-intro panel-intro-closed">{self._escape(closed_positions_section.get("intro", ""))}</p>
          <div class="table-shell">
            {self._render_table(
                list(closed_positions_section.get("headers") or []),
                list(closed_positions_section.get("rows") or []),
                str(closed_positions_section.get("empty_text") or "No closed positions recorded yet."),
                table_id=str(closed_positions_section.get("table_id") or "closed-positions"),
            )}
          </div>
        </section>
"""

    def _render_charts_section(self) -> str:
        return f"""
        <section class="panel panel-wide chart-panel">
          <div class="panel-head">
            {self._render_panel_heading("Closed Trade PnL", "portfolio.closed_trade_pnl.panel")}
          </div>
          <p class="panel-intro">Per-trade net PnL across confirmed closed futures positions.</p>
          <div class="chart-shell">
            <div id="portfolio-pnl-chart" class="chart-canvas" aria-label="Closed trade net pnl chart"></div>
          </div>
        </section>
"""

    def _render_portfolio_content(
        self,
        *,
        capital_snapshot_items: list[dict[str, Any]],
        open_positions_section: dict[str, Any],
        closed_positions_section: dict[str, Any],
    ) -> str:
        return f"""
      <section class="runtime-panel-stack">
        {self._render_capital_panel(capital_snapshot_items)}
        {self._render_main_tables(open_positions_section=open_positions_section, closed_positions_section=closed_positions_section)}
        {self._render_charts_section()}
      </section>
"""
