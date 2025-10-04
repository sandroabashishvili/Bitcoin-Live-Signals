// assets/apps/volume-visualizer.js
// Orderbook Volume (30m) — Single Panel (Shadow DOM, refined)

class VolumeVisualizer extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    // data
    this.rows = [];
    this.pageSize = 5;
    this.pageIndex = 0;

    // utils
    this.n2 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
    this.n0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
    this.shortInt = (n) => (n > 999 ? (Math.round(n / 100) / 10) + 'k' : String(n));

    // bindings
    this.boundResize = () => { try { this.chart?.resize(); } catch {} };
    this.boundTheme  = () => { try { this.applyChartTheme(); this.renderChart(); this.chart?.resize(); } catch {} };
  }

  connectedCallback() {
    this.render();
    this.initChart();
    this.autoLoad();

    window.addEventListener('resize', this.boundResize);
    window.addEventListener('themechange', this.boundTheme);

    // lightweight ticker hookup (optional)
    try {
      if (window.SSHTicker?.subscribe) {
        const tick = () => { if (!document.hidden) this.autoLoad(); };
        this._unsubTicker = window.SSHTicker.subscribe(tick);
      }
    } catch {}
  }

  disconnectedCallback() {
    window.removeEventListener('resize', this.boundResize);
    window.removeEventListener('themechange', this.boundTheme);
    try { this.chart?.dispose(); } catch {}
    this.chart = null;
    try { this._unsubTicker?.(); this._unsubTicker = null; } catch {}
  }

  $(q) { return this.shadowRoot.querySelector(q); }

  render() {
  this.shadowRoot.innerHTML = `
    <style>
      /* Layout rhythm match with page */
      :host { display:block; margin:0; }
      .wrap { max-width:1320px; margin:0 auto; padding:0 18px; } /* same side gutter as other panels */

      /* Panel */
      .panel{
        background:var(--card,#fff);
        border:1px solid var(--line,#e6e6e9);
        border-radius:16px;
        padding:12px;                     /* compact inner padding */
        box-shadow:0 4px 12px rgba(0,0,0,.05);
        transition: box-shadow .18s ease, transform .18s ease;
      }
      .panel:hover{ box-shadow:0 6px 14px rgba(0,0,0,.08); transform: translateY(-1px) }

      /* Header */
      .header{
        display:grid; grid-template-columns:1fr auto; align-items:center;
        gap:10px; margin-bottom:8px;
      }
      .title{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:18px }
      .sub{ color: var(--muted,#64748b); font-size:13px }

      /* Controls */
      .controls{ display:flex; align-items:center; gap:8px; flex-wrap:wrap }
      .btn{
        background: color-mix(in oklab, var(--card,#fff) 92%, transparent);
        border:1px solid var(--line,#e6e6e9);
        padding:8px 12px; border-radius:10px; cursor:pointer;
        transition: box-shadow .18s ease, transform .18s ease, background-color .18s ease, border-color .18s ease;
        color: inherit;
      }
      .btn:hover{ background: color-mix(in oklab, var(--card,#fff) 88%, transparent); box-shadow:0 3px 10px rgba(0,0,0,.08); transform: translateY(-1px) }
      .btn[disabled]{ opacity:.6; cursor:not-allowed }

      /* Stats row */
      .stats{
        display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
        gap:8px; margin:6px 0 6px 0;
      }
      .stat{
        display:grid; grid-template-columns:1fr auto; gap:6px;
        padding:8px 10px; border-radius:12px;
        background: color-mix(in oklab, var(--card,#fff) 94%, transparent);
        border:1px solid var(--line,#e6e6e9);
        transition: box-shadow .18s ease, transform .18s ease;
      }
      .stat:hover{ box-shadow:0 4px 12px rgba(0,0,0,.08); transform: translateY(-1px) }
      .stat b{ font-size:18px }
      .delta-pos{ color:var(--buy,#16a34a) }
      .delta-neg{ color:var(--sell,#dc2626) }

      /* Chart */
      .chart{ height:420px; border-radius:12px; margin-bottom:6px }

      /* Table */
      .table-wrap{
        max-height:40vh; overflow:auto;
        border:1px solid var(--line,#e6e6e9);
        border-radius:12px; background:var(--card,#fff)
      }
      table{ width:100%; border-collapse:separate; border-spacing:0 }
      .interactive-table{ table-layout: fixed }
      .interactive-table thead th:nth-child(1),
      .interactive-table tbody td:nth-child(1){ width:160px; white-space:nowrap }
      thead th{
        text-align:left; font-weight:600; font-size:13px; padding:10px;
        border-bottom:1px solid color-mix(in oklab, var(--ink,#000) 20%, transparent);
        position:sticky; top:0; z-index:2;
        background: color-mix(in oklab, var(--card,#fff) 92%, transparent);
        backdrop-filter: saturate(120%) blur(4px)
      }
      tbody td{
        padding:10px; border-bottom:1px solid color-mix(in oklab, var(--ink,#000) 12%, transparent); font-size:13px;
        transition: background-color .18s ease; background: var(--card,#fff);
      }
      tbody tr:hover td{ background: color-mix(in oklab, var(--card,#fff) 92%, transparent) }
      .num{ text-align:right; font-variant-numeric: tabular-nums }

      /* Footer strip */
      .foot{
        display:flex; align-items:center; justify-content:space-between;
        gap:8px; margin-top:6px; color:var(--muted,#64748b); font-size:13px
      }

      /* Small screens: stacked table */
      @media (max-width:420px){
        .interactive-table thead{ display:none }
        .interactive-table, .interactive-table tbody, .interactive-table tr, .interactive-table td{
          display:block; width:100%
        }
        .interactive-table tr{
          margin:12px 0; border:1px solid var(--line,#e6e6e9);
          border-radius:12px; padding:10px; background: var(--card,#fff)
        }
        .interactive-table td{ border:none; padding:6px 0 }
        .interactive-table td::before{
          content: attr(data-label); display:block; font-size:.8rem; opacity:.7; margin-bottom:2px
        }
      }
    </style>

    <div class="wrap">
      <div class="panel">
        <div class="header">
          <div class="title">
            📈 Orderbook Volume (30m)
            <span class="sub">Current: <b id="obSelDay">—</b></span>
          </div>
          <div class="controls">
            <button class="btn" id="obPrevDay" title="Previous day">← Prev Day</button>
            <button class="btn" id="obNextDay" title="Next day">Next Day →</button>
            <div style="width:1px;height:24px;background:color-mix(in oklab, var(--ink,#000) 20%, transparent);margin:0 6px"></div>
            <button class="btn" id="btnBack" title="Back (newer)">Back</button>
            <button class="btn" id="btnNext" title="Next (older)">Next</button>
          </div>
        </div>

        <div id="stats" class="stats"></div>
        <div id="chart" class="chart" role="img" aria-label="Orderbook delta chart"></div>

        <div class="table-wrap" role="region" aria-label="Orderbook table container">
          <table class="interactive-table" role="table" aria-label="Buy Sell Table">
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col" class="num">Buy</th>
                <th scope="col" class="num">Sell</th>
                <th scope="col" class="num">Δ (Buy−Sell)</th>
                <th scope="col" class="num">Cum Δ</th>
              </tr>
            </thead>
            <tbody id="tbody"></tbody>
          </table>
        </div>

        <div class="foot">
          <div id="pagerInfo">Page 1 / 1</div>
          <div class="sub">Tip: Scroll table to see more rows</div>
        </div>
      </div>
    </div>
  `;

    // controls
    this.$('#obPrevDay')?.addEventListener('click', () => this.shiftDay(-1));
    this.$('#obNextDay')?.addEventListener('click', () => this.shiftDay(+1));
    this.$('#btnBack')?.addEventListener('click', () => { if (this.pageIndex > 0) { this.pageIndex--; this.renderTable(); } });
    this.$('#btnNext')?.addEventListener('click', () => { const tp = this.totalPages(); if (this.pageIndex < tp - 1) { this.pageIndex++; this.renderTable(); } });

    // init selected day
    this.obTargetDate = this.ymd(new Date());
    this.updateDayLabel();
  }

  // ---------- Data utils ----------
  parseTs(t){
    if (typeof t === 'number') return t;
    if (typeof t !== 'string') return NaN;
    let d = Date.parse(t); if (!isNaN(d)) return d;
    d = Date.parse(t.replace(' ','T')); if (!isNaN(d)) return d;
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(t)) return Date.parse(t.replace(' ','T')+':00');
    return NaN;
  }
  parseRows(arr){
    const out = (arr||[]).map(r=>{
      const ts   = this.parseTs(r.time ?? r.timestamp ?? r.date);
      const buy  = r.buy_volume ?? r.buy;
      const sell = r.sell_volume ?? r.sell;
      if (isNaN(ts) || buy==null || sell==null) return null;
      return { ts, time:new Date(ts).toISOString().slice(0,16).replace('T',' '), buy:+buy, sell:+sell };
    }).filter(Boolean).sort((a,b)=>a.ts-b.ts);
    let cum=0; for(const r of out){ r.delta=r.buy-r.sell; cum+=r.delta; r.cum=cum; }
    return out;
  }

  // ---------- Chart ----------
  initChart(){
    const E = (window?.echarts) || (typeof echarts!=='undefined' ? echarts : null);
    if (!E) return;
    this.chart = E.init(this.$('#chart'));
    const min30 = 30*60*1000;
    this.chart.setOption({
      grid:{ left:56, right:20, top:32, bottom:40 },
      tooltip:{ trigger:'axis', axisPointer:{ type:'shadow' } },
      dataZoom:[ { type:'inside', xAxisIndex:0 } ],
      xAxis:{ type:'time', minInterval:min30, axisLabel:{ hideOverlap:true, formatter:(val)=>{
        const d=new Date(val);
        const hh=String(d.getHours()).padStart(2,'0');
        const mm=String(d.getMinutes()).padStart(2,'0');
        const dd=String(d.getDate()).padStart(2,'0');
        const mo=String(d.getMonth()+1).padStart(2,'0');
        return `${hh}:${mm} · ${dd}.${mo}`;
      }}},
      yAxis:{ type:'value', splitLine:{ lineStyle:{ opacity:.15 } } },
      legend:{ show:false },
      animationDurationUpdate: 200
    });
    this.applyChartTheme();
  }

  getThemeColors(){
    const cs = getComputedStyle(document.documentElement);
    return {
      ink  : (cs.getPropertyValue('--ink')  || '#222').trim(),
      muted: (cs.getPropertyValue('--muted')|| '#64748b').trim(),
      grid : (cs.getPropertyValue('--line') || '#e6e6e9').trim(),
      buy  : (cs.getPropertyValue('--buy')  || '#16a34a').trim(),
      sell : (cs.getPropertyValue('--sell') || '#dc2626').trim(),
    };
  }
  applyChartTheme(){
    if (!this.chart) return;
    const { ink, muted, grid } = this.getThemeColors();
    this.chart.setOption({
      textStyle: { color: ink },
      xAxis: [{ axisLabel:{ color: muted }, axisLine:{ lineStyle:{ color: grid } }, splitLine:{ lineStyle:{ color: grid, opacity:.3 } } }],
      yAxis: [{ axisLabel:{ color: muted }, axisLine:{ lineStyle:{ color: grid } }, splitLine:{ lineStyle:{ color: grid, opacity:.3 } } }],
      tooltip: { textStyle:{ color: ink } }
    });
  }

  renderChart(){
    if (!this.chart || !this.rows.length) return;
    const { buy:POS, sell:NEG } = this.getThemeColors();
    const times = this.rows.map(r=>r.ts);
    const net   = this.rows.map(r=> (r.buy - r.sell));
    const maxAbs = Math.max(...net.map(v=>Math.abs(v)), 1);
    this.chart.setOption({
      yAxis:{ min:-maxAbs, max:maxAbs, splitLine:{ lineStyle:{ opacity:.15 } } },
      series:[{
        type:'bar', name:'Δ (Buy−Sell)',
        data: times.map((t,i)=>[t, net[i]]),
        barMaxWidth: 18, barMinWidth: 6,
        itemStyle:{ color:(p)=> (p.value[1]>=0 ? POS : NEG) },
        emphasis:{ focus:'series' }
      }],
      tooltip:{
        trigger:'axis', axisPointer:{ type:'shadow' },
        formatter:(params)=>{
          const p = params?.[0]; if(!p) return '';
          const ts = p.value[0]; const v = p.value[1];
          const d=new Date(ts);
          const hh=String(d.getHours()).padStart(2,'0');
          const mm=String(d.getMinutes()).padStart(2,'0');
          const dd=String(d.getDate()).padStart(2,'0');
          const mo=String(d.getMonth()+1).padStart(2,'0');
          const time = `${hh}:${mm} · ${dd}.${mo}`;
          return `${time}<br/>Δ (Buy−Sell): <b>${Number(v).toFixed(2)}</b>`;
        }
      }
    });
  }

  // ---------- Stats & Table ----------
  renderStats(){
    const el = this.$('#stats'); if (!el) return;
    const d = this.rows; if (!d.length){ el.innerHTML=''; return; }
    const totalBuy = d.reduce((s,r)=>s+r.buy,0);
    const totalSell = d.reduce((s,r)=>s+r.sell,0);
    const net = totalBuy-totalSell;
    const maxB = d.reduce((a,b)=>a.buy>b.buy?a:b);
    const maxS = d.reduce((a,b)=>a.sell>b.sell?a:b);
    el.innerHTML = `
      <div class="stat"><span>Total Buy</span><b>${this.n2.format(totalBuy)}</b></div>
      <div class="stat"><span>Total Sell</span><b>${this.n2.format(totalSell)}</b></div>
      <div class="stat"><span>Net Δ</span><b class="${net>=0?'delta-pos':'delta-neg'}">${this.n2.format(net)}</b></div>
      <div class="stat"><span>Max Buy @ ${maxB.time}</span><b>${this.n2.format(maxB.buy)}</b></div>
      <div class="stat"><span>Max Sell @ ${maxS.time}</span><b>${this.n2.format(maxS.sell)}</b></div>`;
  }

  totalPages(){ return Math.max(1, Math.ceil(this.rows.length / this.pageSize)); }
  getPageDesc(idx){
    const desc = this.rows.slice().sort((a,b)=>b.ts-a.ts);
    const start = idx*this.pageSize;
    return desc.slice(start, start+this.pageSize);
  }
  renderPager(){
    const tp = this.totalPages(); const total = this.rows.length;
    this.$('#pagerInfo').textContent = `Page ${Math.min(this.pageIndex+1,tp)} / ${tp} · Records: ${this.shortInt(total)}`;
    this.$('#btnBack').disabled = (this.pageIndex<=0);
    this.$('#btnNext').disabled = (this.pageIndex>=tp-1);
  }
  renderTable(){
    const body = this.$('#tbody');
    if(!this.rows.length){ body.innerHTML=''; this.renderPager(); return; }
    const page = this.getPageDesc(this.pageIndex);
    const clamp = (v)=> (Math.abs(v)<1e-10?0:v);
    body.innerHTML = page.map(r=>`<tr>
      <td class="nowrap" data-label="Time">${r.time}</td>
      <td class="num" data-label="Buy">${this.n2.format(clamp(r.buy))}</td>
      <td class="num" data-label="Sell">${this.n2.format(clamp(r.sell))}</td>
      <td class="num ${r.delta>=0?'delta-pos':'delta-neg'}" data-label="Δ (Buy−Sell)">${this.n2.format(clamp(r.delta))}</td>
      <td class="num ${r.cum>=0?'delta-pos':'delta-neg'}" data-label="Cum Δ">${this.n2.format(clamp(r.cum))}</td>
    </tr>`).join('');
    this.renderPager();
  }

  // ---------- IO ----------
  async autoLoad(){
    try { await this.loadForDate(this.obTargetDate || this.ymd(new Date())); }
    catch(err){ console.warn('Orderbook auto-load failed', err); }
  }

  ymd(d){ const y=d.getFullYear(); const m=String(d.getMonth()+1).padStart(2,'0'); const dd=String(d.getDate()).padStart(2,'0'); return `${y}-${m}-${dd}`; }
  async fetchWithTimeout(url, ms=10000){
    const c=new AbortController(); const t=setTimeout(()=>c.abort(), ms);
    try { const bust = url.includes('?')?`&_=${Date.now()}`:`?_=${Date.now()}`; return await fetch(url+bust,{cache:'no-store', signal:c.signal}); }
    finally { clearTimeout(t); }
  }
  async fetchJSONFirst(candidates){
    for (const u of candidates){
      const r = await this.fetchWithTimeout(u).catch(()=>null);
      if(r?.ok){ try { return await r.json(); } catch {} }
    }
    throw new Error('Load failed');
  }

  async loadForDate(ymd){
    try{
      const d = new Date(ymd); if (isNaN(+d)) return;
      const y = new Date(d); y.setDate(y.getDate()-1);

      const candToday = [
       `logs/orderbook_30m_${this.ymd(d)}.json`,
       `logs/orderbook_${this.ymd(d)}.json`,
      ];
      const candYday = [
      `logs/orderbook_30m_${this.ymd(y)}.json`,
      `logs/orderbook_${this.ymd(y)}.json`,
      ];

      let data = null, used = null, source = 'today';
      try { data = await this.fetchJSONFirst(candToday); }
      catch { data = await this.fetchJSONFirst(candYday); source='yday'; used=this.ymd(y); }

      this.rows = this.parseRows(data||[]);
      this.pageIndex = 0;

      this.renderChart();
      this.renderStats();
      this.renderTable();

      this.obTargetDate = used || this.ymd(d);
      this.updateDayLabel();

      if (source==='yday' && used) {
        window.dispatchEvent(new CustomEvent('daychange', { detail: { date: used } }));
      }
    }catch(err){ console.warn('loadForDate failed', err); }
  }

  updateDayLabel(){
    const el = this.$('#obSelDay'); if (el) el.textContent = this.obTargetDate || '—';
    const isToday = (this.obTargetDate === this.ymd(new Date()));
    const nx = this.$('#obNextDay'); if (nx) nx.disabled = isToday;
  }

  shiftDay(delta=0){
    try{
      const d = new Date(this.obTargetDate || this.ymd(new Date()));
      d.setDate(d.getDate() + delta);
      this.loadForDate(this.ymd(d));
    }catch{}
  }
}

customElements.define('volume-visualizer', VolumeVisualizer);
