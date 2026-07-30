import { buildGradient, mountChart } from "./common.js";

function buildSeries() {
  const rows = Array.isArray(window.__ORDERBOOK_ROWS__) ? window.__ORDERBOOK_ROWS__ : [];
  if (!rows.length) {
    return { rows: [], delta: [], cumulative: [] };
  }

  let cumulative = 0;
  const delta = [];
  const cumulativeSeries = [];
  const positiveArea = [];
  const negativeArea = [];
  const enrichedRows = [];

  rows
    .map((row) => {
      const buyers = Number(row.buyers);
      const sellers = Number(row.sellers);
      const ts = Date.parse(`${String(row.timestamp_text).replace(" ", "T")}Z`);
      if (!Number.isFinite(buyers) || !Number.isFinite(sellers) || !Number.isFinite(ts)) {
        return null;
      }
      return { ...row, ts, rawDelta: buyers - sellers };
    })
    .filter(Boolean)
    .sort((a, b) => a.ts - b.ts)
    .forEach((row) => {
      cumulative += row.rawDelta;
      delta.push([row.ts, Number(row.rawDelta.toFixed(4))]);
      const cumulativeValue = Number(cumulative.toFixed(4));
      cumulativeSeries.push([row.ts, cumulativeValue]);
      positiveArea.push([row.ts, cumulativeValue > 0 ? cumulativeValue : null]);
      negativeArea.push([row.ts, cumulativeValue < 0 ? cumulativeValue : null]);
      enrichedRows.push({
        ...row,
        cumulative_delta_live: cumulativeValue,
      });
    });

  return { rows: enrichedRows, delta, cumulative: cumulativeSeries, positiveArea, negativeArea };
}

function buildOption(E, theme) {
  const series = buildSeries();
  if (!series.delta.length) {
    return {
      animation: false,
      backgroundColor: theme.chartBg,
      title: {
        text: "No orderflow history yet.",
        left: "center",
        top: "middle",
        textStyle: { color: theme.muted, fontSize: 14, fontWeight: 500 },
      },
    };
  }

  const isMobile = window.matchMedia("(max-width: 640px)").matches;
  const tooltipMinWidth = isMobile ? 190 : 260;
  const tooltipFontSize = isMobile ? 12 : 13;

  return {
    animationDuration: 500,
    backgroundColor: theme.chartBg,
    grid: { left: 54, right: 24, top: 28, bottom: 42 },
    legend: {
      top: 0,
      right: 8,
      textStyle: { color: theme.muted },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      confine: true,
      appendToBody: false,
      backgroundColor: theme.tooltipBg,
      borderWidth: 0,
      textStyle: { color: theme.text, fontSize: tooltipFontSize },
      extraCssText: "max-width: 92vw; z-index: 10000; white-space: normal;",
      position(pos, params, dom, rect, size) {
        if (!isMobile) return null;
        const [x, y] = pos;
        const boxWidth = dom?.offsetWidth || tooltipMinWidth;
        const boxHeight = dom?.offsetHeight || 120;
        const viewWidth = size?.viewSize?.[0] || window.innerWidth;
        const viewHeight = size?.viewSize?.[1] || window.innerHeight;
        const left = Math.max(8, Math.min(x - boxWidth / 2, viewWidth - boxWidth - 8));
        let top = y - boxHeight - 12;
        if (top < 8) {
          top = Math.min(y + 12, viewHeight - boxHeight - 8);
        }
        return [left, Math.max(8, top)];
      },
      formatter(params) {
        const point = params?.[0];
        if (!point) return "";
        const row = series.rows[point.dataIndex];
        if (!row) return "";
        const deltaColor = Number(row.rawDelta) >= 0 ? "#22c55e" : "#ef4444";
        const classColor = row.momentum_classification === "bullish"
          ? "#22c55e"
          : row.momentum_classification === "bearish"
            ? "#ef4444"
            : "#94a3b8";
        return `
          <div style="min-width: ${tooltipMinWidth}px; line-height: 1.45;">
            <div style="font-weight: 700; color: #f8fafc; margin-bottom: 6px;">
              ${row.timestamp_text}
            </div>
            <div>Buy / Sell: <b>${row.buyers}</b> / <b>${row.sellers}</b></div>
            <div>Net Δ: <b style="color:${deltaColor};">${Number(row.rawDelta).toFixed(2)}</b></div>
            <div>Cumulative Δ: <b>${Number(row.cumulative_delta_live).toFixed(2)}</b></div>
            <div>Class: <b style="color:${classColor};">${row.momentum_classification}</b></div>
            <div>Imbalance: <b>${row.imbalance}</b> · Dominance: <b>${row.dominance_ratio}</b></div>
            <div>Trades: <b>${row.period_count}</b> · Source: <b>${row.source}</b></div>
          </div>
        `;
      },
    },
    xAxis: {
      type: "time",
      axisLabel: {
        color: theme.muted,
        formatter(value) {
          const d = new Date(value);
          return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}\n${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
        },
      },
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.14)" } },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: "value",
        axisLabel: { color: theme.muted },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.10)", opacity: 1 } },
      },
    ],
    series: [
      {
        type: "bar",
        name: "Net Δ",
        data: series.delta,
        itemStyle: {
          color(params) {
            return Number(params.value[1]) >= 0 ? theme.green : theme.red;
          },
          borderRadius(params) {
            return Number(params.value[1]) >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4];
          },
        },
        barMaxWidth: 16,
      },
      {
        type: "line",
        name: "Cumulative Δ",
        data: series.cumulative,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.2, color: "#7dd3fc" },
        areaStyle: { opacity: 0 },
      },
      {
        type: "line",
        name: "Cumulative Δ +",
        data: series.positiveArea,
        showSymbol: false,
        smooth: true,
        connectNulls: true,
        lineStyle: { opacity: 0 },
        areaStyle: { color: theme.green, opacity: 0.16 },
        tooltip: { show: false },
        emphasis: { disabled: true },
        z: 1,
      },
      {
        type: "line",
        name: "Cumulative Δ -",
        data: series.negativeArea,
        showSymbol: false,
        smooth: true,
        connectNulls: true,
        lineStyle: { opacity: 0 },
        areaStyle: { color: theme.red, opacity: 0.16 },
        tooltip: { show: false },
        emphasis: { disabled: true },
        z: 1,
      },
    ],
  };
}

mountChart("orderflow-delta-chart", buildOption);
