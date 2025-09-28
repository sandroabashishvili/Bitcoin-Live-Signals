// assets/apps/equity-viewer/trades-mixin.js
// Trades table filtering, paging, and rendering

export function applyTradesMixin(Cls){
  Object.assign(Cls.prototype, {
    filteredSignals() {
      const sigs = Array.isArray(this.state.kpiStrategy?.signals) ? this.state.kpiStrategy.signals : [];
      // ფილტრები: Status, Side, Result
      let filtered = sigs;

      // Status
      if (this.state.statusFilter && this.state.statusFilter !== 'ALL') {
        filtered = filtered.filter(s => (s.status || '').toUpperCase() === this.state.statusFilter);
      }

      // Side
      const sideFlt = this.$('#fltSide')?.value || "ALL";
      if (sideFlt !== "ALL") {
        filtered = filtered.filter(s => (s.side || '').toUpperCase() === sideFlt);
      }

      // Result (TP/SL)
      const resultFlt = this.$('#fltResult')?.value || "ALL";
      if (resultFlt !== "ALL") {
        filtered = filtered.filter(s => {
          const val = (s.validated || s.result || '').toUpperCase();
          if (resultFlt === "TP") return val.includes("TP");
          if (resultFlt === "SL") return val.includes("SL");
          return true;
        });
      }
      return filtered;
    },

    totalPages() {
      const n = this.filteredSignals().length;
      return Math.max(1, Math.ceil(n / this.state.pageSize));
    },

    renderTrades() {
      const body = this.$('#trBody'); if (!body) return;
      const sigs = this.filteredSignals().slice();

      // newest first
      sigs.sort((a, b) => this.parseTs(b.time) - this.parseTs(a.time));

      const start = (this.state.page - 1) * this.state.pageSize;
      const pageRows = sigs.slice(start, start + this.state.pageSize);

      const fmt = (v) => (v == null ? '—' : (typeof v === 'number' ? Number(v).toFixed(2) : v));

      const rows = pageRows.map(s => {
        // ---- Side badge
        const side = (s.side || '').toUpperCase();
        const sideClass = side === "LONG" ? "side-badge long"
                           : side === "SHORT" ? "side-badge short"
                           : "side-badge";
        const sideText  = side === "LONG" ? "LONG"
                           : side === "SHORT" ? "SHORT"
                           : (side || "—");

        // ---- Result (TP/SL) badge
        const resultUpper = (s.validated || s.result || '').toUpperCase();
        let resultClass = "result-badge";
        if (resultUpper.includes("TP")) resultClass += " tp";
        else if (resultUpper.includes("SL")) resultClass += " sl";

        // ---- PnL (+/-)
        const pnl = (s.net_pnl == null) ? '—' : Number(s.net_pnl).toFixed(2);
        const pnlCls = (s.net_pnl == null) ? '' : (s.net_pnl > 0 ? 'pos' : s.net_pnl < 0 ? 'neg' : '');

        // ======= შენი წესები =======
        // TP ყოველთვის მწვანე, SL ყოველთვის წითელი, RR უფეროდ
        const tpCls = (s.tp == null) ? '' : 'pos';
        const slCls = (s.sl == null) ? '' : 'neg';
        const rr    = fmt(s.rrr);
        const rrCls = ''; // უფეროდ

        // ---- Status ტექსტი + „ბოქსის“ ფერი შედეგის მიხედვით
        const statusUpper = (s.status || '').toUpperCase();
        let statusText = s.status ?? '—';
        let statusCls  = "status-box"; // საბაზისო არე

        if (statusUpper === "OPEN") {
          if (side === "LONG")  { statusText += " / LONG";  statusCls += " pos"; }
          if (side === "SHORT") { statusText += " / SHORT"; statusCls += " neg"; }
        } else if (statusUpper === "CLOSED") {
          if (resultUpper.includes("TP")) { statusText += " / TP"; statusCls += " pos"; }
          else if (resultUpper.includes("SL")) { statusText += " / SL"; statusCls += " neg"; }
        }

        // ---- Row
        return `<tr class="trade-row" title="${(s.core_reason||'')}${s.support_reason?(' | '+s.support_reason):''}">
          <td class="nowrap" data-label="Time">${s.time ? new Date(this.parseTs(s.time)).toLocaleString() : '—'}</td>
          <td data-label="Status"><span class="${statusCls}">${statusText}</span></td>
          <td class="num" data-label="Entry">${fmt(s.entry)}</td>
          <td class="num" data-label="Exit">${fmt(s.exit_price)}</td>
          <td class="num ${pnlCls}" data-label="Net PnL">${pnl}</td>
          <td class="num ${rrCls}" data-label="RR">${rr}</td>
          <td class="num ${slCls}" data-label="SL">${fmt(s.sl)}</td>
          <td class="num ${tpCls}" data-label="TP">${fmt(s.tp)}</td>
          <td class="t-ellipsis" data-label="Mode">
            <span class="${sideClass}">${sideText}</span>
            ${resultUpper ? `<span class="${resultClass}">${resultUpper}</span>` : ""}
          </td>
        </tr>`;
      }).join('');

      body.innerHTML = rows;

      // Announce page change politely for screen readers (debounced)
      try {
        const page = this.state.page; const totalPages = this.totalPages();
        if (window._announceTradesTimer) clearTimeout(window._announceTradesTimer);
        window._announceTradesTimer = setTimeout(() => {
          const st = document.getElementById('trades-status');
          if (st) st.textContent = `Page ${page} of ${totalPages}`;
        }, 120);
      } catch {}

      const total = sigs.length;
      this.$('#pageInfo').textContent = `Page ${this.state.page} / ${this.totalPages()} · Records: ${this.shortInt(total)}`;
      this.$('#btnPrev').disabled = (this.state.page <= 1);
      this.$('#btnNext').disabled = (this.state.page >= this.totalPages());
    }
  });
}
