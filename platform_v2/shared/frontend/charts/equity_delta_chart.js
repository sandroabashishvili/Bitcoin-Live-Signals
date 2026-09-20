import { buildGradient, mountChart } from "./common.js";

function parseTs(value) {
  if (!value) {
    return NaN;
  }
  const ts = Date.parse(value);
  return Number.isFinite(ts) ? ts : NaN;
}

function buildSeries() {
  const rows = Array.isArray(window.__SSH_OVERVIEW_EQUITY__) ? window.__SSH_OVERVIEW_EQUITY__ : [];
  if (!rows.length) {
    return [];
  }

  const points = rows
    .map((row) => {
      const start = Number(row.starting_capital);
      const equity = Number(row.equity);
      const ts = parseTs(row.datetime || row.date || row.timestamp);
      if (!Number.isFinite(start) || !Number.isFinite(equity) || !Number.isFinite(ts) || start === 0) {
        return null;
      }
      const deltaPct = ((equity - start) / start) * 100;
      const deltaAbs = equity - start;
      return {
        value: [ts, Number(deltaPct.toFixed(4)), equity, start, deltaAbs],
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.value[0] - b.value[0]);

  if (points.length) {
    const first = points[0].value;
    const firstTs = first[0];
    const firstStart = first[3];
    const firstDelta = first[1];
    if (Number.isFinite(firstTs) && Number.isFinite(firstStart) && firstDelta !== 0) {
      points.unshift({
        value: [firstTs - 60000, 0, firstStart, firstStart, 0],
      });
    }
  }

  return points;
}

function formatAxisDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
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
  const isUp = last[1] >= 0;
  const lineColor = isUp ? theme.green : theme.red;

  const minDelta = Math.min(...data.map((point) => point.value[1]));
  const maxDelta = Math.max(...data.map((point) => point.value[1]));
  const maxAbsDelta = Math.max(Math.abs(minDelta), Math.abs(maxDelta));
  const axisHalfRange = Math.max(Number((maxAbsDelta * 1.25).toFixed(4)), 0.1);
  const markPoints = [];

  if (maxDelta !== last[1]) {
    markPoints.push({ type: "max", name: "Max" });
  }
  if (minDelta !== last[1]) {
    markPoints.push({ type: "min", name: "Min" });
  }
  markPoints.push({
    coord: last,
    name: "Last",
    itemStyle: { color: lineColor, borderColor: "#ffffff", borderWidth: 2 },
    label: {
      color: lineColor,
      position: "left",
      distance: 10,
      backgroundColor: "rgba(9,17,26,0.92)",
      borderRadius: 6,
      padding: [4, 6],
      formatter() {
        return `${Number(last[1]).toFixed(2)}%`;
      },
    },
  });

  return {
    animationDuration: 500,
    grid: compact
      ? { left: isMobile ? 42 : 48, right: isMobile ? 16 : 34, top: 24, bottom: isMobile ? 34 : 42 }
      : { left: 54, right: 42, top: 28, bottom: 46 },
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
        const dt = new Date(point[0]).toLocaleString();
        const delta = Number(point[1]).toFixed(2);
        const equity = Number(point[2]).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
        const start = Number(point[3]).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
        const deltaAbsValue = Number(point[4]);
        const deltaAbs = deltaAbsValue.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
        const deltaTone = deltaAbsValue >= 0 ? theme.green : theme.red;
        const boxWidth = isMobile ? 154 : 220;
        const titleSize = isMobile ? 11 : 13;
        const bodySize = isMobile ? 10 : 12;
        return `
          <div style="width:${boxWidth}px; line-height:1.34; color:${theme.tooltipText}; font-size:${bodySize}px;">
            <div style="font-weight:700; color:${theme.tooltipTitle}; margin-bottom:4px; font-size:${titleSize}px;">${dt}</div>
            <div style="margin-bottom:1px;">Starting Capital: <b style="color:${theme.tooltipTitle};">$${start}</b></div>
            <div style="margin-bottom:1px;">Equity: <b style="color:${theme.tooltipTitle};">$${equity}</b></div>
            <div style="margin-bottom:1px;">Net Change: <b style="color:${deltaTone};">$${deltaAbs}</b></div>
            <div>Δ% from Start: <b style="color:${deltaTone};">${delta}%</b></div>
          </div>
        `;
      },
    },
    xAxis: {
      type: "time",
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
      min: -axisHalfRange,
      max: axisHalfRange,
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
        lineStyle: { width: compact ? 2.2 : 2.4, color: lineColor },
        areaStyle: { color: buildGradient(E, lineColor), opacity: 0.34 },
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
            color: "rgba(255,255,255,0.32)",
            type: "dashed",
            width: 1.2,
            opacity: 1,
          },
          data: [{ yAxis: 0, label: { position: "insideEndTop" } }],
        },
        markPoint: {
          symbolSize: compact ? 14 : 16,
          label: {
            color: lineColor,
            backgroundColor: "rgba(9,17,26,0.92)",
            borderRadius: 6,
            padding: compact ? [3, 5] : [4, 6],
            formatter(param) {
              const value = Array.isArray(param.value) ? param.value[1] : param.value;
              return `${Number(value).toFixed(2)}%`;
            },
          },
          data: markPoints,
        },
      },
    ],
  };
}

mountChart("overview-equity-chart", buildOption);
