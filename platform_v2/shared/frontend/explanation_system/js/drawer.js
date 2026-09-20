const drawer = document.querySelector("[data-expl-drawer]");
const titleNode = document.querySelector("[data-expl-title]");
const summaryNode = document.querySelector("[data-expl-summary]");
const detailsNode = document.querySelector("[data-expl-details]");
const linkNode = document.querySelector("[data-expl-link]");
const secondaryLinkNode = document.querySelector("[data-expl-link-secondary]");
const explanationMap = window.__SSH_EXPLANATIONS__ || {};
let hoverTooltip = null;

const ensureHoverTooltip = () => {
  if (hoverTooltip) return hoverTooltip;
  hoverTooltip = document.createElement("div");
  hoverTooltip.className = "explanation-hover-tooltip";
  hoverTooltip.setAttribute("aria-hidden", "true");
  document.body.appendChild(hoverTooltip);
  return hoverTooltip;
};

const hideHoverTooltip = () => {
  if (!hoverTooltip) return;
  hoverTooltip.setAttribute("aria-hidden", "true");
  hoverTooltip.textContent = "";
};

const positionHoverTooltip = (trigger) => {
  if (!hoverTooltip || !trigger) return;
  const rect = trigger.getBoundingClientRect();
  const tooltipRect = hoverTooltip.getBoundingClientRect();
  const margin = 12;
  let left = rect.left + rect.width / 2 - tooltipRect.width / 2;
  left = Math.max(margin, Math.min(left, window.innerWidth - tooltipRect.width - margin));
  let top = rect.top - tooltipRect.height - 10;
  if (top < margin) {
    top = rect.bottom + 10;
  }
  hoverTooltip.style.left = `${left}px`;
  hoverTooltip.style.top = `${top}px`;
};

const showHoverTooltip = (trigger) => {
  if (!trigger || window.matchMedia("(max-width: 640px)").matches) return;
  const text = trigger.getAttribute("data-expl-hover");
  if (!text) return;
  const tooltip = ensureHoverTooltip();
  tooltip.textContent = text;
  tooltip.setAttribute("aria-hidden", "false");
  positionHoverTooltip(trigger);
};

const bindHoverTitles = () => {
  const triggers = document.querySelectorAll("[data-expl-key]");
  for (const trigger of triggers) {
    const key = trigger.getAttribute("data-expl-key");
    if (!key) continue;
    const item = explanationMap[key];
    if (!item) continue;
    const hoverText = item.summary || item.title || "";
    if (!hoverText) continue;
    trigger.setAttribute("data-expl-hover", hoverText);
    trigger.setAttribute("aria-label", item.title || hoverText);
    trigger.removeAttribute("title");
    trigger.addEventListener("mouseenter", () => showHoverTooltip(trigger));
    trigger.addEventListener("mouseleave", hideHoverTooltip);
    trigger.addEventListener("focus", () => showHoverTooltip(trigger));
    trigger.addEventListener("blur", hideHoverTooltip);
  }
};

const closeDrawer = () => {
  if (!drawer) return;
  drawer.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
};

const openDrawer = (key) => {
  if (!drawer) return;
  const item = explanationMap[key];
  if (!item) return;

  titleNode.textContent = item.title || "Metric Detail";
  summaryNode.textContent = item.summary || "";
  detailsNode.innerHTML = "";

  for (const detail of item.details || []) {
    const li = document.createElement("li");
    li.textContent = detail;
    detailsNode.appendChild(li);
  }

  if (linkNode) {
    if (item.cta_label && item.cta_href) {
      linkNode.textContent = item.cta_label;
      linkNode.setAttribute("href", item.cta_href);
      linkNode.hidden = false;
    } else {
      linkNode.hidden = true;
      linkNode.textContent = "";
      linkNode.setAttribute("href", "#");
    }
  }

  if (secondaryLinkNode) {
    if (item.secondary_cta_label && item.secondary_cta_href) {
      secondaryLinkNode.textContent = item.secondary_cta_label;
      secondaryLinkNode.setAttribute("href", item.secondary_cta_href);
      secondaryLinkNode.hidden = false;
    } else {
      secondaryLinkNode.hidden = true;
      secondaryLinkNode.textContent = "";
      secondaryLinkNode.setAttribute("href", "#");
    }
  }

  drawer.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
};

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-expl-key]");
  if (trigger) {
    event.preventDefault();
    openDrawer(trigger.getAttribute("data-expl-key"));
    return;
  }

  if (event.target.closest("[data-expl-close]")) {
    closeDrawer();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeDrawer();
    hideHoverTooltip();
  }
});

window.addEventListener("scroll", hideHoverTooltip, { passive: true });
window.addEventListener("resize", hideHoverTooltip);

bindHoverTitles();
