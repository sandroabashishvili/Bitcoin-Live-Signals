// assets/apps/equity-viewer/template-style.js
export default `
<style>
  :host{ color: var(--ink); overflow-anchor: none; display:block }
  .wrap { max-width: 1320px; margin: 0 auto; padding: 18px; display: grid; gap: 12px; }
  h1, h2 { margin: 0; }
  h2 { font-size: 20px; }

  /* პანელები — მკაფიო კონტური და სუფთა ფონი */
  .panel {
    background: var(--card, #fff);
    border: 1px solid var(--line, #e6e6e9);
    border-radius: 14px;
    padding: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,.05);
    transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
  }
  .panel:hover { box-shadow: 0 6px 14px rgba(0,0,0,.08); transform: translateY(-1px); }

  @media (max-width:700px){ .mtf-grid{ grid-template-columns: 1fr; } }
  .kpi b { font-size: 18px; }

  /* ტექსტური შეღებვა ინდივიდუალური ელემენტებისთვის (მაგ. მაჩვენებლები) */
  .pos { color: var(--buy, #16a34a); font-weight: 700; }
  .neg { color: var(--sell, #dc2626); font-weight: 700; }
  .muted { color: #64748b; }

  /* მხოლოდ BUY/SELL სიტყვის შესაღებად (სიგნალში) */
  .sig-word { font-variant-numeric: tabular-nums; }
  .sig-word.pos { color: var(--buy, #16a34a); font-weight: 700; }
  .sig-word.neg { color: var(--sell, #dc2626); font-weight: 700; }

  /* კონტრასტული კონტროლები */
  .switcher { display:flex; gap:10px; justify-content:center; flex-wrap:wrap; }
  .switcher button {
    background: color-mix(in oklab, var(--card,#fff) 92%, transparent);
    border:1px solid var(--line, #d1d5db);
    color:inherit; padding:8px 14px; border-radius:10px; cursor:pointer;
    transition: box-shadow .18s ease, transform .18s ease, background-color .18s ease, border-color .18s ease;
  }
  .switcher button:hover { box-shadow: 0 3px 10px rgba(0,0,0,.08); transform: translateY(-1px);
    background: color-mix(in oklab, var(--card,#fff) 88%, transparent); }
  .switcher button:focus-visible { outline: 2px solid var(--line, #94a3b8); outline-offset: 2px; }
  .switcher button.active, .switcher button[aria-pressed="true"] {
    background: color-mix(in oklab, var(--card,#fff) 84%, transparent);
    border-color: color-mix(in oklab, var(--line,#e6e6e9) 70%, var(--ink,#222));
  }

  .controls { display:flex; gap:8px; align-items:center; justify-content:center; flex-wrap:wrap; }

  /* გრაფიკს მივცემ სუფთა ფონს, რომ არ “გაიქრეს” */
  .chart { height: 440px; border-radius: 12px; background: var(--card,#fff); }

  /* KPI / Metrics ბლოკები — მკაფიო განსხვავება */
  .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:12px; }
  .kpi, .metric {
    padding:10px; border-radius:12px;
    background: color-mix(in oklab, var(--card,#fff) 94%, transparent);
    border:1px solid var(--line,#e6e6e9);
    transition: box-shadow .18s ease, transform .18s ease, background-color .18s ease, border-color .18s ease;
  }
  .metric:hover, .kpi:hover { box-shadow:0 4px 12px rgba(0,0,0,.08); transform: translateY(-1px); }
  .kpi:focus-within, .metric:focus-within { box-shadow:0 0 0 2px color-mix(in oklab, var(--line,#94a3b8) 100%, transparent) inset; }
  .kpi b { font-size: 18px; }
 
  /* ===== Trades Table ===== */
  .table-header { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; }
  .controls-inline { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  select {
    background: color-mix(in oklab, var(--card,#fff) 92%, transparent);
    border:1px solid var(--line,#e6e6e9); padding:8px 12px; border-radius:10px;
  }
  .table-wrap{
    max-height:60vh; overflow:auto;
    border:1px solid var(--line,#e6e6e9); border-radius:10px; background: var(--card,#fff)
  }
  table { width:100%; border-collapse:separate; border-spacing:0; }
  thead th {
    text-align:left;
    background: color-mix(in oklab, var(--card,#fff) 90%, transparent);
    font-weight:600; font-size:13px; padding:10px; border-bottom:1px solid var(--line,#00000020);
    position:sticky; top:0; z-index:2;
    backdrop-filter: saturate(120%) blur(4px);
  }
  tbody td {
    padding:10px; border-bottom:1px solid var(--line,#00000012); font-size:13px; transition: background-color .18s ease;
    background: var(--card,#fff);
  }
  .interactive-table.trades{ table-layout: fixed }
  .interactive-table.trades thead th:nth-child(1),
  .interactive-table.trades tbody td:nth-child(1){ width: 20ch; white-space: nowrap }
  .interactive-table.trades thead th:nth-child(2),
  .interactive-table.trades tbody td:nth-child(2){ width: 10ch; white-space: nowrap }
  .interactive-table.trades thead th:nth-child(6),
  .interactive-table.trades tbody td:nth-child(6){ width: 7ch; white-space: nowrap; text-align: right }
  .interactive-table.trades thead th:nth-child(9),
  .interactive-table.trades tbody td:nth-child(9){ width: 12ch; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
  .interactive-table tbody tr:nth-child(even){
    background: color-mix(in oklab, var(--card,#fff) 96%, transparent)
  }
  .interactive-table tbody tr:hover td{
    background: color-mix(in oklab, var(--card,#fff) 92%, transparent)
  }
  .num { text-align:right; font-variant-numeric: tabular-nums; }
  .nowrap { white-space:nowrap; }
  .pager { display:flex; gap:8px; align-items:center; justify-content:flex-end; margin-top:8px; color:var(--muted,#64748b); font-size:13px; }
  .t-ellipsis{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
  .sr-only{ position:absolute !important; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,1px,1px); white-space:nowrap; border:0 }

  /* ===== Live & MTF ===== */
  .live-wrap {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 10px;
    box-shadow: 0 6px 16px rgba(0,0,0,.06);
  }

  .intro-banner { text-align:center; margin-bottom:10px }
  .intro-banner h1 {
    font-size: calc(var(--fs-title, 24px) + 8px);
    line-height:1.15;
    margin:0 0 6px 0;
  }
  .intro-banner .subhead { color: var(--muted, #64748b); margin:0 0 8px 0 }
  .chips { display:flex; gap:8px; justify-content:center; flex-wrap:wrap; margin:8px 0 }
  .legal { color: var(--muted, #64748b); font-size:12px; margin:6px auto 0; max-width:920px }

  /* Snapshots */
  .snapshot {
    display:grid;
    grid-template-columns: repeat(auto-fit, minmax(140px,1fr));
    gap:8px;
  }
  .snap {
    background: color-mix(in oklab, var(--card,#fff) 94%, transparent);
    border:1px solid var(--line,#e6e6e9);
    border-radius:10px;
    padding:8px;
    text-align:center;
    transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
  }
  .snap:hover { box-shadow:0 4px 12px rgba(0,0,0,.08); transform: translateY(-1px); }
  .snap .label { color: var(--muted,#888fa5); font-weight:600 }
  .snap .value { font-weight:800 }

  /* --- Snap ბოქსების კანტის ფერი სიგნალით --- */
  .snap.pos { border-color: var(--buy,#16a34a); box-shadow: 0 0 0 1px color-mix(in oklab, var(--buy) 28%, transparent); }
  .snap.neg { border-color: var(--sell,#dc2626); box-shadow: 0 0 0 1px color-mix(in oklab, var(--sell) 28%, transparent); }
  .snap.neu { border-color: var(--line,#e6e6e9); box-shadow: none; }

  
  /* კონტეინერზე დადებული .pos/.neg ტექსტს ნეიტრალიზაცია — მხოლოდ კანტი იცვლება */
  .snap.pos, .snap.neg { color: inherit; }

  /* Multi-timeframe cards */
  .mtf-grid {
    display:grid;
    grid-template-columns: repeat(3, 1fr);
    gap:10px;
    margin-top:8px;
  }
  .mtf-card {
    background: color-mix(in oklab, var(--card,#fff) 94%, transparent);
    border:1px solid var(--line,#e6e6e9);
    border-radius:12px;
    padding:8px;
    transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
  }
  .mtf-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,.08);
    transform: translateY(-1px);
  }

  .mtf-hdr { font-weight:700; margin-bottom:6px }
  .mtf-rows > div { display:flex; align-items:center; justify-content:space-between; padding:2px 0 }
  .kv { display:flex; justify-content:space-between; gap:8px }

  /* --- MTF ბარათების კანტის ფერი სიგნალით --- */
  .mtf-card { border-width:2px; } /* რომ კანტი აშკარად გამოჩნდეს */
  .mtf-card.pos  { border-color: var(--buy,#16a34a);  box-shadow: 0 0 0 1px color-mix(in oklab, var(--buy) 24%, transparent); }
  .mtf-card.neg  { border-color: var(--sell,#dc2626); box-shadow: 0 0 0 1px color-mix(in oklab, var(--sell) 24%, transparent); }
  .mtf-card.neu  { border-color: var(--line,#e6e6e9); box-shadow: none; }
  /* კონტეინერზე დადებული .pos/.neg ტექსტს ნეიტრალიზაცია — მხოლოდ კანტი იცვლება */
  .mtf-card.pos, .mtf-card.neg { color: inherit; }

  /* თავსებადობა ძველ მდგომარეობებთან (თუ სადმე რჩება) */
  .mtf-card.is-buy  { border-color: var(--buy,#16a34a); }
  .mtf-card.is-sell { border-color: var(--sell,#dc2626); }
  .mtf-card.is-none { border-color: var(--line,#e6e6e9); }

  /* ===== Indicators ===== */
  .ind-grid{ display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:8px }
  @media (max-width: 900px){ .ind-grid{ grid-template-columns:1fr } }
  .ind-card{
    background: color-mix(in oklab, var(--card,#fff) 94%, transparent);
    border:1px solid var(--line,#e6e6e9);
    border-radius:12px; padding:8px;
    transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
  }
  .ind-card:hover{ box-shadow:0 4px 12px rgba(0,0,0,.08); transform: translateY(-1px); }
  .donut{ height: 160px }
  .ind-tables{ display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:12px }
  @media (max-width: 900px){ .ind-tables{ grid-template-columns:1fr } }
  .ind-shell{ overflow:auto; border-radius:10px; transition: box-shadow .18s ease, transform .18s ease; }
  .ind-shell:hover{ box-shadow:0 4px 12px rgba(0,0,0,.08); transform: translateY(-1px); }

  .view-toggle{ font-size:12px; margin-left:8px }
  .view-toggle button{
    background: color-mix(in oklab, var(--card,#fff) 92%, transparent);
    border:1px solid var(--line,#e6e6e9);
    padding:4px 8px; border-radius:8px; margin-left:6px; cursor:pointer;
    transition: box-shadow .18s ease, transform .18s ease, background-color .18s ease, border-color .18s ease
  }
  .view-toggle button:hover{ background: color-mix(in oklab, var(--card,#fff) 88%, transparent); box-shadow:0 3px 10px rgba(0,0,0,.08); transform: translateY(-1px) }
  .view-toggle button.active{
    background: color-mix(in oklab, var(--card,#fff) 84%, transparent);
    border-color: color-mix(in oklab, var(--line,#e6e6e9) 70%, var(--ink,#222));
  }

  .btn{
    background: color-mix(in oklab, var(--card,#fff) 92%, transparent);
    border:1px solid var(--line,#e6e6e9); padding:6px 10px; border-radius:8px; cursor:pointer;
    transition: box-shadow .18s ease, transform .18s ease, background-color .18s ease, border-color .18s ease
  }
  .btn:hover{ background: color-mix(in oklab, var(--card,#fff) 88%, transparent); box-shadow:0 3px 10px rgba(0,0,0,.08); transform: translateY(-1px) }

  /* Focus-visible consistency in shadow DOM */
  :host(:focus-visible), :host *:focus-visible{ outline:2px solid color-mix(in oklab, var(--line,#94a3b8) 100%, transparent); outline-offset: 2px; border-radius:8px }

  /* Mobile tweaks */
  @media (max-width:640px){ .switcher{ flex-wrap: wrap; gap: 8px } }

  /* Opt-in stacked-cards for very small screens */
  @media (max-width:400px){
    .stacked-cards .interactive-table thead{ display:none }
    .stacked-cards .interactive-table,
    .stacked-cards .interactive-table tbody,
    .stacked-cards .interactive-table tr,
    .stacked-cards .interactive-table td{ display:block; width:100% }
    .stacked-cards .interactive-table tr{
      margin:12px 0; border:1px solid var(--line,#e6e6e9); border-radius:12px; padding:10px; background: var(--card,#fff)
    }
    .stacked-cards .interactive-table td{ border:none; padding:6px 0 }
    .stacked-cards .interactive-table td::before{ content: attr(data-label); display:block; font-size:.8rem; opacity:.7; margin-bottom:2px }
  }

#live-title.live-animate {
  animation: subtlePulse 1.08s cubic-bezier(.39,.15,.44,1) 1;
}
@keyframes subtlePulse {
  0%   { opacity:1; transform:scale(1);}
  14%  { opacity:0.83; transform:scale(1.04);}
  28%  { opacity:1; transform:scale(1.04);}
  45%  { opacity:1; transform:scale(1);}
  100% { opacity:1; transform:scale(1);}
}

  /* სურვილისამებრ: მაღალი კონტრასტი */
  :host([data-contrast="high"]) .mtf-card,
  :host([data-contrast="high"]) .kpi,
  :host([data-contrast="high"]) .metric,
  :host([data-contrast="high"]) .snap,
  :host([data-contrast="high"]) .ind-card{
    border-color: color-mix(in oklab, var(--ink,#222) 35%, var(--line,#e6e6e9));
    background: color-mix(in oklab, var(--card,#fff) 90%, transparent);
  }

  /* ჰოვერ ეფექტი: მთელი row-ზე */
.interactive-table tbody tr.trade-row:hover td {
  background: color-mix(in oklab, var(--buy,#e5f9ee) 11%, var(--card,#fff) 89%);
  /* ან უფრო მკვეთრი */
  /* background: #e5f9ee; */
}

/* ბეჯები: */
.side-badge {
  display: inline-block;
  padding: 2px 8px;
  margin-right: 2px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
  background: color-mix(in oklab, var(--card,#fff) 92%, transparent);
  border: 1.5px solid #d1d5db;
}
.side-badge.long  { color: var(--buy,#16a34a); border-color: var(--buy,#16a34a); }
.side-badge.short { color: var(--sell,#dc2626); border-color: var(--sell,#dc2626); }

.result-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
  margin-left: 3px;
  background: #f3f5f7;
  color: #64748b;
  border: 1.2px solid #e6e6e9;
}
.result-badge.tp { color: var(--buy,#16a34a); border-color: var(--buy,#16a34a);}
.result-badge.sl { color: var(--sell,#dc2626); border-color: var(--sell,#dc2626);}

/* Status */
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
  background: #f3f5f7;
  color: #64748b;
  border: 1.2px solid #e6e6e9;
}
.status-badge.open   { color: var(--buy,#16a34a); border-color: var(--buy,#16a34a);}
.status-badge.closed { color: var(--muted,#64748b);}

</style>
`;