import { mountChart } from "./common.js";

// Backend owns counts, percentages, denominators and win rates.
function buildDonutOption(chart, theme) {
  if (!chart?.has_data) {
    return {
      animation: false, backgroundColor: theme.chartBg,
      title: { text: "No gate outcomes yet.", left: "center", top: "middle",
        textStyle: { color: theme.muted, fontSize: 14 } },
    };
  }
  const isMobile = window.matchMedia("(max-width: 640px)").matches;
  const tone = (key) => key === "tp" || key === "profit_lock"
    ? theme.green : key === "sl" ? theme.red : theme.amber;
  return {
    animationDuration: 550, backgroundColor: theme.chartBg,
    title: {
      text: chart.win_rate_text, subtext: chart.title, left: "center", top: "39%",
      textStyle: { color: theme.text, fontSize: 18, fontWeight: 700 },
      subtextStyle: { color: theme.muted, fontSize: 10, lineHeight: 14 },
    },
    tooltip: {
      trigger: "item", confine: true, appendToBody: false,
      backgroundColor: theme.tooltipBg, borderWidth: 0,
      triggerOn: isMobile ? "click" : "mousemove", hideDelay: isMobile ? 1400 : 0,
      textStyle: { color: theme.text, fontSize: isMobile ? 12 : 13 },
      extraCssText: "max-width: 92vw; z-index: 10000; white-space: normal;",
      formatter(params) {
        const outcome = params.data;
        return `<div style="max-width: 300px; line-height: 1.45;">
          <div style="font-weight:700;">${chart.title} Gates</div>
          <div>${outcome.name}: <b style="color:${tone(outcome.key)};">${outcome.value}</b> (${outcome.percent_text})</div>
          <div>Gate participations: <b>${chart.total}</b></div>
          <div style="color:${theme.muted};">${chart.count_definition}</div>
          <div style="color:${theme.muted};">Win rate: ${chart.win_rate_definition}</div>
        </div>`;
      },
    },
    series: [{
      type: "pie", radius: ["50%", "70%"], center: ["50%", "50%"],
      avoidLabelOverlap: true, label: { show: false }, labelLine: { show: false },
      itemStyle: { borderWidth: 2, borderColor: theme.chartBg },
      data: chart.outcomes.map((outcome) => ({
        ...outcome, itemStyle: { color: tone(outcome.key) },
      })),
    }],
  };
}

const charts = window.__SSH_STRATEGY_LOGIC__?.charts || [];
mountChart("strategy-primary-donut", (_E, theme) => buildDonutOption(charts[0], theme));
mountChart("strategy-confirmation-donut", (_E, theme) => buildDonutOption(charts[1], theme));
