// assets/apps/equity-viewer/live-mixin.js
// Live signal snapshot and multi-timeframe (MTF) rendering
export function applyLiveMixin(Cls){
  Object.assign(Cls.prototype, {
    // Prefer global SSHTicker so multiple apps don't spawn parallel intervals
    startPolling(){
      if (this._unsubscribeTicker || this._pollTimer) return;
      const tickFn = async () => {
        try { await this.autoLoad(); } catch(e){ console.warn('[EquityViewer] poll failed', e); }
      };
      if (window.SSHTicker && typeof window.SSHTicker.subscribe === 'function'){
        this._unsubscribeTicker = window.SSHTicker.subscribe(tickFn);
      } else {
        // fallback local interval if global ticker not present
        const TICK = 10000;
        this._pollTimer = setInterval(() => { if (!document.hidden) tickFn(); }, TICK);
      }
    },
    stopPolling(){
      if (this._unsubscribeTicker){ try { this._unsubscribeTicker(); } catch{} this._unsubscribeTicker = null; }
      if (this._pollTimer){ clearInterval(this._pollTimer); this._pollTimer = null; }
    },

    normalizeBTC(btc){ return Array.isArray(btc) ? btc : (btc? [btc] : []); },
    money(v){ const x = Math.abs(v) < 1e-10 ? 0 : v; return this.n2.format(x); },

    // ---- helper: build markup so only BUY/SELL word is colored
    _signalMarkup(sigUpper){
      if (!sigUpper) return { html: 'NO SIGNAL', aria: 'NO SIGNAL' };
      const s = String(sigUpper).toUpperCase();
      if (s.includes('BUY'))  return { html: 'SIGNAL <span class="sig-word pos">BUY</span>',  aria: 'SIGNAL BUY'  };
      if (s.includes('SELL')) return { html: 'SIGNAL <span class="sig-word neg">SELL</span>', aria: 'SIGNAL SELL' };
      return { html: 'NO SIGNAL', aria: 'NO SIGNAL' };
    },

    renderLiveSignal(btcArr){
      const arr = this.normalizeBTC(btcArr);
      const last = arr.length ? arr[arr.length-1] : null;

      // setter: no global pos/neg on container; supports {html, aria}
      const setText = (id, value) => {
        const el = this.$('#'+id); if (!el) return;
        el.classList.remove('pos','neg','neu');
        if (value == null) { el.textContent = '—'; return; }
        if (value && typeof value === 'object' && 'html' in value) {
          el.innerHTML = value.html;
          if (value.aria) el.setAttribute('aria-label', value.aria);
          return;
        }
        el.textContent = value;
      };

      // ბოქსების სია (ყველა snap)
      const snapIds = ['snapSignal','snapPrice','snapEntry','snapTP','snapSL'];

      // ყოველთვის გაასუფთავე ყველა ბოქსი (კანტი და ტექსტიც)
      snapIds.forEach(id => {
        const box = this.$('#'+id)?.closest('.snap');
        if (box) box.classList.remove('pos','neg');
        this.$('#'+id)?.classList.remove('pos','neg');
      });

      if (!last) {
        setText('snapSignal', { html:'NO SIGNAL', aria:'NO SIGNAL' });
        setText('snapPrice','—'); setText('snapEntry','—'); setText('snapTP','—'); setText('snapSL','—');
        return;
      }

      const sig = (last.signal||'').toUpperCase();
      const mark = this._signalMarkup(sig);
      setText('snapSignal', mark);

      setText('snapPrice', last.price!=null ? this.money(+last.price) : '—');

      if (sig==='BUY' || sig==='SELL'){
        const entry = (last.entry!=null)? last.entry : last.price;
        setText('snapEntry', entry!=null? this.money(+entry): '—');
        setText('snapTP', last.tp!=null? this.money(+last.tp): '—');
        setText('snapSL', last.sl!=null? this.money(+last.sl): '—');

        // ფერები და კანტები: ყველა ბოქსს BUY-ზე მწვანე, SELL-ზე წითელი
        const className = sig === 'BUY' ? 'pos' : 'neg';
        snapIds.forEach(id => {
          const box = this.$('#'+id)?.closest('.snap');
          if (box) box.classList.add(className);
          this.$('#'+id)?.classList.add(className);
        });

      } else {
        setText('snapEntry','—'); setText('snapTP','—'); setText('snapSL','—');
        // ყველა ბოქსი რჩება უფეროდ (ზემოთ გაასუფთავე)
      }
    },

    renderMTF(btcArr) {
      const arr = this.normalizeBTC(btcArr);
      const last = arr.length ? arr[arr.length-1] : null;
      if (!last) return;
      const snaps = last?.multi_tf_context?.snapshots || {};

      // 1) headers: color only BUY/SELL word (no pos/neg on the container)
      const setSignal = (id, sig) => {
        const el = this.$('#'+id);
        if (!el) return;
        const s = sig ? String(sig).toUpperCase() : '';
        const { html, aria } = this._signalMarkup(
          s.includes('BUY') ? 'BUY' : s.includes('SELL') ? 'SELL' : ''
        );
        el.classList.remove('pos','neg','neu');
        el.innerHTML = html;
        el.setAttribute('aria-label', aria);
      };

      setSignal('mtf5m_signal',   snaps['5m']   && snaps['5m'].signal);
      setSignal('mtf30m_signal',  snaps['30m']  && snaps['30m'].signal);
      setSignal('mtf4h_signal',   snaps['4h']   && snaps['4h'].signal);

      // 2) indicators
      const tfList = [ ['5m', 'mtf5m'], ['30m', 'mtf30m'], ['4h', 'mtf4h'] ];
      const colorize = (id, val, positiveHigh=true, thresholds=null) => {
        const el = this.$('#'+id); if (!el) return;
        if (val == null || !isFinite(val)) {
          el.textContent = '—';
          el.classList.remove('pos','neg','neu');
          return;
        }
        el.textContent = this.n2.format(val);
        el.classList.remove('pos','neg','neu');
        if (thresholds && thresholds.type === 'rsi') {
          if (val >= 55) el.classList.add('pos');
          else if (val <= 45) el.classList.add('neg');
          else el.classList.add('neu');
        } else if (thresholds && thresholds.type === 'adx') {
          if (val >= 25) el.classList.add('pos');
          else el.classList.add('neu');
        } else {
          if (positiveHigh) { el.classList.add(val >= 0 ? 'pos' : 'neg'); }
          else { el.classList.add(val >= 50 ? 'pos' : 'neg'); }
        }
      };

      for (const [key, prefix] of tfList) {
        const s = snaps[key] || last[`tf${key}`] || {};
        this.$('#'+prefix+'_price')?.replaceChildren(document.createTextNode(s.price != null ? this.money(+s.price) : '—'));
        colorize(prefix+'_rsi', s.rsi, false, {type:'rsi'});
        colorize(prefix+'_macd', s.macd, true);
        colorize(prefix+'_adx', s.adx, true, {type:'adx'});
        this.$('#'+prefix+'_vwap')?.replaceChildren(document.createTextNode(s.vwap != null ? this.money(+s.vwap) : '—'));
        const ema = (s.ema50 != null && s.ema200 != null) ? `${this.money(+s.ema50)} / ${this.money(+s.ema200)}` : '—';
        this.$('#'+prefix+'_ema')?.replaceChildren(document.createTextNode(ema));
        const ichi = (s.tenkan != null && s.kijun != null) ? `${this.money(+s.tenkan)} / ${this.money(+s.kijun)}` : '—';
        this.$('#'+prefix+'_ichi')?.replaceChildren(document.createTextNode(ichi));
        this.$('#'+prefix+'_atr')?.replaceChildren(document.createTextNode(s.atr != null ? this.money(+s.atr) : '—'));
      }
    }
  }); 
}
