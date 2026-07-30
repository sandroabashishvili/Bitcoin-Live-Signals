import { mountChart } from "./common.js";

function getPayload() {
  const payload = window.__SSH_STRATEGY_LOGIC__;
  return payload && typeof payload === "object" ? payload : {};
}

function buildDonutOption(title, totals, mode, theme) {
  const isMobile = window.matchMedia("(max-width: 640px)").matches;
  const tooltipMinWidth = isMobile ? 180 : 220;
  const tooltipFontSize = isMobile ? 12 : 13;
  const tp = Number(totals?.tp || 0);
  const sl = Number(totals?.sl || 0);
  const hasForceClose = totals && Object.prototype.hasOwnProperty.call(totals, "force_close");
  const thirdKey = hasForceClose ? "force_close" : "open";
  const thirdLabel = hasForceClose ? "Force Close" : "Open";
  const thirdValue = Number(totals?.[thirdKey] || 0);
  const winRate = Number.isFinite(Number(totals?.win_rate))
    ? Number(totals?.win_rate || 0)
    : (tp + sl)
      ? (tp / (tp + sl)) * 100
      : 0;
  return {
    animationDuration: 550,
    backgroundColor: theme.chartBg,
    title: {
      text: `${winRate.toFixed(1)}%`,
      subtext: title,
      left: "center",
      top: "39%",
      textStyle: { color: theme.text, fontSize: 18, fontWeight: 700 },
      subtextStyle: {
        color: theme.muted,
        fontSize: 10,
        fontWeight: 500,
        lineHeight: 14,
        padding: [4, 0, 0, 0],
      },
    },
    tooltip: {
      trigger: "item",
      confine: true,
      appendToBody: false,
      backgroundColor: theme.tooltipBg,
      borderWidth: 0,
      triggerOn: isMobile ? "click" : "mousemove",
      hideDelay: isMobile ? 1400 : 0,
      textStyle: { color: theme.text, fontSize: tooltipFontSize },
      extraCssText: "max-width: 92vw; z-index: 10000; white-space: normal;",
      position(point, _params, dom, _rect, size) {
        if (!isMobile) return null;
        const [x, y] = point;
        const boxW = size.contentSize[0];
        const boxH = size.contentSize[1];
        const vw = size.viewSize[0];
        const vh = size.viewSize[1];
        const left = Math.min(Math.max(8, x - boxW / 2), vw - boxW - 8);
        const top = Math.min(Math.max(8, y - boxH - 12), vh - boxH - 8);
        return [left, top];
      },
      formatter(params) {
        const totalCount = tp + sl + thirdValue;
        const tone = params.name === "TP" ? theme.green : params.name === "SL" ? theme.red : theme.amber;
        const percent = totalCount ? (Number(params.value || 0) / totalCount) * 100 : 0;
        return `
          <div style="min-width: ${tooltipMinWidth}px; line-height: 1.45;">
            <div style="font-weight: 700; color: ${theme.text}; margin-bottom: 6px;">${title} Gates</div>
            <div>${params.name}: <b style="color:${tone};">${params.value}</b> <span style="color:${theme.muted};">(${percent.toFixed(1)}%)</span></div>
            <div>Mix Total: <b>${totalCount}</b></div>
          </div>
        `;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["50%", "70%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: { borderWidth: 2, borderColor: theme.chartBg },
        data: [
          { value: tp || 0.0001, name: "TP", itemStyle: { color: theme.green } },
          { value: sl || 0.0001, name: "SL", itemStyle: { color: theme.red } },
          { value: thirdValue || 0.0001, name: thirdLabel, itemStyle: { color: theme.amber } },
        ],
      },
    ],
  };
}

const strategyLogicPayload = getPayload();
const chartMode = strategyLogicPayload.chart_mode || "default";

mountChart("strategy-primary-donut", (_E, theme) =>
  buildDonutOption("Primary", strategyLogicPayload.primary_totals, chartMode, theme),
);

mountChart("strategy-confirmation-donut", (_E, theme) =>
  buildDonutOption("Confirmation", strategyLogicPayload.confirmation_totals, chartMode, theme),
);
