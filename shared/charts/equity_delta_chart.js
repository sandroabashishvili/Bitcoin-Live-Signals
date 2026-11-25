import { mountChart } from "./common.js";

function buildSeries() {
  const rows = window.__SSH_OVERVIEW_EQUITY__?.rows || [];
  return rows.map((row) => ({ value: row.chart_point }));
}

function niceSymmetricPercentBound(maxAbs) {
  const padded = Math.max(maxAbs * 1.15, 0.5);
  const magnitude = Math.pow(10, Math.floor(Math.log10(padded)));
  const normalized = padded / magnitude;
  const step =
    normalized <= 1 ? 1 :
    normalized <= 1.2 ? 1.2 :
    normalized <= 1.5 ? 1.5 :
    normalized <= 2 ? 2 :
    normalized <= 2.5 ? 2.5 :
    normalized <= 3 ? 3 :
    normalized <= 4 ? 4 :
    normalized <= 5 ? 5 :
    normalized <= 6 ? 6 :
    normalized <= 8 ? 8 : 10;
  return Number((step * magnitude).toPrecision(6));
}

function formatAxisDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function formatUtcDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return (
    date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "UTC",
    }) + " UTC"
  );
}

function formatUsd(value, signed = false) {
  const num = Number(value);
  const absText = Math.abs(num).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (signed) {
    return `${num >= 0 ? "+" : "-"}$${absText}`;
  }
  return `${num < 0 ? "-" : ""}$${absText}`;
}

