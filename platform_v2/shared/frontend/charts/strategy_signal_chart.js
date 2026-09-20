import { mountChart } from "./common.js";

function parseTimestampText(value) {
  const text = String(value || "").trim();
  const match = text.match(/^(\d{2})\.(\d{2})\.(\d{4}),\s*(\d{2}):(\d{2}):(\d{2})$/);
  if (!match) {
    return Number.NaN;
  }
  const [, dd, mm, yyyy, hh, mi, ss] = match;
  return Date.UTC(
    Number(yyyy),
    Number(mm) - 1,
    Number(dd),
    Number(hh),
    Number(mi),
    Number(ss),
  );
}

function getRows() {
  const rows = Array.isArray(window.__SSH_STRATEGY_SIGNALS__) ? window.__SSH_STRATEGY_SIGNALS__ : [];
  return rows
    .map((row) => {
      const ts = parseTimestampText(row.timestamp_text);
      return {
        ...row,
        score: Number(row.score),
        threshold: Number(row.threshold),
        ts,
      };
    })
    .filter((row) => Number.isFinite(row.score) && Number.isFinite(row.ts))
    .sort((a, b) => a.ts - b.ts);
}

function pointColor(row) {
  if (row.entry_status === "Denied") {
    return "#ef4444";
  }
  if (row.side === "BUY") {
    return "#22c55e";
  }
  return "#fbbf24";
}

function buildOption(E, theme) {
  const rows = getRows();
  if (!rows.length) {
    return {
      animation: false,
      backgroundColor: theme.chartBg,
      title: {
        text: "No strategy signals yet.",
        left: "center",
        top: "middle",
        textStyle: { color: theme.muted, fontSize: 14, fontWeight: 500 },
      },
    };
  }

  const lineData = rows.map((row) => [row.ts, row.score]);
  const thresholdData = rows.map((row) => [row.ts, row.threshold]);

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
      backgroundColor: theme.tooltipBg,
      borderWidth: 0,
      textStyle: { color: theme.text },
      formatter(params) {
        const point = params?.[0];
        if (!point) return "";
        const row = rows[point.dataIndex];
        if (!row) return "";
        const pointTone = pointColor(row);
        return `
          <div style="min-width: 270px; line-height: 1.45;">
            <div style="font-weight: 700; color: ${theme.text}; margin-bottom: 6px;">
              ${row.timestamp_text}
            </div>
            <div>Side: <b style="color:${pointTone};">${row.side}</b></div>
            <div>Score / Threshold: <b>${row.score.toFixed(2)}</b> / <b>${row.threshold.toFixed(2)}</b></div>
            <div>Entry: <b>${row.entry_status}</b></div>
            <div>Failed Gates: <b>${row.failed_gates || "—"}</b></div>
            <div>Reason: <b>${row.denial_reason || "—"}</b></div>
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
    yAxis: {
      type: "value",
      axisLabel: { color: theme.muted },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.10)" } },
    },
    series: [
      {
        type: "line",
        name: "Score",
        data: lineData,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2.2, color: "#7dd3fc" },
      },
      {
        type: "line",
        name: "Threshold",
        data: thresholdData,
        smooth: false,
        showSymbol: false,
        lineStyle: { width: 1.2, color: "#fbbf24", type: "dashed" },
      },
      {
        type: "scatter",
        name: "Signals",
        data: rows.map((row) => ({
          value: [row.ts, row.score],
          itemStyle: { color: pointColor(row) },
        })),
        symbolSize: 10,
        z: 4,
      },
    ],
  };
}

mountChart("strategy-signal-chart", buildOption);
