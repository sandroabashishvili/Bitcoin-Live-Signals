import { mountChart } from "../../../../shared/frontend/charts/common.js";

function asNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function niceSymmetricBound(maxAbs) {
  const padded = Math.max(maxAbs * 1.12, 10);
  const magnitude = Math.pow(10, Math.floor(Math.log10(padded)));
  const normalized = padded / magnitude;
  const step = normalized <= 1.2 ? 1.2 : normalized <= 1.5 ? 1.5 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 3 ? 3 : normalized <= 4 ? 4 : normalized <= 5 ? 5 : normalized <= 6 ? 6 : normalized <= 8 ? 8 : 10;
  return Math.ceil(step * magnitude);
}

function formatAxisDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function timestampOf(row) {
  const numeric = Number(row?.timestamp_ms);
  if (Number.isFinite(numeric) && numeric > 0) {
    return numeric;
  }
  const parsed = Date.parse(row?.datetime || row?.time_readable || row?.timestamp || "");
  return Number.isFinite(parsed) ? parsed : NaN;
}

function basketPoints(side) {
  const key = side === "LONG" ? "long_basket" : "short_basket";
  const rows = Array.isArray(window.__SSH_HEDGE_BASKETS__) ? window.__SSH_HEDGE_BASKETS__ : [];
  return rows
    .map((row) => {
      const timestamp = timestampOf(row);
      const basket = row?.[key] || {};
      if (!Number.isFinite(timestamp)) {
        return null;
      }
      return [
        timestamp,
        asNumber(basket.unrealized_pnl),
        asNumber(basket.margin_usdt),
        asNumber(basket.count),
      ];
    })
    .filter(Boolean)
    .sort((a, b) => a[0] - b[0]);
}

function buildOption(side) {
  return (E, theme) => {
    const points = basketPoints(side);
    const isMobile = window.matchMedia("(max-width: 640px)").matches;

    if (!points.length) {
      return {
        animation: false,
        title: {
          text: `No ${side} basket history yet.`,
          left: "center",
          top: "middle",
          textStyle: { color: theme.muted, fontSize: 12, fontWeight: 500 },
        },
      };
    }

    const maxAbs = points.reduce((acc, point) => Math.max(acc, Math.abs(Number(point[1]) || 0)), 0);
    const bound = niceSymmetricBound(maxAbs);

    return {
      animationDuration: 420,
      grid: { left: isMobile ? 48 : 54, right: 18, top: 18, bottom: 34 },
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
        confine: true,
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        borderWidth: 1,
        textStyle: { color: theme.tooltipText },
        formatter(params) {
          const point = params?.[0]?.value;
          if (!Array.isArray(point)) return "";
          const time =
            new Date(point[0]).toLocaleString("en-US", {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
              timeZone: "UTC",
            }) + " UTC";
          const pnlNum = Number(point[1]);
          const pnl = `${pnlNum >= 0 ? "+" : ""}${pnlNum.toFixed(2)}`;
          const pnlColor = pnlNum >= 0 ? theme.green : theme.red;
          const margin = Number(point[2]).toFixed(2);
          const entries = Number(point[3]);
          return `<strong>${side} Basket</strong><br>${time}<br>PnL: <b style="color:${pnlColor};">${pnl} USDT</b><br>Margin: ${margin} USDT<br>Entries: ${entries}`;
        },
      },
      xAxis: {
        type: "time",
        axisLabel: {
          color: theme.muted,
          fontSize: 10,
          hideOverlap: true,
          formatter: formatAxisDate,
        },
        axisLine: { lineStyle: { color: theme.line } },
        axisTick: { show: false },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: -bound,
        max: bound,
        axisLabel: {
          color: theme.muted,
          fontSize: 10,
          formatter(value) {
            return `${Number(value).toFixed(1)}`;
          },
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: theme.line, opacity: 0.45 } },
      },
      series: [
        {
          type: "line",
          name: `${side} Unrealized PnL`,
          data: points,
          smooth: 0.22,
          showSymbol: points.length < 8,
          symbolSize: 6,
          lineStyle: { width: 2.2 },
          areaStyle: { origin: "auto", opacity: 0.18 },
          markLine: {
            symbol: "none",
            silent: true,
            label: { show: false },
            lineStyle: { color: "rgba(255,255,255,0.34)", type: "dashed" },
            data: [{ yAxis: 0 }],
          },
        },
      ],
    };
  };
}

mountChart("hedge-long-basket-chart", buildOption("LONG"));
mountChart("hedge-short-basket-chart", buildOption("SHORT"));