function buildOption(E, theme) {
  const data = buildSeries();
  const root = document.getElementById("overview-equity-chart");
  const compact = root?.closest(".overview-compact-chart-panel") !== null;
  const isMobile = window.matchMedia("(max-width: 640px)").matches;
  if (!data.length) {
    return {
      animation: false,
      title: {
        text: "No equity history yet.",
        left: "center",
        top: "middle",
        textStyle: { color: theme.muted, fontSize: 14, fontWeight: 500 },
      },
    };
  }

  const last = data[data.length - 1].value;
  const isUp = Number(last[1]) >= 0;
  const lastColor = isUp ? theme.green : theme.red;

  const payload = window.__SSH_OVERVIEW_EQUITY__;
  const maxDataAbs = data.reduce((acc, item) => Math.max(acc, Math.abs(Number(item.value?.[1]) || 0)), 0);
  const bound = niceSymmetricPercentBound(maxDataAbs);
  const markPoints = [];

  if (payload.max_point && payload.max_point[1] !== last[1]) {
    const maxTone = Number(payload.max_point[1]) >= 0 ? theme.green : theme.red;
    markPoints.push({
      coord: payload.max_point,
      value: payload.max_point[1],
      name: "Max",
      itemStyle: { color: maxTone },
      label: { color: maxTone },
    });
  }
  if (payload.min_point && payload.min_point[1] !== last[1]) {
    const minTone = Number(payload.min_point[1]) >= 0 ? theme.green : theme.red;
    markPoints.push({
      coord: payload.min_point,
      value: payload.min_point[1],
      name: "Min",
      itemStyle: { color: minTone },
      label: { color: minTone },
    });
  }
  markPoints.push({
    coord: last,
    name: "Last",
    itemStyle: { color: lastColor, borderColor: "#ffffff", borderWidth: 2 },
    label: {
      color: lastColor,
      position: "left",
      distance: 10,
      backgroundColor: "rgba(9,17,26,0.92)",
      borderRadius: 6,
      padding: [4, 6],
      formatter() {
        const val = Number(last[1]);
        return `${val >= 0 ? "+" : ""}${val.toFixed(2)}%`;
      },
    },
  });

  return {
    animationDuration: 500,
    grid: compact
      ? { left: isMobile ? 48 : 54, right: isMobile ? 16 : 34, top: 24, bottom: isMobile ? 34 : 42 }
      : { left: 60, right: 42, top: 28, bottom: 46 },
    visualMap: {
      show: false,
      type: "piecewise",
      dimension: 1,
      seriesIndex: 0,
      pieces: [
        { gte: 0, lte: bound, color: theme.green },
        { gte: -bound, lt: 0, color: theme.red },
      ],
    },
    tooltip: {
      trigger: "axis",
      appendToBody: !isMobile,
      confine: isMobile,
      axisPointer: { type: "cross" },
      backgroundColor: theme.tooltipBg,
      borderColor: theme.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: theme.tooltipText },
      extraCssText: [
        "z-index: 9999",
        "border-radius: 12px",
        `box-shadow: 0 10px 28px rgba(0,0,0,0.22)`,
      ].join(";"),
      position(pos, params, dom, rect, size) {
        const [x, y] = pos;
        const margin = isMobile ? 10 : 14;
        const boxWidth = dom?.offsetWidth || (isMobile ? 154 : 220);
        const boxHeight = dom?.offsetHeight || (isMobile ? 104 : 120);
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
        const point = params?.[0]?.value;
        if (!Array.isArray(point)) {
          return "";
        }
        const dt = formatUtcDateTime(point[0]);
        const deltaNum = Number(point[1]);
        const delta = `${deltaNum >= 0 ? "+" : ""}${deltaNum.toFixed(2)}`;
        const equity = formatUsd(point[2], false);
        const start = formatUsd(point[3], false);
        const deltaAbsValue = Number(point[4]);
        const deltaAbs = formatUsd(deltaAbsValue, true);
        const deltaTone = deltaAbsValue >= 0 ? theme.green : theme.red;
        const boxWidth = isMobile ? 154 : 220;
        const titleSize = isMobile ? 11 : 13;
        const bodySize = isMobile ? 10 : 12;
        return `
          <div style="width:${boxWidth}px; line-height:1.34; color:${theme.tooltipText}; font-size:${bodySize}px;">
            <div style="font-weight:700; color:${theme.tooltipTitle}; margin-bottom:4px; font-size:${titleSize}px;">${dt}</div>
            <div style="margin-bottom:1px;">Starting Capital: <b style="color:${theme.tooltipTitle};">${start}</b></div>
            <div style="margin-bottom:1px;">Equity: <b style="color:${theme.tooltipTitle};">${equity}</b></div>
            <div style="margin-bottom:1px;">Net Change: <b style="color:${deltaTone};">${deltaAbs}</b></div>
            <div>Δ% from Start: <b style="color:${deltaTone};">${delta}%</b></div>
          </div>
        `;
      },
    },
    xAxis: {
      type: "time",
      axisPointer: {
        label: {
          formatter(params) {
            return formatUtcDateTime(params.value);
          },
        },
      },
      axisLabel: {
        show: true,
        color: theme.muted,
        fontSize: isMobile ? 10 : 11,
        hideOverlap: true,
        formatter: formatAxisDate,
      },
      axisTick: { show: true, lineStyle: { color: theme.line, opacity: 0.7 } },
      axisLine: { show: true, lineStyle: { color: theme.line, opacity: 0.9 } },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      min: -bound,
      max: bound,
      axisLabel: {
        show: true,
        color: theme.muted,
        fontSize: isMobile ? 10 : 11,
        formatter(value) {
          return `${Number(value).toFixed(2)}%`;
        },
      },
      axisTick: { show: true, lineStyle: { color: theme.line, opacity: 0.7 } },
      axisLine: { show: true, lineStyle: { color: theme.line, opacity: 0.9 } },
      splitLine: { lineStyle: { color: theme.line, opacity: 0.55 } },
    },
    series: [
      {
        type: "line",
        name: "Equity Δ% from Start",
        data,
        smooth: false,
        showSymbol: false,
        symbolSize: 8,
        sampling: "lttb",
        lineStyle: { width: compact ? 2.2 : 2.4 },
        areaStyle: { origin: "auto", opacity: 0.18 },
        markLine: {
          symbol: "none",
          silent: true,
          label: {
            show: true,
            formatter: "0%",
            color: theme.text,
            fontSize: compact ? 11 : 12,
            fontWeight: 700,
            backgroundColor: "rgba(9,17,26,0.88)",
            borderRadius: 6,
            padding: compact ? [2, 5] : [3, 6],
          },
          lineStyle: {
            color: "rgba(255,255,255,0.34)",
            type: "dashed",
            width: 1.2,
            opacity: 1,
          },
          data: [{ yAxis: 0, label: { position: "insideEndTop" } }],
        },
        markPoint: {
          symbolSize: compact ? 14 : 16,
          label: {
            backgroundColor: "rgba(9,17,26,0.92)",
            borderRadius: 6,
            padding: compact ? [3, 5] : [4, 6],
            formatter(param) {
              const value = Number(Array.isArray(param.value) ? param.value[1] : param.value);
              return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
            },
          },
          data: markPoints,
        },
      },
    ],
  };
}

mountChart("overview-equity-chart", buildOption);
