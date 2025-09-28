// assets/apps/equity-viewer/indicators-mixin.js
// Indicator tables and donuts (always show full catalog with zeros)

export function applyIndicatorsMixin(Cls){
  Object.assign(Cls.prototype, {

    // ---- Catalog of indicators (pretty names) ----
    getIndicatorCatalog(){
      const core = [
        ['rsi_macd',        'RSI/MACD Momentum Trigger'],
        ['ema_cross',       'EMA Trend Confirmation'],
        ['volatility_spike','Volatility Spike Detection'],
        ['macd_histogram',  'MACD Histogram Growth'],
        ['trend_confirm',   'Trend Confirm (Ichimoku + RSI + MACD)'],
      ];
      const support = [
        ['vwap_bias',       'VWAP Positional Bias'],
        ['mtf_agreement',   'Multi-Timeframe Agreement'],
        ['adx_momentum',    'ADX + Momentum Strength'],
        ['order_dominance', 'Order Imbalance Dominance'],
        ['liquidity_zone',  'Liquidity Zone Proximity'],
      ];
      return { core, support };
    },

    // normalize/parse flags that may be object or stringified json
    parseFlags(raw){
      if (raw == null) return {};
      let flags = raw;
      if (typeof raw === 'string') {
        try {
          flags = JSON.parse(raw);
        } catch {
          return {};
        }
      }
      return (flags && typeof flags === 'object') ? flags : {};
    },

    // Aggregate closed signals, but start from full catalog prefilled with zeros
    aggregateByFlags(signals, key){
      const { core, support } = this.getIndicatorCatalog();
      const pairs = key === 'core' ? core : support;

      /** @type {Map<string,{tp:number,sl:number,_key:string}>} */
      const map = new Map(pairs.map(([k, pretty]) => [pretty, { tp:0, sl:0, _key:k }]));

      const closed = Array.isArray(signals) ? signals.filter(s => s && s.status === 'CLOSED') : [];
      for (const s of closed) {
        const raw   = (key === 'core') ? (s.core_debug ?? {}) : (s.support_debug ?? {});
        const flags = this.parseFlags(raw);
        const isTP  = (Number(s?.net_pnl) || 0) > 0;

        // known catalog first (naming stays consistent)
        for (const [k, pretty] of pairs) {
          if (!flags[k]) continue; // count only when flag true
          let rec = map.get(pretty);
          if (!rec) { rec = { tp:0, sl:0, _key:k }; map.set(pretty, rec); }
          if (isTP) rec.tp++; else rec.sl++;
        }

        // unknown/extra indicators -> ad-hoc lines
        for (const [name, val] of Object.entries(flags)) {
          if (!val) continue;
          const isKnown = pairs.some(([k]) => k === name);
          if (isKnown) continue;
          const base   = (/^\d+$/.test(name) ? 'Unknown' : name);
          const pretty = base;
          let rec = map.get(pretty);
          if (!rec) { rec = { tp:0, sl:0, _key: base }; map.set(pretty, rec); }
          if (isTP) rec.tp++; else rec.sl++;
        }
      }

      // build & sort rows
      const rows = [...map.entries()].map(([name, v]) => ({ name, tp:v.tp, sl:v.sl }));
      rows.sort((a,b)=>{
        const aAct = a.tp + a.sl, bAct = b.tp + b.sl;
        if (bAct !== aAct) return bAct - aAct;                 // activity desc
        const aDelta = a.tp - a.sl, bDelta = b.tp - b.sl;
        if (bDelta !== aDelta) return bDelta - aDelta;          // delta desc
        return a.name.localeCompare(b.name);                    // name asc
      });
      return rows;
    },

    donutTotals(signals, key){
      const closed = Array.isArray(signals) ? signals.filter(s => s && s.status === 'CLOSED') : [];
      let tp=0, sl=0;
      for (const s of closed){
        const flags = this.parseFlags(key==='core' ? (s.core_debug||{}) : (s.support_debug||{}));
        // count this trade once if ANY indicator in this group was true
        if (Object.values(flags).some(Boolean)) {
          if ((Number(s?.net_pnl) || 0) > 0) tp++; else sl++;
        }
      }
      return { tp, sl }; // can be 0/0 -> donut will still render with 0% text
    },

    // Ensure number formatters exist even if host class forgot to set them
    ensureFormatters(){
      if (!this.n2) this.n2 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
      if (!this.n0) this.n0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
    },

    renderIndicators(){
      this.ensureFormatters();

      const sigs = Array.isArray(this.state?.kpiStrategy?.signals) ? this.state.kpiStrategy.signals : [];
      const section = this.$ ? this.$('#indSection') : document.querySelector('#indSection');
      if (!section) return;

      // Always show the section; fallback to zeros if nothing present
      section.style.display = '';

      // Donuts
      const coreT = this.donutTotals(sigs, 'core');
      const supT  = this.donutTotals(sigs, 'support');
      this.renderDonut('core', this.$('#indCoreDonut'), coreT.tp, coreT.sl);
      this.renderDonut('support', this.$('#indSupportDonut'), supT.tp, supT.sl);

      const coreMeta = this.$('#indCoreMeta');     if (coreMeta) coreMeta.textContent   = `Core — TP ${coreT.tp} / SL ${coreT.sl}`;
      const supMeta  = this.$('#indSupportMeta');  if (supMeta)  supMeta.textContent    = `Support — TP ${supT.tp} / SL ${supT.sl}`;

      // Tables — always include full catalog (zeros if no data)
      const coreRows = this.aggregateByFlags(sigs, 'core');
      const supRows  = this.aggregateByFlags(sigs, 'support');

      const fill = (tblSel, rows) => {
        const tbHost = this.$(tblSel);
        const tb = this.$(tblSel + ' tbody');
        if (!tbHost || !tb) return;

        const fmtPct = (v)=> this.n2.format(v) + '%';
        tb.innerHTML = rows.map(r=>{
          const total = r.tp + r.sl;
          const acc   = total ? (r.tp/total*100) : 0;
          const delta = r.tp - r.sl;
          const accCls = acc>=50 ? 'pos' : 'neg';
          const dCls   = delta>0 ? 'pos' : (delta<0 ? 'neg' : '');
          return `<tr>
            <td>${r.name}</td>
            <td class="num pos">${r.tp}</td>
            <td class="num neg">${r.sl}</td>
            <td class="num ${dCls}">${delta}</td>
            <td class="num ${accCls}">${fmtPct(acc)}</td>
          </tr>`;
        }).join('');
      };

      // Totals strips (place right above each table)
      const sum = (arr, key) => arr.reduce((a,r)=>a + (r[key]||0), 0);
      const coreTotals = { tp: sum(coreRows,'tp'), sl: sum(coreRows,'sl') };
      const supTotals  = { tp: sum(supRows,'tp'),  sl: sum(supRows,'sl')  };

      const renderTotals = (hostSel, totals, label)=>{
        const host = this.$(hostSel);
        if (!host) return;
        const stripId = (label==='Core') ? 'coreTotalsStrip' : 'supTotalsStrip';
        const delta = totals.tp - totals.sl;
        const acc   = (totals.tp + totals.sl) ? (totals.tp/(totals.tp+totals.sl)*100) : 0;
        const dCls  = delta>0 ? 'pos' : (delta<0 ? 'neg' : '');
        const aCls  = acc>=50 ? 'pos' : 'neg';
        const html  = `<div class="muted" style="margin:4px 0 6px" id="${stripId}">
          <b>${label} Totals:</b> TP Σ <span class="pos">${this.n0.format(totals.tp)}</span>
          · SL Σ <span class="neg">${this.n0.format(totals.sl)}</span>
          · Δ Σ <span class="${dCls}">${this.n0.format(delta)}</span>
          · Acc% Σ <span class="${aCls}">${this.n2.format(acc)}%</span>
        </div>`;

        const exist = this.$('#'+stripId);
        if (exist) {
          exist.outerHTML = html;
        } else {
          host.insertAdjacentHTML('beforebegin', html);
        }
      };

      renderTotals('#tblCore', coreTotals, 'Core');
      renderTotals('#tblSupport', supTotals, 'Support');

      fill('#tblCore', coreRows);
      fill('#tblSupport', supRows);
    },

    renderDonut(key, el, tp, sl){
      const E = (typeof window!=='undefined' && window.echarts) ? window.echarts :
                (typeof echarts!=='undefined' ? echarts : null);
      if (!el || !E) return;

      if (!this.donuts) this.donuts = {};
      let chart = this.donuts[key];
      if (!chart) { chart = E.init(el); this.donuts[key] = chart; }

      const cs   = getComputedStyle(document.documentElement);
      const buy  = (cs.getPropertyValue('--buy').trim()  || '#16a34a');
      const sell = (cs.getPropertyValue('--sell').trim() || '#dc2626');
      const ink  = (cs.getPropertyValue('--ink').trim()  || '#222');

      const total = (tp||0) + (sl||0);
      const acc   = total ? (tp/total*100) : 0;

      // ECharts pie დედა-სიბოლოებზე შეიძლება “არაფერი” დახატოს როცა ორივე 0-ია.
      // ამიტომ ვაძლევთ ძალიან მცირე მნიშვნელობებს, ვიზუალი რომ არ გაქრეს; ტექსტი მაინც 0% იქნება.
      const tpVal = total ? tp : 0.0001;
      const slVal = total ? sl : 0.0001;

      chart.setOption({
        title:{
          text: `${this.n2.format(acc)}%`,
          left:'center', top:'50%',
          textStyle:{ fontSize: 16, fontWeight: '700', color: ink }
        },
        tooltip:{ trigger:'item', formatter:(p)=> `${p.name}: ${p.value} (${p.percent}%)` },
        legend:{ show:false },
        series:[{
          type:'pie',
          radius:['56%','80%'],
          avoidLabelOverlap:true,
          label:{ show:false },
          data:[
            { value: tpVal, name:'TP', itemStyle:{ color: buy } },
            { value: slVal, name:'SL', itemStyle:{ color: sell } }
          ]
        }]
      });
    }
  });
}
