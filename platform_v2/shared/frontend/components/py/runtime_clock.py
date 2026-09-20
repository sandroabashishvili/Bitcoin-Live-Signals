"""Shared runtime clock and countdown helpers for frontend pages."""


def render_runtime_clock_strip() -> str:
    return """
          <div class="runtime-clock-strip" aria-label="Runtime clock">
            <span class="runtime-clock-item">
              <span class="runtime-clock-label">System Clock</span>
              <strong class="runtime-clock-value" data-system-time>--:--:--</strong>
            </span>
            <span class="runtime-clock-item">
              <span class="runtime-clock-label">Next Signal Incoming</span>
              <strong class="runtime-clock-value" data-next-signal-countdown>--:--</strong>
            </span>
          </div>
"""


def render_runtime_clock_script() -> str:
    return """
    <script>
      (() => {
        const systemTimeNode = document.querySelector('[data-system-time]');
        const countdownNode = document.querySelector('[data-next-signal-countdown]');
        if (!systemTimeNode || !countdownNode) {
          return;
        }

        const systemFormatter = new Intl.DateTimeFormat('en-GB', {
          timeZone: 'UTC',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        });

        const update = () => {
          const now = new Date();
          systemTimeNode.textContent = `${systemFormatter.format(now)} UTC`;

          const nextCloseMs = Math.ceil(now.getTime() / 900000) * 900000;
          const remainingMs = Math.max(0, nextCloseMs - now.getTime());
          const totalSeconds = Math.floor(remainingMs / 1000);
          const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
          const seconds = String(totalSeconds % 60).padStart(2, '0');
          countdownNode.textContent = `${minutes}:${seconds}`;
          countdownNode.classList.toggle('countdown-safe', totalSeconds > 300);
          countdownNode.classList.toggle('countdown-urgent', totalSeconds <= 300);
        };

        update();
        window.setInterval(update, 1000);
      })();
    </script>
    <script>
      (() => {
        const controls = Array.from(document.querySelectorAll(".hero-control"));
        if (!controls.length) return;
        controls.forEach((control) => {
          control.addEventListener("touchstart", (event) => {
            const summary = control.querySelector("summary");
            if (!summary || !summary.contains(event.target)) return;
            event.preventDefault();
            controls.forEach((other) => {
              if (other !== control) other.open = false;
            });
            control.open = !control.open;
          });
        });
        controls.forEach((control) => {
          control.addEventListener("toggle", () => {
            if (!control.open) return;
            controls.forEach((other) => {
              if (other !== control) other.open = false;
            });
          });
        });

        const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
        if (!canHover) return;
        controls.forEach((control) => {
          let closeTimer = null;
          const scheduleClose = () => {
            if (closeTimer) window.clearTimeout(closeTimer);
            closeTimer = window.setTimeout(() => {
              control.open = false;
            }, 180);
          };
          const cancelClose = () => {
            if (closeTimer) window.clearTimeout(closeTimer);
            closeTimer = null;
          };
          control.addEventListener("mouseenter", () => {
            cancelClose();
            controls.forEach((other) => {
              if (other !== control) other.open = false;
            });
            control.open = true;
          });
          control.addEventListener("mouseleave", scheduleClose);
          control.addEventListener("focusout", scheduleClose);
          const menu = control.querySelector(".hero-control-menu");
          if (menu) {
            menu.addEventListener("mouseenter", cancelClose);
            menu.addEventListener("mouseleave", scheduleClose);
          }
        });

        document.addEventListener("click", (event) => {
          if (controls.some((control) => control.contains(event.target))) return;
          controls.forEach((control) => {
            control.open = false;
          });
        });
      })();
    </script>
"""
