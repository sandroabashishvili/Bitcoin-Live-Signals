import { buildGradient, mountChart } from "./common.js";

function formatDateTime(value) {
  if (value == null || value === "") {
    return "—";
  }
  const raw = String(value).trim();
  let ts = Number.NaN;
  if (/^\d+$/.test(raw)) {
    ts = Number(raw);
    if (raw.length <= 10) {
      ts *= 1000;
    }
  } else {
    ts = Date.parse(raw.replace(" ", "T") + "Z");
  }
  if (!Number.isFinite(ts)) {
    return raw;
  }
  return new Date(ts).toLocaleString("en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).replace(",", "");
}

function getRows() {
  const rows = Array.isArray(window.__SSH_PORTFOLIO_CLOSED__) ? window.__SSH_PORTFOLIO_CLOSED__ : [];
  return rows
    .map((row, index) => {
      const net = Number(row.net_pnl);
      const closedAt = row.closed_at || row.opened_at || `Trade ${index + 1}`;
      const ts = /^\d+$/.test(String(closedAt).trim())
        ? Number(String(closedAt).trim())
        : Date.parse(String(closedAt).replace(" ", "T") + "Z");
      return {
        index: index + 1,
        label: `T${index + 1}`,
        net,
        closedAt: formatDateTime(closedAt),
        openedAt: formatDateTime(row.opened_at),
        symbol: row.symbol || "—",
        side: row.side || "—",
        exitReason: row.exit_reason || "—",
        wasForceClosed: Boolean(row.was_force_closed),
        entryPrice: row.entry_price || "—",
        exitPrice: row.exit_price || "—",
        rrRatio: row.rr_ratio || "—",
        duration: row.duration || "—",
        netPct: row.net_pct || "—",
        ts: Number.isFinite(ts) ? ts : index,
      };
    })
    .filter((row) => Number.isFinite(row.net))
    .sort((a, b) => a.ts - b.ts);
}

function buildPerTradeOption(E, theme) {
  const rows = getRows();
  const isMobile = window.matchMedia("(max-width: 640px)").matches;
  if (!rows.length) {
    return {
      animation: false,
      backgroundColor: theme.chartBg,
      title: {
        text: "No closed trades yet.",
        left: "center",
        top: "middle",
        textStyle: { color: theme.muted, fontSize: 14, fontWeight: 500 },
      },
    };
  }

  return {
    animationDuration: 500,
    backgroundColor: theme.chartBg,
    grid: isMobile ? { left: 42, right: 12, top: 18, bottom: 34 } : { left: 54, right: 20, top: 22, bottom: 42 },
    tooltip: {
      trigger: "axis",
      appendToBody: !isMobile,
      confine: isMobile,
      axisPointer: {
        type: "shadow",
        shadowStyle: {
          color: "rgba(255,255,255,0.015)",
        },
      },
      backgroundColor: theme.tooltipBg,
      borderColor: theme.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: theme.tooltipText },
      extraCssText: [
        "z-index: 9999",
        "border-radius: 12px",
        "box-shadow: 0 10px 28px rgba(0,0,0,0.22)",
      ].join(";"),
      position(pos, params, dom, rect, size) {
        const [x, y] = pos;
        const margin = isMobile ? 10 : 14;
        const boxWidth = dom?.offsetWidth || (isMobile ? 164 : 260);
        const boxHeight = dom?.offsetHeight || (isMobile ? 118 : 136);
        const viewWidth = size?.viewSize?.[0] || window.innerWidth;
        const viewHeight = size?.viewSize?.[1] || window.innerHeight;
        const left = Math.max(margin, Math.min(x + (isMobile ? 4 : 12), viewWidth - boxWidth - margin));
        let top = y - boxHeight - 14;
        if (top < margin) {
          top = Math.min(y + 14, viewHeight - boxHeight - margin);
        }
        return [left, Math.max(margin, top)];
      },
      formatter(params) {
        const point = params?.[0];
        if (!point) return "";
        const row = rows[point.dataIndex];
        const net = Number(row.net).toFixed(2);
        const reason = row.wasForceClosed ? `${row.exitReason} · force` : row.exitReason;
        const pnlColor = row.net >= 0 ? theme.green : theme.red;
        const boxWidth = isMobile ? 164 : 260;
        const titleSize = isMobile ? 11 : 13;
        const bodySize = isMobile ? 10 : 12;
        return `
          <div style="width:${boxWidth}px; line-height:1.34; color:${theme.tooltipText}; font-size:${bodySize}px;">
            <div style="font-weight:700; color:${theme.tooltipTitle}; margin-bottom:4px; font-size:${titleSize}px;">
              ${row.symbol} · ${row.side} · ${row.label}
            </div>
            <div style="margin-bottom:1px;">Result: <b style="color:${theme.tooltipTitle};">${reason}</b></div>
            <div style="margin-bottom:1px;">Opened: <b style="color:${theme.tooltipTitle};">${row.openedAt}</b></div>
            <div style="margin-bottom:1px;">Closed: <b style="color:${theme.tooltipTitle};">${row.closedAt}</b></div>
            <div style="margin-bottom:1px;">Entry / Exit: <b style="color:${theme.tooltipTitle};">${row.entryPrice}</b> → <b style="color:${theme.tooltipTitle};">${row.exitPrice}</b></div>
            <div>Duration: <b style="color:${theme.tooltipTitle};">${row.duration}</b> · R:R <b style="color:${theme.tooltipTitle};">${row.rrRatio}</b></div>
            <div style="margin-top: 4px;">Net PnL: <b style="color:${pnlColor};">$${net}</b> <b style="color:${pnlColor};">(${row.netPct})</b></div>
          </div>
        `;
      },
    },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.label),
      axisLabel: { color: theme.muted, fontSize: isMobile ? 10 : 11 },
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.14)" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: theme.muted, fontSize: isMobile ? 10 : 11 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.10)" } },
    },
    series: [
      {
        type: "bar",
        data: rows.map((row) => row.net),
        barMaxWidth: isMobile ? 16 : 22,
        itemStyle: {
          color(params) {
            return Number(params.value) >= 0 ? theme.green : theme.red;
          },
          borderRadius(params) {
            return Number(params.value) >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4];
          },
        },
      },
    ],
  };
}

mountChart("portfolio-pnl-chart", buildPerTradeOption);
