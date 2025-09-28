// assets/apps/equity-viewer/data-mixin.js
// Adds parsing, loading, and derived computations to EquityViewer

export function applyDataMixin(Cls){
  Object.assign(Cls.prototype, {
    parseTs(t) {
      if (typeof t === 'number') return t;
      if (typeof t !== 'string') return NaN;
      let d = Date.parse(t); if (!isNaN(d)) return d;
      d = Date.parse(t.replace(' ', 'T')); if (!isNaN(d)) return d;
      if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(t)) return Date.parse(t.replace(' ', 'T') + ':00');
      return NaN;
    },

    async loadFiles() { /* legacy no-op */ },

    // ===== Auto-load from /logs with fallback to yesterday =====
    ymd(d){
      const y=d.getFullYear(); const m=String(d.getMonth()+1).padStart(2,'0'); const dd=String(d.getDate()).padStart(2,'0');
      return `${y}-${m}-${dd}`;
    },
    async fetchWithTimeout(url, ms=10000){
      const ctrl=new AbortController();
      const to=setTimeout(()=>ctrl.abort(), ms);
      try {
        const bust = url.includes('?') ? `&_=${Date.now()}` : `?_=${Date.now()}`;
        return await fetch(url + bust, { cache:'no-store', signal: ctrl.signal });
      }
      finally { clearTimeout(to); }
    },
    async fetchJsonIfOk(url, ms=10000){
      try{
        const r = await this.fetchWithTimeout(url, ms);
        if (r && r.ok) return await r.json();
      }catch {}
      return null;
    },
    async fetchJSONWithFallback(urlToday, urlYday){
      let res = await this.fetchWithTimeout(urlToday).catch(()=>null);
      if (res && res.ok) return { data: await res.json(), source: 'today' };
      res = await this.fetchWithTimeout(urlYday).catch(()=>null);
      if (res && res.ok) return { data: await res.json(), source: 'yday' };
      throw new Error('Load failed');
    },
    async autoLoad(){
      try{
        const now = new Date();
        const todayYmd = this.ymd(now);
        if (!this.state.targetDate) this.state.targetDate = todayYmd;
        const prev = new Date(now); prev.setDate(prev.getDate()-1); const yday=this.ymd(prev);
        // Logs live at repo root: /logs/*.json (not under /docs)
        const capToday = `/logs/capital_log_${todayYmd}.json`;
        const capYday  = `/logs/capital_log_${yday}.json`;
        const stratToday = `/logs/strategy_results_${todayYmd}.json`;
        const stratYday  = `/logs/strategy_results_${yday}.json`;
        const btcToday = `/logs/BTC_log_${todayYmd}.json`;
        const btcYday  = `/logs/BTC_log_${yday}.json`;
        // Use only generic daily strategy file (no TF-specific)
        let stratRes = null; let stratSrc = null;
        const tryStrats = [stratToday, stratYday];
        for (const u of tryStrats){ stratRes = await this.fetchJsonIfOk(u); if (stratRes){ stratSrc = u; break; } }

        const [capRes, btcRes] = await Promise.all([
          this.fetchJSONWithFallback(capToday, capYday).catch(()=>null),
          this.fetchJSONWithFallback(btcToday, btcYday).catch(()=>null)
        ]);
        const cap = capRes?.data; const strat = stratRes; const btcArr = btcRes?.data;
        if (!strat && console && console.warn) console.warn('[EV] strategy JSON not found in', tryStrats);
        if (strat && console && console.info) console.info('[EV] strategy JSON loaded from', stratSrc);
        if (Array.isArray(cap)) {
          const normalized = cap.map(r=>({
            ts:this.parseTs(r.time||r.timestamp),
            time:(r.time||r.timestamp),
            capital:Number(r.capital),
            ...(r && typeof r.metrics === 'object' ? { metrics: r.metrics } : {})
          }))
                                 .filter(r=>r.ts && isFinite(r.capital)).sort((a,b)=>a.ts-b.ts);
          this.state.kpiCapital = normalized;
          this.state.chartCapital = normalized; // ensure chart has data on first load
          // keep legacy alias used by finance strip (LIVE today)
          this.state.capital = normalized;
        }
        if (strat && Array.isArray(strat.signals)) {
          this.state.kpiStrategy = strat;
          this.state.chartStrategy = strat; // ensure chart has data on first load
        }
        if (btcArr) { this.renderLiveSignal(btcArr); this.renderMTF(btcArr); }
        this.recomputeDerived();
        this.renderAll();
        // Update chart day label & next button state (chart-only)
        const sel = this.$('#selDay'); if (sel) sel.textContent = this.state.targetDate;
        const isToday = (this.state.targetDate === todayYmd);
        const btnNext = this.$('#btnNextDay'); if (btnNext) btnNext.disabled = isToday;
      }catch(err){ console.warn('Auto-load failed', err); }
    },

    async findNearestDay(startYmd, step){
      const maxSteps = 90;
      const todayYmd = this.ymd(new Date());
      let d = new Date(startYmd);
      for (let i=1;i<=maxSteps;i++){
        d.setDate(d.getDate()+step);
        const ymd = this.ymd(d);
        if (step>0 && ymd>todayYmd) return null;
        const ok = await this.checkAllLogsFor(ymd);
        if (ok) return ymd;
      }
      return null;
    },
    async checkAllLogsFor(ymd){
      // require capital + daily strategy file only (no TF-specific)
      const capU = `/logs/capital_log_${ymd}.json`;
      const stratCandidates = [ `/logs/strategy_results_${ymd}.json` ];
      try{
        const capOK = await this.fetchWithTimeout(capU, 5000).then(r=>!!(r&&r.ok)).catch(()=>false);
        if (!capOK) return false;
        for (const u of stratCandidates){
          const ok = await this.fetchWithTimeout(u, 3000).then(r=>!!(r&&r.ok)).catch(()=>false);
          if (ok) return true;
        }
        return false;
      }catch{ return false; }
    },
    async shiftDay(delta){
      const base = this.state.targetDate || this.ymd(new Date());
      const target = await this.findNearestDay(base, delta);
      if (!target) return; // no available date in range
      this.state.targetDate = target;
      await this.loadChartForDate(target);
      const sel = this.$('#selDay'); if (sel) sel.textContent = target;
      // no global event — keep change local to chart
    },

    async loadChartForDate(ymd){
      try{
        const capU = `/logs/capital_log_${ymd}.json`;
        const stratCandidates = [ `/logs/strategy_results_${ymd}.json` ];
        const capRes = await this.fetchWithTimeout(capU, 8000).then(r=>r.ok?r.json():null).catch(()=>null);
        let stratRes = null;
        for (const u of stratCandidates){
          stratRes = await this.fetchWithTimeout(u, 8000).then(r=>r.ok?r.json():null).catch(()=>null);
          if (stratRes) break;
        }
        if (Array.isArray(capRes)){
          this.state.chartCapital = capRes.map(r=>({
            ts:this.parseTs(r.time||r.timestamp),
            time:(r.time||r.timestamp),
            capital:Number(r.capital),
            ...(r && typeof r.metrics === 'object' ? { metrics: r.metrics } : {})
          }))
                                          .filter(r=>r.ts && isFinite(r.capital)).sort((a,b)=>a.ts-b.ts);
          // do not touch LIVE capital; chart-only dataset
        }
        if (stratRes && Array.isArray(stratRes.signals)){
          this.state.chartStrategy = stratRes;
        }
        this.recomputeDerived();
        this.applyChart();
      }catch(err){ console.warn('loadChartForDate failed', err); }
    },

    recomputeDerived() {
      // Build pnl bars from chartCapital deltas
      const bars = [];
      const cap = this.state.chartCapital || [];
      for (let i = 1; i < cap.length; i++) {
        const d = cap[i].capital - cap[i-1].capital;
        bars.push({ ts: cap[i].ts, delta: d });
      }
      this.state.pnlBars = bars;
    }
  });
}
