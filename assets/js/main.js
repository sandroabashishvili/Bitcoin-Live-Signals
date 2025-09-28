// ======================== FILE: main.js =========================

(async function () {
  // === [L1] LOAD HEADER & FOOTER PARTIALS (exec scripts, attach styles) ===
  async function loadPartials() {
    const bust = `?_=${Date.now()}`;
    try {
      // NOTE: files are at root, NOT /includes
      const [headerHtml, footerHtml] = await Promise.all([
        fetch("header.html" + bust, { cache: "no-store" }).then(r => r.text()),
        fetch("footer.html" + bust, { cache: "no-store" }).then(r => r.text())
      ]);

      // Parse header into a detached container
      const tmp = document.createElement("div");
      tmp.innerHTML = headerHtml;

      // Move <link rel="stylesheet"> and <link rel="icon"> to <head> (avoid duplicates)
      tmp.querySelectorAll('link[rel="stylesheet"], link[rel="icon"]').forEach(link => {
        const href = link.getAttribute("href");
        if (!href) return;
        const exists = [...document.querySelectorAll('link[rel]')].some(l => l.getAttribute("href") === href);
        if (!exists) {
          const clone = document.createElement("link");
          clone.rel = link.getAttribute("rel") || "stylesheet";
          clone.href = href;
          document.head.appendChild(clone);
        }
        link.remove();
      });

      // Execute header <script> tags (innerHTML doesn't run scripts)
      tmp.querySelectorAll("script").forEach(scr => {
        const src = scr.getAttribute("src");
        const type = scr.getAttribute("type") || "";
        if (src) {
          const exists = [...document.scripts].some(s => s.getAttribute("src") === src);
          if (exists) { scr.remove(); return; }
        }
        const s = document.createElement("script");
        if (type) s.type = type;
        if (src) s.src = src;
        else s.textContent = scr.textContent || "";
        s.async = false;
        document.head.appendChild(s);
        scr.remove();
      });

      // Inject nav/header markup
      const headerHost = document.getElementById("header-placeholder");
      if (headerHost) headerHost.innerHTML = tmp.innerHTML;

      // Inject footer markup
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

    // Highlight active link (ignore query/hash)
    const here = location.origin + location.pathname;
    document.querySelectorAll(".nav a[href]").forEach(link => {
      const url = new URL(link.href);
      if ((url.origin + url.pathname) === here) link.classList.add("active");
    });

    // Open
    if (toggle && nav && overlay) {
      toggle.addEventListener("click", () => {
        nav.classList.add("nav-open");
        overlay.classList.add("active");
      });
    }
    // Close by button
    if (closeBtn && nav && overlay) {
      closeBtn.addEventListener("click", () => {
        nav.classList.remove("nav-open");
        overlay.classList.remove("active");
      });
    }
    // Close by overlay click
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
  // data-theme: 'light' | 'dark' | (unset → 'system')
  // data-accent: 'boss' | 'ferrari' | 'bull' | 'joker' | ...
  function initThemeSwitcher() {
    const root = document.documentElement;
    const savedTheme = localStorage.getItem("theme");   // light | dark
    const savedAccent = localStorage.getItem("accent"); // boss | ferrari | ...

    // Apply persisted choices
    if (savedTheme === "light" || savedTheme === "dark") {
      root.setAttribute("data-theme", savedTheme);
    } else {
      // system mode → remove explicit override
      root.removeAttribute("data-theme");
    }
    if (savedAccent) {
      root.setAttribute("data-accent", savedAccent);
    }

    // Accent swatches: <button class="swatch" data-theme="boss">…</button>
    document.querySelectorAll(".swatch").forEach(swatch => {
      swatch.addEventListener("click", () => {
        const accent = swatch.getAttribute("data-theme");
        if (!accent) return;
        root.setAttribute("data-accent", accent);
        localStorage.setItem("accent", accent);
        window.dispatchEvent(new Event("themechange"));
      });
    });

    // Optional light/dark/system toggles:
    // <button data-force-theme="light|dark|system">...</button>
    document.querySelectorAll("[data-force-theme]").forEach(btn => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-force-theme"); // 'light' | 'dark' | 'system'
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

    // React to OS scheme changes while in 'system' mode
    try {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq && typeof mq.addEventListener === "function") {
        mq.addEventListener("change", () => {
          if (!root.hasAttribute("data-theme")) {
            // still in 'system'
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

    iframe.addEventListener("load", () => {
      loader.style.display = "none";
    });
  }

  // === [L6] Horizontal wheel → horizontal scroll for tables ===
  function attachHorizontalWheel(root = document) {
    root.addEventListener(
      "wheel",
      function (e) {
        const wrap = e.target && e.target.closest ? e.target.closest(".table-wrap") : null;
        if (!wrap) return;
        if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
          wrap.scrollLeft += e.deltaY;
          e.preventDefault(); // requires non-passive
        }
      },
      { passive: false }
    );
  }

  // ==== [RUN] ====
  await loadPartials();     // header/footer first (nav/theme controls rely on them)
  initNavigation();
  initThemeSwitcher();
  initFooterYear();
  initIframeLoader();
  attachHorizontalWheel();

  // Fire initial themechange so charts/components can theme themselves
  window.dispatchEvent(new Event("themechange"));

  window.dispatchEvent(new Event("themechange"));

})();
