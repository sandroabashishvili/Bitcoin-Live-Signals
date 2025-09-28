// assets/apps/equity-viewer/template.js

import equityViewerStyle from './template-style.js';

export function equityViewerTemplate() {
  return `
    ${equityViewerStyle}
    
    <div class="wrap">
        <div class="panel live-wrap">
          <div class="intro-banner" aria-label="Page introduction">
            <h1 id="live-title">Bitcoin Live Signals</h1>
            <p class="subhead">Real-time trade signals with TP/SL, multi-timeframe view, and transparent performance.</p>
            <div class="chips" aria-label="Key highlights">
              <span class="btn" role="note">AI-powered</span>
              <span class="btn" role="note">For traders and quant teams</span>
              <span class="btn" role="note">Updates every 30 min</span>
            </div>
            <p class="legal">Educational use only. Not financial advice. Trading involves risk; past performance does not guarantee future results.</p>
          </div>
          <div class="snapshot" style="margin-bottom:8px">
            <div class="snap">
              <div class="label">Signal</div>
              <div class="value" id="snapSignal">—</div>
            </div>
            <div class="snap">
              <div class="label">Price</div>
              <div class="value" id="snapPrice">—</div>
            </div>
            <div class="snap">
              <div class="label">Entry</div>
              <div class="value" id="snapEntry">—</div>
            </div>
            <div class="snap">
              <div class="label">TP</div>
              <div class="value" id="snapTP">—</div>
            </div>
            <div class="snap">
              <div class="label">SL</div>
              <div class="value" id="snapSL">—</div>
            </div>
          </div>

          <h3 class="muted" style="margin:12px 0 4px 0; font-size: 18px;">
           Multi-Timeframe Signals 
          </h3>
          <div class="mtf-grid">
            <div class="mtf-card">
              <div class="mtf-hdr">5m <span class="mtf-signal" id="mtf5m_signal" style="margin-left:10px;font-weight:700;font-size:1.1em"></span></div>
              <div class="mtf-rows">
                <div><span>Price</span><b id="mtf5m_price">—</b></div>
                <div><span>RSI</span><b id="mtf5m_rsi">—</b></div>
                <div><span>MACD</span><b id="mtf5m_macd">—</b></div>
                <div><span>ADX</span><b id="mtf5m_adx">—</b></div>
                <div class="kv"><span>EMA 50/200</span><b id="mtf5m_ema">—</b></div>
                <div class="kv"><span>VWAP</span><b id="mtf5m_vwap">—</b></div>
                <div class="kv"><span>Tenkan/Kijun</span><b id="mtf5m_ichi">—</b></div>
                <div><span>ATR</span><b id="mtf5m_atr">—</b></div>
              </div>
            </div>

            <div class="mtf-card">
              <div class="mtf-hdr">30m <span class="mtf-signal" id="mtf30m_signal" style="margin-left:10px;font-weight:700;font-size:1.1em"></span></div>
              <div class="mtf-rows">
                <div><span>Price</span><b id="mtf30m_price">—</b></div>
                <div><span>RSI</span><b id="mtf30m_rsi">—</b></div>
                <div><span>MACD</span><b id="mtf30m_macd">—</b></div>
                <div><span>ADX</span><b id="mtf30m_adx">—</b></div>
                <div class="kv"><span>EMA 50/200</span><b id="mtf30m_ema">—</b></div>
                <div class="kv"><span>VWAP</span><b id="mtf30m_vwap">—</b></div>
                <div class="kv"><span>Tenkan/Kijun</span><b id="mtf30m_ichi">—</b></div>
                <div><span>ATR</span><b id="mtf30m_atr">—</b></div>
              </div>
            </div>

            <div class="mtf-card">
              <div class="mtf-hdr">4h <span class="mtf-signal" id="mtf4h_signal" style="margin-left:10px;font-weight:700;font-size:1.1em"></span></div>
              <div class="mtf-rows">
                <div><span>Price</span><b id="mtf4h_price">—</b></div>
                <div><span>RSI</span><b id="mtf4h_rsi">—</b></div>
                <div><span>MACD</span><b id="mtf4h_macd">—</b></div>
                <div><span>ADX</span><b id="mtf4h_adx">—</b></div>
                <div class="kv"><span>EMA 50/200</span><b id="mtf4h_ema">—</b></div>
                <div class="kv"><span>VWAP</span><b id="mtf4h_vwap">—</b></div>
                <div class="kv"><span>Tenkan/Kijun</span><b id="mtf4h_ichi">—</b></div>
                <div><span>ATR</span><b id="mtf4h_atr">—</b></div>
              </div>
            </div>
          </div>
        </div>

        <section class="panel" aria-labelledby="sec-trades">
          <div class="table-header">
            <h2 id="sec-trades" class="muted">Recent Trades</h2>
            <div class="controls-inline">
              <label> Status
                <select id="fltStatus" aria-label="Filter by status">
                  <option value="ALL">All</option>
                  <option value="OPEN">Open</option>
                  <option value="CLOSED">Closed</option>
                </select>
              </label>
              <label> Side
                <select id="fltSide" aria-label="Filter by side">
                  <option value="ALL">All</option>
                  <option value="LONG">Long</option>
                  <option value="SHORT">Short</option>
                </select>
              </label>
              <label> Result
                <select id="fltResult" aria-label="Filter by result">
                  <option value="ALL">All</option>
                  <option value="TP">TP (Take Profit)</option>
                  <option value="SL">SL (Stop Loss)</option>
                </select>
              </label>
              <label> Page size
                <select id="selPageSize" aria-label="Page size">
                  <option selected>5</option>
                  <option>10</option>
                  <option>25</option>
                  <option>50</option>
                </select>
              </label>
            </div>
          </div>
          <div class="table-wrap" role="region" aria-label="Trades table container">
            <table id="trades-table" class="interactive-table trades" role="table" aria-label="Recent trades table">
              <thead>
                <tr>
                  <th scope="col">Time</th>
                  <th scope="col">Status</th>
                  <th scope="col" class="num">Entry</th>
                  <th scope="col" class="num">Exit</th>
                  <th scope="col" class="num">Net PnL</th>
                  <th scope="col" class="num">RR</th>
                  <th scope="col" class="num">SL</th>
                  <th scope="col" class="num">TP</th>
                  <th scope="col">Mode</th>
                </tr>
              </thead>
              <tbody id="trBody"></tbody>
            </table>
          </div>
          <div class="pager">
            <button class="btn" id="btnPrev" title="Prev" aria-controls="trades-table" aria-label="Previous page — trades table">Prev</button>
            <button class="btn" id="btnNext" title="Next" aria-controls="trades-table" aria-label="Next page — trades table">Next</button>
            <div id="pageInfo">Page 1 / 1</div>
          </div>
          <p id="trades-status" class="sr-only" aria-live="polite" aria-atomic="true"></p>
        </section>


         <!-- მხოლოდ ერთი Equity Chart -->
        <section class="panel" aria-labelledby="sec-chart">
          <h2 id="sec-chart" class="muted"><span id="chartTitle">Capital Δ% from Start</span></h2>
          <div id="chart" class="chart" aria-label="Equity chart"></div>
        </section>


        <section class="panel" aria-labelledby="sec-kpi">
          <h2 id="sec-kpi" class="muted">KPI Overview + Finance</h2>
          <div id="finTotals" class="muted" style="margin:4px 0 8px"></div>
          <div aria-live="polite" aria-atomic="true">
            <div id="kpis" class="grid" style="margin-bottom:8px"></div>
            <div id="finance" class="grid"></div>
          </div>
        </section>

        <!-- ინდიკატორების სექცია დაბრუნებულია! -->
        <section class="panel" aria-labelledby="sec-indicators" id="indSection">
          <h2 id="sec-indicators" class="muted">Indicators Overview</h2>
          <div class="ind-grid">
            <div class="ind-card">
              <div id="indCoreDonut" class="donut" aria-label="Core Indicators Donut"></div>
              <div class="muted" id="indCoreMeta"></div>
            </div>
            <div class="ind-card">
              <div id="indSupportDonut" class="donut" aria-label="Support Indicators Donut"></div>
              <div class="muted" id="indSupportMeta"></div>
            </div>
          </div>
          <div class="ind-tables">
            <div class="ind-shell">
              <table aria-label="Core Indicators" id="tblCore">
                <thead>
                  <tr>
                    <th>Indicator</th>
                    <th class="num">TP</th>
                    <th class="num">SL</th>
                    <th class="num">Δ (TP–SL)</th>
                    <th class="num">Acc%</th>
                  </tr>
                </thead>
                <tbody></tbody>
              </table>
            </div>
            <div class="ind-shell">
              <table aria-label="Support Indicators" id="tblSupport">
                <thead>
                  <tr>
                    <th>Indicator</th>
                    <th class="num">TP</th>
                    <th class="num">SL</th>
                    <th class="num">Δ (TP–SL)</th>
                    <th class="num">Acc%</th>
                  </tr>
                </thead>
                <tbody></tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
  `;
}
