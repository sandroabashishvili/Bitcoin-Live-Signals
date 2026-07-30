function cssVar(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function getChartTheme() {
  return {
    bg: cssVar("--panel", "#0f1722"),
    text: cssVar("--text", "#e8eef5"),
    muted: cssVar("--muted", "#8ca0b3"),
    line: cssVar("--line", "rgba(255,255,255,0.08)"),
    green: "#22c55e",
    red: "#ef4444",
    blue: cssVar("--blue", "#60a5fa"),
    amber: cssVar("--amber", "#fbbf24"),
    chartBg: cssVar("--panel-2", "#0c1622"),
    tooltipBg: cssVar("--panel", "#122131"),
    tooltipTitle: cssVar("--text", "#e8eef5"),
    tooltipText: cssVar("--text", "#e8eef5"),
    tooltipMuted: cssVar("--muted", "#8ca0b3"),
    tooltipBorder: cssVar("--line", "rgba(255,255,255,0.08)"),
  };
}

export function requireEcharts() {
  const E = window.echarts || null;
  if (!E) {
    return null;
  }
  return E;
}

export function buildGradient(E, color) {
  if (!E?.graphic?.LinearGradient) {
    return color;
  }
  const isGreen = color === "#22c55e";
  const alphaTop = isGreen ? "rgba(34,197,94,0.30)" : "rgba(239,68,68,0.28)";
  const alphaBottom = isGreen ? "rgba(34,197,94,0.03)" : "rgba(239,68,68,0.03)";
  return new E.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: alphaTop },
    { offset: 1, color: alphaBottom },
  ]);
}

export function mountChart(elementId, buildOption) {
  const E = requireEcharts();
  const el = document.getElementById(elementId);
  if (!E || !el) {
    return null;
  }

  const chart = E.init(el);
  const apply = () => {
    const option = buildOption(E, getChartTheme());
    if (option) {
      chart.setOption(option, true);
    }
  };

  apply();
  window.addEventListener("resize", () => {
    chart.resize();
  }, { passive: true });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      chart.resize();
      apply();
    }
  }, { passive: true });

  return chart;
}
