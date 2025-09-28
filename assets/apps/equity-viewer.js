// assets/apps/equity-viewer.js
// Equity & Trades Viewer — slim entry using mixins + template
// All feature logic lives in mixins under assets/apps/equity-viewer/

// cache-bust to ensure latest mixins after repo updates
import { applyDataMixin }      from './equity-viewer/data-mixin.js';
import { applyKpiMixin }       from './equity-viewer/kpi-mixin.js';
import { applyIndicatorsMixin }from './equity-viewer/indicators-mixin.js';
import { applyChartMixin }     from './equity-viewer/chart-mixin.js';
import { applyTradesMixin }    from './equity-viewer/trades-mixin.js';
import { applyLiveMixin }      from './equity-viewer/live-mixin.js';
import { equityViewerTemplate }from './equity-viewer/template.js';

class EquityViewer extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    // ===== Shared state (mixins can read/write) =====
    this.state = {
      capital: [],            // [{ts,time,capital}]
      pnlBars: [],            // [{ts,delta}]
      strategy: { signals: [] },

      // view state
      mode: 'pnl',            // 'equity' | 'pnl'
      amplify: true,
      deltaPct: true,
      statusFilter: 'ALL',
      page: 1,
      pageSize: 5,
      targetDate: null,

      // datasets separated for non-chart UI stability
      kpiCapital: [],
      kpiStrategy: { signals: [] },
      chartCapital: [],
      chartStrategy: { signals: [] },

      // optional: multi-timeframe latest signals
      // mtfSignals: { '5m':'BUY'|'SELL'|'NO_SIGNAL', '30m':..., '4h':... }
    };

    this.boundResize = () => this.chart && this.chart.resize();
    this.boundTheme  = () => { try { this.applyChartTheme(); this.applyChart(); this.chart && this.chart.resize(); } catch {} };

    this.n2 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
    this.n0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
    this.shortInt = (n)=> (n>999 ? (Math.round(n/100)/10)+'k' : String(n));
  }

  connectedCallback() {
    this.render();
    this.initChart();
    this.autoLoad();

    window.addEventListener('resize', this.boundResize);
    window.addEventListener('themechange', this.boundTheme);

    // start lightweight polling if mixin provided it
    try { typeof this.startPolling === 'function' && this.startPolling(); } catch {}

    // ensure initial MTF visual states after first render tick
    queueMicrotask(() => this.applyMtfStates());

     // LIVE TITLE ანიმაცია
  const liveTitle = this.shadowRoot.getElementById('live-title');
  if (liveTitle) {
    setInterval(() => {
      liveTitle.classList.remove('live-animate');
      void liveTitle.offsetWidth;
      liveTitle.classList.add('live-animate');
    }, 6500);
  }
  }

  disconnectedCallback() {
    window.removeEventListener('resize', this.boundResize);
    window.removeEventListener('themechange', this.boundTheme);
    try { this.chart && this.chart.dispose(); } catch {}
    this.chart = null;
    if (this.donuts) {
      for (const k of Object.keys(this.donuts)) { try { this.donuts[k].dispose(); } catch {} }
      this.donuts = null;
    }
    try { typeof this.stopPolling === 'function' && this.stopPolling(); } catch {}
  }

  $(sel)    { return this.shadowRoot.querySelector(sel); }
  $all(sel) { return Array.from(this.shadowRoot.querySelectorAll(sel)); }

  render() {
  // Template
  this.shadowRoot.innerHTML = equityViewerTemplate();

  // Wire controls
  this.$('#btnEquity')?.addEventListener('click', () => this.setMode('equity'));
  this.$('#btnPnL')?.addEventListener('click', () => this.setMode('pnl'));
  this.$('#btnAmplify')?.addEventListener('click', () => this.toggleAmplify());
  this.$('#btnDelta')?.addEventListener('click', () => this.toggleDelta());
  this.$('#btnViewTrade')?.addEventListener('click', () => { this.setChartView('trade'); });
  this.$('#btnViewTime')?.addEventListener('click', () => { this.setChartView('time'); });
  this.$('#fltStatus')?.addEventListener('change', (e) => { this.state.statusFilter = e.target.value; this.state.page = 1; this.renderTrades(); });
  this.$('#selPageSize')?.addEventListener('change', (e) => { this.state.pageSize = parseInt(e.target.value, 10) || 5; this.state.page = 1; this.renderTrades(); });
  this.$('#btnPrev')?.addEventListener('click', () => { if (this.state.page > 1) { this.state.page--; this.renderTrades(); } });
  this.$('#btnNext')?.addEventListener('click', () => { const tp = this.totalPages(); if (this.state.page < tp) { this.state.page++; this.renderTrades(); } });
  this.$('#btnPrevDay')?.addEventListener('click', () => { this.shiftDay(-1); });
  this.$('#btnNextDay')?.addEventListener('click', () => { this.shiftDay(+1); });

  // === აქ ჩასვი ეს ორი ხაზი ===
  this.$('#fltSide')?.addEventListener('change', () => { this.state.page = 1; this.renderTrades(); });
  this.$('#fltResult')?.addEventListener('change', () => { this.state.page = 1; this.renderTrades(); });
}

  // ===== Aggregate re-render that delegates to mixins =====
  renderAll() {
    this.renderKPIs();
    this.renderFinance();
    this.renderIndicators();
    this.applyChart();
    this.renderTrades();

    // 🔁 after any full render, (re)apply MTF visual classes
    this.applyMtfStates();
  }

  // ===== Normalize a signal string to a CSS class =====
  classForSignal(sig) {
    if (!sig) return 'is-none';
    const s = String(sig)
      .toUpperCase()
      .replace(/[^A-Z_ -]/g, '')  // drop emojis/symbols
      .replace(/\s+/g, ' ')
      .trim();

    if (/(^| )BUY( |$)/.test(s))  return 'is-buy';
    if (/(^| )SELL( |$)/.test(s)) return 'is-sell';
    if (/NO[_ -]?SIGNAL/.test(s)) return 'is-none';
    return 'is-none';
  }

  // ===== Apply classes to 5m / 30m / 4h cards (robust mapping) =====
  applyMtfStates() {
    try {
      const cards = this.$all('.mtf-grid .mtf-card');
      if (!cards.length) return;

      // Prefer state-provided signals if available
      const mtf = this.state.mtfSignals || this.state.mtf || this.state.signals || {};

      // Extract TF from each card's header text (more reliable than index)
      const tfFromCard = (card) => {
        const t = (card.querySelector('.mtf-hdr')?.textContent || '').toLowerCase();
        if (t.includes('5m'))  return '5m';
        if (t.includes('30m')) return '30m';
        if (t.includes('4h'))  return '4h';
        return null;
      };

      // Get a signal for a given TF with fallbacks
      const getSignal = (tf, card) => {
        let s = mtf?.[tf]?.signal ?? mtf?.[tf];
        if (s) return s;

        s = card.getAttribute('data-signal') || card.dataset?.signal;
        if (s) return s;

        const el = card.querySelector('[data-field="signal"], .mtf-signal, .signal');
        if (el?.textContent) return el.textContent;

        return 'NO_SIGNAL';
      };

      cards.forEach((card) => {
        const tf  = tfFromCard(card);
        if (!tf) return;
        const sig = getSignal(tf, card);
        card.classList.remove('is-buy','is-sell','is-none');
        card.classList.add(this.classForSignal(sig));
      });
    } catch {}
  }
}

// Apply mixins
applyDataMixin(EquityViewer);
applyKpiMixin(EquityViewer);
applyIndicatorsMixin(EquityViewer);
applyChartMixin(EquityViewer);
applyTradesMixin(EquityViewer);
applyLiveMixin(EquityViewer);

customElements.define('equity-viewer', EquityViewer);
