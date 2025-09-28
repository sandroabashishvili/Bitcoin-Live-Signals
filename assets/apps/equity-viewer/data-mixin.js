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

    // ===== Auto-load supporting docs/logs → /logs fallback =====
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

    // ---- NEW: multiple-bases helpers (docs/logs first, then /logs) ----
    logsBases(){
      return ['logs', './logs', '../logs', '/logs'];
    },


    async fetchFirstFromBases(fileNames){
      // fileNames: ['capital_log_2025-09-29.json', ...]
      for (const base of this.logsBases()){
        for (const name of fileNames){
          const url = `${base}/${name}`.replace(/\/{2,}/g,'/');
          const res = await this.fetchWithTimeout(url).catch(()=>null);
          if (res?.ok){
            try { return await res.json(); } catch {}
          }
        }
      }
      return null;
    },

    async fetchDailyWithFallback(todayNames, ydayNames){
      // Try today across bases, else yesterday across bases
      let data = await this.fetchFirstFromBases(todayNames);
      if (data) return { data, source:'today' };
      data = await this.fetchFirstFromBases(ydayNames);
      if (data) return { data, source:'yday' };
      throw new Error('Load failed');
    },

    async existsInBases(fileName, timeoutMs=5000){
      for (const base of this.logsBases()){
        const url = `${base}/${fileName}`.replace(/\/{2,}/g,'/');
        const ok = await this.fetchWithTimeout(url, timeoutMs).then(r=>!!(r&&r.ok)).catch(()=>false);
        if (ok) return true;
      }
      return false;
    },

    async autoLoad(){
      try{
        const now = new Date();
        const todayYmd = this.ymd(now);
        if (!this.state.targetDate) this.state.targetDate = todayYmd;
        const prev = new Date(now); prev.setDate(prev.getDate()-1);
        const yday = this.ymd(prev);

        // filenames only (bases დაემატება ჰელსპერებით)
        const capT   = [`capital_log_${todayYmd}.json`];
        const capY   = [`capital_log_${yday}.json`];
        const stratT = [`strategy_results_${todayYmd}.json`];
        const stratY = [`strategy_results_${yday}.json`];
        const btcT   = [`BTC_log_${todayYmd}.json`];
        const btcY   = [`BTC_log_${yday}.json`];

        // load with smart fallback (docs/logs → /logs, today → yday)
        const [capRes, stratRes, btcRes] = await Promise.all([
          this.fetchDailyWithFallback(capT, capY).catch(()=>null),
          // სტრატეგიისთვის საკმარისია "პირველი რომ იპოვოს": ჯერ today, მერე yday
          (async () => {
            const sToday = await this.fetchFirstFromBases(stratT);
            if (sToday) return sToday;
            return await this.fetchFirstFromBases(stratY);
          })().catch(()=>null),
          this.fetchDailyWithFallback(btcT, btcY).catch(()=>null)
        ]);

        const cap   = capRes?.data;
        const strat = stratRes;
        const btcArr= btcRes?.data;

        if (Array.isArray(cap)) {
          const normalized = cap.map(r=>({
            ts:this.parseTs(r.time||r.timestamp),
            time:(r.time||r.timestamp),
            capital:Number(r.capital),
            ...(r && typeof r.metrics === 'object' ? { metrics: r.metrics } : {})
          }))
          .filter(r=>r.ts && isFinite(r.capital))
          .sort((a,b)=>a.ts-b.ts);
          this.state.kpiCapital  = normalized;
          this.state.chartCapital= normalized; // ensure chart has data on first load
          // keep legacy alias used by finance strip (LIVE today)
          this.state.capital     = normalized;
        }

        if (strat && Array.isArray(strat.signals)) {
          this.state.kpiStrategy   = strat;
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
      try{
        const capOK   = await this.existsInBases(`capital_log_${ymd}.json`, 5000);
        if (!capOK) return false;
        const stratOK = await this.existsInBases(`strategy_results_${ymd}.json`, 3000);
        return !!stratOK;
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
        const capNames   = [`capital_log_${ymd}.json`];
        const stratNames = [`strategy_results_${ymd}.json`];

        const capRes   = await this.fetchFirstFromBases(capNames).catch(()=>null);
        const stratRes = await this.fetchFirstFromBases(stratNames).catch(()=>null);

        if (Array.isArray(capRes)){
          this.state.chartCapital = capRes.map(r=>({
            ts:this.parseTs(r.time||r.timestamp),
            time:(r.time||r.timestamp),
            capital:Number(r.capital),
            ...(r && typeof r.metrics === 'object' ? { metrics: r.metrics } : {})
          }))
          .filter(r=>r.ts && isFinite(r.capital))
          .sort((a,b)=>a.ts-b.ts);
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
