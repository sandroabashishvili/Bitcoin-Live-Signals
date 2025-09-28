// assets/apps/equity-viewer/kpi-mixin.js
// KPI overview and finance rendering

export function applyKpiMixin(Cls){
  Object.assign(Cls.prototype, {
    renderKPIs() {
      const host = this.$('#kpis'); if (!host) return;
      const sigs = Array.isArray(this.state.kpiStrategy?.signals) ? this.state.kpiStrategy.signals : [];
      const total = sigs.length;
      const closed = sigs.filter(s => s.status === 'CLOSED');
      const open = sigs.filter(s => s.status === 'OPEN');
      const tpHits = closed.filter(s => (s.net_pnl ?? 0) > 0).length;
      const slHits = closed.filter(s => (s.net_pnl ?? 0) <= 0).length;
      const acc = closed.length ? (tpHits / closed.length * 100) : null;
      const avgRR = closed.length ? (closed.reduce((a, s) => a + (Number.isFinite(s.rrr) ? +s.rrr : 0), 0) / closed.length) : null;
      const avgPnL = closed.length ? (closed.reduce((a, s) => a + (Number.isFinite(s.net_pnl) ? +s.net_pnl : 0), 0) / closed.length) : null;

      const totalNet = closed.reduce((a, s)=> a + (Number.isFinite(s.net_pnl)? +s.net_pnl : 0), 0);
      const lastCap = this.state.kpiCapital[this.state.kpiCapital.length-1]?.capital ?? null;
      const mdd = this.calcMaxDrawdown();
      const elapsed = this.calcElapsedDays(sigs);

      const fmtPct = v => v == null ? '—' : this.n2.format(v) + '%';
      const fmtNum = v => v == null ? '—' : Number(v).toFixed(2);

      // KPI ბოქსებს ვუყენებთ id-ებს, რათა მარტივად ვიპოვოთ
      host.innerHTML = `
        <div class="kpi" id="kpi-total"><div>Total Trades</div><b>${total || '—'}</b></div>
        <div class="kpi" id="kpi-closed"><div>Closed Positions</div><b>${closed.length || '—'}</b></div>
        <div class="kpi" id="kpi-open"><div>Open Positions</div><b>${open.length || '—'}</b></div>
        <div class="kpi" id="kpi-tphits"><div>TP Hits</div><b>${tpHits || 0}</b></div>
        <div class="kpi" id="kpi-slhits"><div>SL Hits</div><b>${slHits || 0}</b></div>
        <div class="kpi" id="kpi-winrate"><div>Win Rate</div><b>${fmtPct(acc)}</b></div>
        <div class="kpi" id="kpi-avgrr"><div>Avg RR</div><b>${fmtNum(avgRR)}</b></div>
        <div class="kpi" id="kpi-avgpnl"><div>Avg Net PnL / Trade</div><b>${fmtNum(avgPnL)}</b></div>
        <div class="kpi" id="kpi-mdd"><div>Max Drawdown</div><b>${mdd==null?'—':fmtNum(mdd)}</b></div>
        <div class="kpi" id="kpi-elapsed"><div>Elapsed</div><b>${elapsed}</b></div>
      `;

      // KPI ბოქსების გაფერადება
      // TP Hits - ყოველთვის მწვანე
      this.$('#kpi-tphits')?.classList.add('pos');
      // SL Hits - ყოველთვის წითელი
      this.$('#kpi-slhits')?.classList.add('neg');
      // Win Rate - >=50% მწვანე, <50% წითელი
      if (acc != null) {
        if (acc >= 50) this.$('#kpi-winrate')?.classList.add('pos');
        else           this.$('#kpi-winrate')?.classList.add('neg');
      }
      // Avg Net PnL / Trade - >=0 მწვანე, <0 წითელი
      if (avgPnL != null) {
        if (avgPnL >= 0) this.$('#kpi-avgpnl')?.classList.add('pos');
        else             this.$('#kpi-avgpnl')?.classList.add('neg');
      }
      // Max Drawdown - <=0 წითელი (ეს არის უარყოფითი always)
      if (mdd != null && mdd <= 0) this.$('#kpi-mdd')?.classList.add('neg');
    },

    renderFinance() {
      const box = this.$('#finance');
      if (!box) return;
      // Try to extract metrics from the last capital entry
      const last = this.state.kpiCapital[this.state.kpiCapital.length - 1];
      const metrics = (last && last.metrics && typeof last.metrics === 'object') ? last.metrics : null;
      const finArr = [];
      if (metrics) {
        for (const [k, v] of Object.entries(metrics)) finArr.push({ Metric: k, Value: String(v) });
      }
      // Look for common finance keys on strategy root as fallback
      const s = this.state.kpiStrategy || {};
      const map = [
        ['Starting Capital', s.starting],
        ['Gross PnL', s.gross],
        ['Fees Paid', s.fees],
        ['Net PnL', s.net],
        ['Exposure', s.exposure],
        ['Available', s.available],
        ['Unrealized PnL', s.unrealized],
        ['Projected Balance', s.projected]
      ].filter(([,v]) => v != null);
      for (const [Metric, Value] of map) finArr.push({ Metric, Value: String(Value) });

      // If still empty, derive from capital/signals
      if (!finArr.length) {
        const sigs = Array.isArray(this.state.kpiStrategy?.signals) ? this.state.kpiStrategy.signals : [];
        const closed = sigs.filter(s=>s.status==='CLOSED');
        const totalNet = closed.reduce((a,s)=> a + (Number.isFinite(+s.net_pnl)? +s.net_pnl : 0), 0);
        if (Number.isFinite(totalNet)) finArr.push({ Metric:'Net PnL (closed)', Value: String(totalNet) });
        const lastCap = this.state.kpiCapital[this.state.kpiCapital.length-1]?.capital;
        if (Number.isFinite(lastCap)) finArr.push({ Metric:'Last Capital', Value: String(lastCap) });
      }

      // Add Strategy Start (earliest signal time or first capital time)
      try {
        let startTs = null;
        const sigs = Array.isArray(this.state.kpiStrategy?.signals) ? this.state.kpiStrategy.signals : [];
        if (sigs.length) {
          const ts = sigs.map(s => this.parseTs(s.time || s.timestamp)).filter(t => Number.isFinite(t) && t>0);
          if (ts.length) startTs = Math.min(...ts);
        }
        if (!startTs && this.state.kpiCapital.length) {
          startTs = this.parseTs(this.state.kpiCapital[0].time || this.state.kpiCapital[0].timestamp);
        }
        if (Number.isFinite(startTs) && startTs>0) {
          const dt = new Date(startTs);
          const nice = dt.toISOString().slice(0,16).replace('T',' ');
          finArr.unshift({ Metric: 'Strategy Start', Value: nice });
        }
      } catch {}

      // Normalize labels to match console (visual only)
      const normalized = finArr.map(({Metric, Value}) => {
        let label = Metric;
        if (label === 'Fees Paid') label = 'Total Fees Paid';
        if (label === 'Exposure') label = 'Active Exposure';
        return { Metric: label, Value };
      });

      // Render cards (id-ებით)
      box.innerHTML = normalized.map(({Metric, Value}, i)=>{
        // ფერადი კლასები: თუ რიცხვია და დადებითი -> pos, უარყოფითი -> neg
        let cls = '';
        let v = Value.replace(/[,$ ]/g,'');
        if (v && !isNaN(+v)) {
          cls = +v > 0 ? 'pos' : +v < 0 ? 'neg' : '';
        }
        // Strategy Start (არც pos/neg)
        if (Metric === 'Strategy Start') cls = '';
        return `<div class="metric" id="metric-${i}"><div class="muted">${Metric}</div><b class="${cls}">${Value}</b></div>`;
      }).join('');

      // Totals strip (როგორც აქამდე)
      const el = this.$('#finTotals'); if (!el) return;
      const sigs = Array.isArray(this.state.kpiStrategy?.signals) ? this.state.kpiStrategy.signals : [];
      const closed = sigs.filter(s=>s.status==='CLOSED');
      const totalNet = closed.reduce((a,s)=> a + (Number.isFinite(+s.net_pnl)? +s.net_pnl : 0), 0);
      const lastCap = this.state.capital[this.state.capital.length-1]?.capital ?? null;
      const startCap = this.state.capital[0]?.capital ?? null;
      const dCls = totalNet>=0 ? 'pos' : 'neg';
      const parts = [
        `<b>Overall Net:</b> <span class="${dCls}">$${this.n2.format(totalNet)}</span>`,
        `<b>Last Capital:</b> ${lastCap==null?'—':('$'+this.n2.format(lastCap))}`,
        startCap!=null ? `<b>Starting:</b> $${this.n2.format(startCap)}` : ''
      ].filter(Boolean);
      el.innerHTML = parts.join(' · ');

      // Finance ბოქსების გაფერადება — დინამიურად ბლოკზე გადაუარე და მიეცი კლასი
      normalized.forEach(({Metric, Value}, i)=>{
        const box = this.$(`#metric-${i}`);
        if (!box) return;
        let v = Value.replace(/[,$ ]/g,'');
        box.classList.remove('pos','neg');
        if (v && !isNaN(+v)) {
          if (+v > 0) box.classList.add('pos');
          else if (+v < 0) box.classList.add('neg');
        }
      });
    },

    calcMaxDrawdown(){
      const cap = this.state.capital; if (!cap.length) return null;
      let peak = cap[0].capital; let mdd = 0;
      for (const r of cap){ peak = Math.max(peak, r.capital); mdd = Math.min(mdd, r.capital - peak); }
      return mdd; // negative value
    },

    calcElapsedDays(sigs){
      if (!Array.isArray(sigs) || !sigs.length) return '—';
      const ordered=[...sigs].sort((a,b)=>this.parseTs(a.time)-this.parseTs(b.time));
      const first=ordered[0], last=ordered[ordered.length-1];
      const days = Math.max(1, Math.round((this.parseTs(last.time)-this.parseTs(first.time))/(1000*60*60*24)));
      return days + ' days';
    }
  });
}
