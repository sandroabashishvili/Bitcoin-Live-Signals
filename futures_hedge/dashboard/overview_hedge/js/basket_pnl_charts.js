import { buildGradient, mountChart } from "../../../../shared/frontend/charts/common.js";

function asNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
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
    const positiveColor = side === "LONG" ? theme.green : theme.red;
    const latestPnl = points.length ? Number(points[points.length - 1][1]) : 0;
    const lineColor = latestPnl >= 0 ? positiveColor : theme.red;
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

    return {
      animationDuration: 420,
      grid: { left: isMobile ? 48 : 54, right: 18, top: 18, bottom: 34 },
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
          const time = new Date(point[0]).toLocaleString();
          const pnl = Number(point[1]).toFixed(2);
          const margin = Number(point[2]).toFixed(2);
          const entries = Number(point[3]);
          return `<strong>${side} Basket</strong><br>${time}<br>PnL: <b>${pnl} USDT</b><br>Margin: ${margin} USDT<br>Entries: ${entries}`;
        },
      },
      xAxis: {
        type: "time",
        axisLabel: { color: theme.muted, fontSize: 10, hideOverlap: true },
        axisLine: { lineStyle: { color: theme.line } },
        axisTick: { show: false },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
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
          lineStyle: { width: 2.2, color: lineColor },
          itemStyle: { color: lineColor },
          areaStyle: { color: buildGradient(E, lineColor), opacity: 0.28 },
          markLine: {
            symbol: "none",
            silent: true,
            label: { show: false },
            lineStyle: { color: "rgba(255,255,255,0.24)", type: "dashed" },
            data: [{ yAxis: 0 }],
          },
        },
      ],
    };
  };
}

mountChart("hedge-long-basket-chart", buildOption("LONG"));
mountChart("hedge-short-basket-chart", buildOption("SHORT"));
