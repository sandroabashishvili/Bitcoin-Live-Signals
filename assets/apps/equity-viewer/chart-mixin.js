// assets/apps/equity-viewer/chart-mixin.js
export function applyChartMixin(Cls){
  Object.assign(Cls.prototype, {
    initChart() {
      const E = (typeof window !== 'undefined' && window.echarts)
        ? window.echarts
        : (typeof echarts !== 'undefined' ? echarts : null);
      if (!E) return;

      // chart root lookup: prefer shadow host if present
      const root = this.chartRoot || (this.$ ? this.$('#chart')?.closest(':host, body') : document);
      const el = this.$?.('#chart')
        || (this.shadowRoot ? this.shadowRoot.querySelector('#chart') : null)
        || (root?.querySelector ? root.querySelector('#chart') : null)
        || document.querySelector('#chart');
      if (!el) return;

      this.echarts = E;
      this.chart = E.init(el);
      this._onResize = () => { try{ this.chart?.resize(); }catch{} };
      window.addEventListener('resize', this._onResize, { passive:true });

      this.applyChart();
      this.applyChartTheme();
    },

    getThemeColors(){
      const cs = getComputedStyle(document.documentElement);
      const ink = (cs.getPropertyValue('--ink')||'#222').trim();
      const muted = (cs.getPropertyValue('--muted')||'#64748b').trim();
      const grid = (cs.getPropertyValue('--line')||'#e6e6e9').trim();
      return { ink, muted, grid };
    },

    applyChartTheme(){
      if (!this.chart) return;
      const { ink, muted, grid } = this.getThemeColors();
      this.chart.setOption({
        textStyle: { color: ink },
        xAxis: { axisLabel:{ color: muted }, axisLine:{ lineStyle:{ color: grid } }, splitLine:{ lineStyle:{ color: grid, opacity:.3 } } },
        yAxis: { axisLabel:{ color: muted }, axisLine:{ lineStyle:{ color: grid } }, splitLine:{ lineStyle:{ color: grid, opacity:.3 } } },
        tooltip: { textStyle:{ color: ink } }
      }, false);
    },

    applyChart() {
      if (!this.chart) return;
      const cap = (this.state?.chartCapital && this.state.chartCapital.length)
        ? this.state.chartCapital
        : (this.state?.capital || []);
      window.CAPITAL = Array.isArray(cap) ? cap : [];

      const amplify = this.state?.amplify ? 1.8 : 1.0;
      const min30 = 30 * 60 * 1000;

      if (!cap.length) { this.chart.clear(); return; }

      const firstValid = cap.find(r => typeof r?.capital === 'number' && isFinite(r.capital));
      const start = (firstValid?.capital && isFinite(firstValid.capital)) ? firstValid.capital : 1;

      const data = cap.map(r => {
        const t = (r.ts !== undefined) ? Number(r.ts) : (r.time ? new Date(r.time).getTime() : NaN);
        const rel = (typeof r.capital === 'number' && isFinite(r.capital))
          ? ((r.capital - start) / start) * 100 * amplify
          : NaN;
        return [t, rel];
      }).filter(d => Number.isFinite(d[0]) && Number.isFinite(d[1]));
      if (!data.length) { this.chart.clear(); return; }

      const lastDelta = data[data.length - 1][1] ?? 0;
      const up = lastDelta >= 0;
      const lineColor = up ? '#22c55e' : '#ef4444';
      const areaBase = up ? '#bbf7d0' : '#fee2e2';

      let gradArea = areaBase;
      if (this.echarts?.graphic?.LinearGradient) {
        gradArea = new this.echarts.graphic.LinearGradient(0,0,0,1,[
          { offset: 0, color: areaBase },
          { offset: 1, color: 'rgba(34,197,94,0.01)' }
        ]);
      }

      const lastPt = data[data.length - 1];
      const markPoints = [
        { type: 'max', name: 'Max', symbolSize: 32 },
        { type: 'min', name: 'Min', symbolSize: 32 }
      ];
      if (lastPt) {
        markPoints.push({
          coord: lastPt,
          name: 'Last',
          symbol: 'circle',
          symbolSize: 18,
          itemStyle: { color: lineColor, borderColor: '#fff', borderWidth: 2 },
          label: {
            show: true,
            position: 'top',
            color: lineColor,
            fontWeight: 'bold',
            fontSize: 15,
            formatter: (p) => `${Number(Array.isArray(p.value)?p.value[1]:p.value).toFixed(2)}%`
          }
        });
      }

      this.chart.clear();
      this.chart.setOption({
        grid: { left: 56, right: 18, top: 28, bottom: 40 },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          backgroundColor: 'rgba(20,24,36,0.92)',
          borderRadius: 8, borderWidth: 0, padding: [8,16],
          textStyle: { fontSize: 14 },
          formatter: (params) => {
            const pt = params?.[0]; if(!pt) return '';
            const idx = pt.dataIndex;
            const startCapital = window.CAPITAL?.[0]?.capital ?? '-';
            const nowCapital = window.CAPITAL?.[idx]?.capital ?? '-';
            const pnlAbs = (Number.isFinite(nowCapital) && Number.isFinite(startCapital))
              ? (nowCapital - startCapital).toFixed(2) : '-';
            const ts = Array.isArray(pt.value) ? pt.value[0] : pt.value;
            const perc = Array.isArray(pt.value) ? pt.value[1] : null;
            return `
              <b>${new Date(ts).toLocaleString()}</b><br>
              Start Capital: <b>${startCapital}</b><br>
              Current: <b>${nowCapital}</b><br>
              Δ%: <b>${Number(perc).toFixed(2)}%</b><br>
              PnL: <b>${pnlAbs}</b>
            `;
          }
        },
        xAxis: {
          type: 'time',
          minInterval: min30,
          axisLabel: {
            hideOverlap:true, fontSize: 13,
            formatter: (val) => {
              const d = new Date(val);
              const dd = String(d.getDate()).padStart(2,'0');
              const mo = String(d.getMonth()+1).padStart(2,'0');
              const hh = String(d.getHours()).padStart(2,'0');
              const mm = String(d.getMinutes()).padStart(2,'0');
              return `${hh}:${mm}\n${dd}.${mo}`;
            }
          }
        },
        yAxis: { type: 'value', splitLine: { lineStyle: { opacity: .15 } } },
        series: [{
          type: 'line',
          name: 'Equity',
          showSymbol: true, symbolSize: 6, smooth: 0.8,
          lineStyle: { width: 2, color: lineColor },
          areaStyle: { opacity: .18, color: gradArea },
          emphasis: { focus: 'series' },
          data,
          markPoint: { data: markPoints, label: { fontWeight: 'bold', fontSize: 13 } }
        }]
      }, true);
    },

    destroyChart(){
      try { window.removeEventListener('resize', this._onResize); this.chart?.dispose(); } catch {}
      this.chart = null;
      this._onResize = null;
    }
  });
}
