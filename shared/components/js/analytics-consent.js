(function () {
  "use strict";

  const loader = document.currentScript;
  const measurementId = loader?.dataset.measurementId || "G-PLE3C4PMNF";
  const consentKey = "smartSignalHubAnalyticsConsent";
  const productionHost = "sandroabashishvili.github.io";
  const privacyUrl = "/Bitcoin-Live-Signals/legal/datenschutz.html";
  let banner = null;
  let analyticsLoaded = false;

  function addStyles() {
    if (document.getElementById("analytics-consent-styles")) return;
    const style = document.createElement("style");
    style.id = "analytics-consent-styles";
    style.textContent = `
      .analytics-consent-banner{position:fixed;right:18px;bottom:18px;z-index:9999;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:22px;width:min(760px,calc(100% - 36px));padding:20px;border:1px solid rgba(255,255,255,.16);border-radius:18px;background:#0b1723;color:#f4f8fb;box-shadow:0 22px 60px rgba(0,0,0,.4);font-family:inherit}
      .analytics-consent-copy p{margin:6px 0 0;color:#c8d4df;line-height:1.55}.analytics-consent-copy a{color:#7ce6c4}.analytics-consent-actions{display:flex;align-items:center;gap:10px}
      .analytics-consent-button{min-height:42px;border:1px solid rgba(255,255,255,.28);border-radius:999px;padding:0 16px;background:transparent;color:#f4f8fb;cursor:pointer;font:inherit}.analytics-consent-accept{border-color:#7ce6c4;background:#7ce6c4;color:#081711}
      .analytics-settings-button{border:0;padding:0;background:transparent;color:inherit;font:inherit;text-decoration:underline;cursor:pointer}
      @media(max-width:720px){.analytics-consent-banner{grid-template-columns:1fr}.analytics-consent-actions{flex-wrap:wrap}.analytics-consent-button{flex:1 1 150px}}@media print{.analytics-consent-banner{display:none!important}}
    `;
    document.head.appendChild(style);
  }

  function loadAnalytics() {
    if (analyticsLoaded || location.hostname !== productionHost) return;
    analyticsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    window.gtag("consent", "default", {
      analytics_storage: "denied",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
    window.gtag("consent", "update", {
      analytics_storage: "granted",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
    window.gtag("js", new Date());
    window.gtag("config", measurementId, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
    });
    const script = document.createElement("script");
    script.async = true;
    script.dataset.analyticsId = measurementId;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    document.head.appendChild(script);
  }

  function clearAnalyticsCookies() {
    document.cookie.split(";").forEach((part) => {
      const name = part.split("=")[0].trim();
      if (!/^_ga(?:_|$)/.test(name)) return;
      const expired = "expires=Thu, 01 Jan 1970 00:00:00 GMT";
      document.cookie = `${name}=;${expired};path=/;SameSite=Lax`;
      document.cookie = `${name}=;${expired};path=/;domain=${location.hostname};SameSite=Lax`;
      document.cookie = `${name}=;${expired};path=/;domain=.${location.hostname};SameSite=Lax`;
    });
  }

  function saveConsent(value) {
    try { localStorage.setItem(consentKey, value); } catch (_) {}
    if (value === "granted") loadAnalytics();
    else clearAnalyticsCookies();
    banner?.remove();
    banner = null;
  }

  function showBanner() {
    addStyles();
    banner?.remove();
    banner = document.createElement("aside");
    banner.className = "analytics-consent-banner";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-modal", "true");
    banner.setAttribute("aria-labelledby", "ssh-consent-title");
    banner.innerHTML = `
      <div class="analytics-consent-copy">
        <strong id="ssh-consent-title">Optional analytics</strong>
        <p>With your consent, Google Analytics helps us understand how SmartSignalHub is used. The Google tag is not loaded before consent. <a href="${privacyUrl}">Privacy details</a></p>
      </div>
      <div class="analytics-consent-actions">
        <button type="button" class="analytics-consent-button" data-consent="denied">Decline</button>
        <button type="button" class="analytics-consent-button analytics-consent-accept" data-consent="granted">Allow analytics</button>
      </div>`;
    banner.addEventListener("click", (event) => {
      const button = event.target.closest("[data-consent]");
      if (button) saveConsent(button.dataset.consent);
    });
    document.body.appendChild(banner);
    banner.querySelector('[data-consent="denied"]')?.focus();
  }

  function addSettingsControl() {
    const footer = document.querySelector(".footer-legal") || document.querySelector("footer nav") || document.querySelector("footer");
    if (!footer || footer.querySelector("[data-consent-settings]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "analytics-settings-button";
    button.dataset.consentSettings = "";
    button.textContent = "Cookie settings";
    footer.appendChild(button);
  }

  addStyles();
  let consent = null;
  try { consent = localStorage.getItem(consentKey); } catch (_) {}
  if (consent === "granted") loadAnalytics();
  if (consent !== "granted" && consent !== "denied") showBanner();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", addSettingsControl);
  else addSettingsControl();
  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-consent-settings]")) return;
    event.preventDefault();
    showBanner();
  });
})();
