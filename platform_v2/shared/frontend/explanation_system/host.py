"""Shared host markup helpers for the explanation drawer."""

from __future__ import annotations


def render_explanation_host(*, asset_prefix: str) -> str:
    """Render the shared explanation drawer shell and loader script."""

    return f"""
    <aside class="explanation-drawer" data-expl-drawer aria-hidden="true">
      <div class="explanation-drawer-backdrop" data-expl-close></div>
      <div class="explanation-drawer-panel" role="dialog" aria-modal="true" aria-labelledby="explanation-drawer-title">
        <button class="explanation-drawer-close" type="button" data-expl-close aria-label="Close details">Close</button>
        <div class="explanation-drawer-body">
          <p class="explanation-drawer-kicker">Metric Detail</p>
          <h2 id="explanation-drawer-title" data-expl-title>—</h2>
          <p class="explanation-drawer-summary" data-expl-summary>—</p>
          <ul class="explanation-drawer-list" data-expl-details></ul>
          <div class="explanation-drawer-cta">
            <a class="explanation-drawer-link" data-expl-link href="#" hidden>Open detail page</a>
            <a class="explanation-drawer-link" data-expl-link-secondary href="#" hidden>Open related page</a>
          </div>
        </div>
      </div>
    </aside>
    <script type="module" src="{asset_prefix}js/drawer.js"></script>
"""
