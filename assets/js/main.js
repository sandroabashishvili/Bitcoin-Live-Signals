// ======================== FILE: main.js =========================
(async () => {
  'use strict';

  // === [L1] LOAD HEADER & FOOTER PARTIALS (exec scripts, attach styles) ===
  async function loadPartials() {
    // project root გამოვიყვანოთ იმავე მისამართიდან, საიდანაც main.js იტვირთება
    const thisScript =
      document.currentScript ||
      [...document.scripts].find(s => (s.src || "").includes("/assets/js/main.js"));
    const ROOT = thisScript
      ? thisScript.src.replace(location.origin, "").replace(/\/assets\/js\/main\.js.*$/, "")
      : ""; // fallback: "" (სიგნალი, თუ ვერ დადგინდა)

    const bust = `?_=${Date.now()}`;
    const headerURL = `${ROOT}/header.html${bust}`;
    const footerURL = `${ROOT}/footer.html${bust}`;

    try {
      const [headerHtml, footerHtml] = await Promise.all([
        fetch(headerURL, { cache: "no-store" }).then(r => r.text()),
        fetch(footerURL, { cache: "no-store" }).then(r => r.text())
      ]);

      const tmp = document.createElement("div");
      tmp.innerHTML = headerHtml;

      tmp.querySelectorAll('link[rel="stylesheet"], link[rel="icon"]').forEach(link => {
        const href = link.getAttribute("href");
        if (!href) return;
        const exists = [...document.querySelectorAll('link[rel]')].some(l => l.getAttribute("href") === href);
        if (!exists) {
          const clone = document.createElement("link");
          clone.rel = link.getAttribute("rel") || "stylesheet";
          clone.href = href.startsWith("http") ? href : `${ROOT}${href.startsWith("/") ? "" : "/"}${href}`;
          document.head.appendChild(clone);
        }
        link.remove();
      });

      tmp.querySelectorAll("script").forEach(scr => {
        const src = scr.getAttribute("src");
        const type = scr.getAttribute("type") || "";
        if (src) {
          const abs = src.startsWith("http") ? src : `${ROOT}${src.startsWith("/") ? "" : "/"}${src}`;
          const exists = [...document.scripts].some(s => s.getAttribute("src") === abs);
          if (exists) { scr.remove(); return; }
          const s = document.createElement("script");
          if (type) s.type = type;
          s.src = abs;
          s.async = false;
          document.head.appendChild(s);
          scr.remove();
        } else {
          const s = document.createElement("script");
          if (type) s.type = type;
          s.textContent = scr.textContent || "";
          s.async = false;
          document.head.appendChild(s);
          scr.remove();
        }
      });

      const headerHost = document.getElementById("header-placeholder");
      if (headerHost) headerHost.innerHTML = tmp.innerHTML;

      const footerHost = document.getElementById("footer-placeholder");
      if (footerHost) footerHost.innerHTML = footerHtml;
    } catch (err) {
      console.error("Error loading partials:", err);
    }
  }

  // === [L2] NAVIGATION (ACTIVE STATE & MOBILE MENU) ===
  function initNavigation() {
    const nav = document.querySelector(".nav");
    const toggle = document.querySelector(".menu-toggle");
    const closeBtn = document.querySelector(".menu-close");
    const overlay = document.querySelector(".menu-overlay");

    const here = location.origin + location.pathname;
    document.querySelectorAll(".nav a[href]").forEach(link => {
      const url = new URL(link.href);
      if ((url.origin + url.pathname) === here) link.classList.add("active");
    });

    if (toggle && nav && overlay) {
      toggle.addEventListener("click", () => {
        nav.classList.add("nav-open");
        overlay.classList.add("active");
      });
    }
    if (closeBtn && nav && overlay) {
      closeBtn.addEventListener("click", () => {
        nav.classList.remove("nav-open");
        overlay.classList.remove("active");
      });
    }
    if (overlay && nav) {
      overlay.addEventListener("click", () => {
        nav.classList.remove("nav-open");
        overlay.classList.remove("active");
      });
    }
  }

  // === [L3] FOOTER YEAR ===
  function initFooterYear() {
    const yearEl = document.getElementById("year");
    if (yearEl) yearEl.textContent = new Date().getFullYear();
  }

  // === [L4] THEME & ACCENT SWITCHER (persist in localStorage) ===
  function initThemeSwitcher() {
    const root = document.documentElement;
    const savedTheme = localStorage.getItem("theme");   // light | dark
    const savedAccent = localStorage.getItem("accent"); // boss | ferrari | ...

    if (savedTheme === "light" || savedTheme === "dark") {
      root.setAttribute("data-theme", savedTheme);
    } else {
      root.removeAttribute("data-theme"); // system
    }
    if (savedAccent) {
      root.setAttribute("data-accent", savedAccent);
    }

    document.querySelectorAll(".swatch").forEach(swatch => {
      swatch.addEventListener("click", () => {
        const accent = swatch.getAttribute("data-theme");
        if (!accent) return;
        root.setAttribute("data-accent", accent);
        localStorage.setItem("accent", accent);
        window.dispatchEvent(new Event("themechange"));
      });
    });

    document.querySelectorAll("[data-force-theme]").forEach(btn => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-force-theme"); // light|dark|system
        if (mode === "system") {
          root.removeAttribute("data-theme");
          localStorage.removeItem("theme");
        } else {
          root.setAttribute("data-theme", mode);
          localStorage.setItem("theme", mode);
        }
        window.dispatchEvent(new Event("themechange"));
      });
    });

    try {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq && typeof mq.addEventListener === "function") {
        mq.addEventListener("change", () => {
          if (!document.documentElement.hasAttribute("data-theme")) {
            window.dispatchEvent(new Event("themechange"));
          }
        });
      }
    } catch {}
  }

  // === [L5] DASHBOARD IFRAME LOADING SPINNER ===
  function initIframeLoader() {
    const iframe = document.querySelector('iframe[title="SmartSignalHub Dashboard"]');
    if (!iframe) return;
    const loader = document.createElement("div");
    loader.className = "iframe-loader";
    loader.innerHTML = `<div class="spinner"></div><span>Loading Dashboard...</span>`;
    iframe.parentNode.insertBefore(loader, iframe);
    iframe.addEventListener("load", () => { loader.style.display = "none"; });
  }

  // === [L6] Horizontal wheel → horizontal scroll for tables ===
  function attachHorizontalWheel(root = document) {
    root.addEventListener("wheel", function (e) {
      const wrap = e.target && e.target.closest ? e.target.closest(".table-wrap") : null;
      if (!wrap) return;
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        wrap.scrollLeft += e.deltaY;
        e.preventDefault(); // requires non-passive
      }
    }, { passive: false });
  }

  // === [L7] GLOBAL TICKER SYSTEM (SSHTicker) ===
  function initGlobalTicker() {
    const subscribers = new Set();
    
    window.SSHTicker = {
      lastUpdateTime: Date.now(),
      
      subscribe(callback) {
        if (typeof callback !== 'function') return;
        subscribers.add(callback);
        return () => subscribers.delete(callback);
      },
      
      trigger() {
        this.lastUpdateTime = Date.now();
        subscribers.forEach(callback => {
          try { callback(); } catch (e) { console.warn('Ticker callback error:', e); }
        });
        // Last update is now handled by equity-viewer when data actually loads
      }
    };

    // განახლება ყოველ 30 წუთში (1,800,000 მილისეკუნდი)
    setInterval(() => {
      if (!document.hidden) {
        window.SSHTicker.trigger();
      }
    }, 1800000); // 30 წუთი

    // Update current time every second for smooth display
    setInterval(() => {
      updateCurrentTime();
    }, 1000); // 1 second

    // Initial updates immediately
    updateCurrentTime();
    
    // Force another update after DOM is ready
    setTimeout(() => {
      updateCurrentTime();
    }, 100);
  }

  // === [L8] TIME DISPLAY FUNCTIONS ===
  function updateCurrentTime() {
    const now = new Date();
    const timeStr = now.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit', 
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    
    const elements = document.querySelectorAll('#current-time');
    
    elements.forEach(el => {
      const oldValue = el.textContent;
      if (oldValue !== timeStr && oldValue !== '—') {
        el.classList.add('changing');
        setTimeout(() => el.classList.remove('changing'), 300);
      }
      el.textContent = timeStr;
    });
  }



  // დავამატოთ last update-ის ტრიგერი ticker-ზე
  window.addEventListener('load', () => {
    if (window.SSHTicker) {
      window.SSHTicker.subscribe(() => {
        updateLastUpdate();
      });
    }
  });

  // ==== [RUN] ====
  await loadPartials();     // header/footer first (nav/theme controls rely on them)
  initNavigation();
  initThemeSwitcher();
  initFooterYear();
  initIframeLoader();
  attachHorizontalWheel();
  initGlobalTicker();       // დაამატეთ global ticker

  // Fire initial themechange so charts/components can theme themselves
  window.dispatchEvent(new Event("themechange"));
  
  // Setup global time update functions that work with Shadow DOM
  window.updateTimeDisplays = {
    updateCurrentTime
  };
  
  // გავუშვათ პირველი განახლება 2 წამის შემდეგ
  setTimeout(() => {
    if (window.SSHTicker) {
      window.SSHTicker.trigger();
    }
  }, 2000);
})();
