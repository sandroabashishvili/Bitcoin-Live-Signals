"""Local browser chat server for the SmartSignalHub assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any
from urllib.parse import urlparse

from .capabilities.action_audit import latest_action_rows, pending_actions
from .engine import answer_question
from .runtime_readers import PLATFORM_ROOT


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
ARTIFACT_ROOT = PLATFORM_ROOT / "runtime" / "artifacts" / "ai_assistant"


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, model: str | None = None) -> None:
    AssistantRequestHandler.model = model
    server = ThreadingHTTPServer((host, port), AssistantRequestHandler)
    print(f"SmartSignalHub AI Assistant: http://{host}:{port}")
    if model:
        print(f"Model composer: {model}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SmartSignalHub AI Assistant.")
    finally:
        server.server_close()


class AssistantRequestHandler(BaseHTTPRequestHandler):
    server_version = "SmartSignalHubAssistant/0.1"
    model: str | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(INDEX_HTML)
            return
        if parsed.path == "/health":
            self._send_json({"status": "ok"})
            return
        if parsed.path == "/api/actions":
            self._send_json({"pending": pending_actions(), "latest": latest_action_rows(25)})
            return
        if parsed.path == "/api/history":
            self._send_json({"latest": _latest_history_rows(20)})
            return
        self._send_json({"error": "not_found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/ask":
            self._send_json({"error": "not_found"}, status=404)
            return
        payload = self._read_json_body()
        question = str(payload.get("question") or "").strip()
        if not question:
            self._send_json({"error": "question_required"}, status=400)
            return
        started = _utc_now()
        try:
            answer = answer_question(question, model=self.model)
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            answer = f"Assistant error: {type(exc).__name__}: {exc}"
            self._write_history(question=question, answer=answer, created_at=started, ok=False)
            self._send_json({"answer": answer, "ok": False}, status=500)
            return
        self._write_history(question=question, answer=answer, created_at=started, ok=True)
        self._send_json({"answer": answer, "ok": True, "created_at": started})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_history(self, *, question: str, answer: str, created_at: str, ok: bool) -> None:
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        date_iso = created_at[:10]
        path = ARTIFACT_ROOT / f"chat_history_{date_iso}.jsonl"
        row = {
            "created_at": created_at,
            "question": question,
            "answer": answer,
            "ok": ok,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _latest_history_rows(limit: int = 20) -> list[dict[str, Any]]:
    if not ARTIFACT_ROOT.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(ARTIFACT_ROOT.glob("chat_history_*.jsonl"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(
                    {
                        "created_at": payload.get("created_at"),
                        "question": payload.get("question"),
                        "ok": payload.get("ok"),
                    }
                )
            if len(rows) >= limit:
                return rows
    return rows


INDEX_HTML = """<!doctype html>
<html lang="ka">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SmartSignalHub Assistant</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101418;
      --panel: #171d23;
      --panel-2: #1f2730;
      --panel-3: #141a20;
      --text: #e7edf3;
      --muted: #95a3b3;
      --line: #2b3540;
      --accent: #3fb984;
      --accent-soft: #1c3b2d;
      --danger: #e06666;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
    }
    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    header {
      height: 58px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 22px;
      border-bottom: 1px solid var(--line);
      background: #12171d;
    }
    h1 {
      margin: 0;
      font-size: 16px;
      font-weight: 650;
      letter-spacing: 0;
    }
    .brand {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .subtitle {
      color: var(--muted);
      font-size: 12px;
    }
    .status {
      color: var(--muted);
      font-size: 13px;
    }
    .header-meta {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .mode-pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      color: var(--muted);
      font-size: 12px;
      background: var(--panel);
    }
    .runtime-pill {
      border: 1px solid #284b3a;
      border-radius: 999px;
      padding: 5px 9px;
      color: #a8dbc4;
      font-size: 12px;
      background: #102019;
    }
    main {
      min-height: 0;
      overflow: hidden;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 380px;
    }
    .chat-pane {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: minmax(0, 1fr) auto;
    }
    #messages {
      min-height: 0;
      overflow: auto;
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .message {
      width: min(920px, 100%);
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      white-space: pre-wrap;
      line-height: 1.45;
      font-size: 14px;
    }
    .message:first-child {
      color: var(--muted);
    }
    .user {
      align-self: flex-end;
      background: #18251f;
      border-color: #244535;
    }
    .assistant {
      align-self: flex-start;
      background: var(--panel);
    }
    .error {
      border-color: var(--danger);
    }
    .action-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--line);
    }
    .action-controls button {
      min-width: 96px;
      height: 36px;
      padding: 0 12px;
      font-size: 13px;
    }
    .action-controls .cancel-action {
      background: #2b3540;
      color: var(--text);
    }
    aside {
      border-left: 1px solid var(--line);
      background: #12171d;
      padding: 14px;
      overflow: auto;
    }
    .tools-header {
      margin-bottom: 12px;
    }
    .tools-header h2 {
      margin: 0;
      font-size: 14px;
      font-weight: 750;
    }
    .tools-tabs {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
      margin-bottom: 14px;
    }
    .tool-tab {
      min-width: 0;
      height: 34px;
      padding: 0 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--muted);
      font-size: 12px;
    }
    .tool-tab.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--text);
    }
    .tool-panel {
      display: none;
    }
    .tool-panel.active {
      display: block;
    }
    .side-section {
      margin-bottom: 20px;
    }
    .side-section h2 {
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 750;
    }
    .section-caption {
      margin: -4px 0 10px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .quick-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
    }
    .prompt-group {
      margin-bottom: 16px;
    }
    .prompt-group h3 {
      margin: 0 0 8px;
      color: #c7d3df;
      font-size: 12px;
      font-weight: 750;
    }
    .quick-btn {
      min-width: 0;
      width: 100%;
      height: auto;
      min-height: 38px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--text);
      text-align: left;
      font-size: 12px;
      font-weight: 650;
      line-height: 1.25;
    }
    .quick-btn:hover {
      border-color: #3b7a5a;
      background: #18231d;
    }
    .actions-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 10px;
    }
    .actions-head h2 {
      margin: 0;
      font-size: 13px;
      font-weight: 700;
    }
    .refresh-actions {
      min-width: 64px;
      height: 30px;
      padding: 0 10px;
      font-size: 12px;
      background: #2b3540;
      color: var(--text);
    }
    .action-tabs {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-bottom: 10px;
    }
    .tab-btn {
      min-width: 0;
      height: 30px;
      padding: 0 8px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--muted);
      font-size: 12px;
    }
    .tab-btn.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--text);
    }
    .action-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 10px;
      background: var(--panel);
      font-size: 12px;
      line-height: 1.35;
    }
    .action-card strong {
      display: block;
      margin-bottom: 4px;
      font-size: 13px;
    }
    .action-card .meta {
      color: var(--muted);
      overflow-wrap: anywhere;
    }
    .action-card .command {
      margin-top: 6px;
      padding: 7px;
      border-radius: 6px;
      background: var(--panel-3);
      color: #bfd0df;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px;
      overflow-wrap: anywhere;
    }
    .history-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      margin-bottom: 8px;
      background: var(--panel);
      color: var(--text);
      cursor: pointer;
    }
    .history-card:hover {
      border-color: #3b7a5a;
      background: #18231d;
    }
    .history-card .question {
      font-size: 12px;
      line-height: 1.35;
    }
    .history-card .time {
      margin-top: 5px;
      color: var(--muted);
      font-size: 11px;
    }
    .action-card .row-actions {
      display: flex;
      gap: 6px;
      margin-top: 8px;
    }
    .action-card button {
      min-width: 0;
      height: 30px;
      padding: 0 10px;
      font-size: 12px;
    }
    .status-completed { border-color: #315f48; }
    .status-failed, .status-timeout { border-color: var(--danger); }
    .status-pending { border-color: #7a6a2e; }
    .status-canceled { border-color: #44515e; opacity: 0.78; }
    .composer-wrap {
      border-top: 1px solid var(--line);
      background: #12171d;
      padding: 12px 18px 14px;
    }
    .composer {
      max-width: 1100px;
      margin: 0 auto;
    }
    .composer-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .mode-toggle {
      display: inline-grid;
      grid-template-columns: auto auto;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    .mode-btn {
      min-width: 86px;
      height: 30px;
      padding: 0 10px;
      background: transparent;
      color: var(--muted);
      border-radius: 6px;
      font-size: 12px;
    }
    .mode-btn.active {
      background: var(--accent);
      color: #07120d;
    }
    form {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      margin: 0;
    }
    textarea {
      width: 100%;
      min-height: 48px;
      max-height: 180px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
      color: var(--text);
      padding: 12px;
      font: inherit;
      line-height: 1.35;
    }
    button {
      min-width: 104px;
      height: 48px;
      border: 0;
      border-radius: 8px;
      background: var(--accent);
      color: #07120d;
      font-weight: 700;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.6;
      cursor: wait;
    }
    .hint {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 12px;
    }
    @media (max-width: 640px) {
      header { padding: 0 14px; }
      main { grid-template-columns: 1fr; }
      aside { display: none; }
      #messages { padding: 14px; }
      .composer-top { align-items: flex-start; flex-direction: column; }
      form { grid-template-columns: 1fr; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div class="brand">
        <h1>SmartSignalHub Assistant</h1>
        <div class="subtitle">Project-aware runtime console</div>
      </div>
      <div class="header-meta">
        <div class="mode-pill" id="mode-pill">Mode: Project</div>
        <div class="runtime-pill" id="status">Runtime: local</div>
      </div>
    </header>
    <main>
      <div class="chat-pane">
        <div id="messages">
          <div class="message assistant">Ask in Project mode for SmartSignalHub facts. Use General only for non-project questions.</div>
        </div>
        <div class="composer-wrap">
          <div class="composer">
            <div class="composer-top">
              <div class="mode-toggle" aria-label="Assistant mode">
                <button class="mode-btn active" id="project-mode" type="button">Project</button>
                <button class="mode-btn" id="general-mode" type="button">General</button>
              </div>
              <div class="hint" id="mode-hint">Project mode uses deterministic project/runtime readers.</div>
            </div>
            <form id="ask-form">
              <textarea id="question" placeholder="Ask about signals, capital, positions, diagnostics, tools, docs, or code..." autocomplete="off"></textarea>
              <button id="send" type="submit">Ask</button>
            </form>
          </div>
        </div>
      </div>
      <aside>
        <div class="tools-header">
          <h2>Assistant Tools</h2>
          <div class="section-caption">Use these to fill the chat box. The chat remains the main workspace.</div>
        </div>
        <div class="tools-tabs">
          <button class="tool-tab active" type="button" data-tool-tab="prompts">Prompts</button>
          <button class="tool-tab" type="button" data-tool-tab="actions">Actions</button>
          <button class="tool-tab" type="button" data-tool-tab="history">History</button>
          <button class="tool-tab" type="button" data-tool-tab="docs">Docs</button>
        </div>
        <div class="tool-panel active" id="panel-prompts">
          <div class="prompt-group">
            <h3>Signals</h3>
            <div class="quick-grid">
              <button class="quick-btn" type="button" data-question="What can you tell me about the latest futures signal?">Latest Futures signal</button>
              <button class="quick-btn" type="button" data-question="Why was the latest futures signal denied?">Latest denied reason</button>
              <button class="quick-btn" type="button" data-question="Compare the latest futures signal with the latest spot signal.">Compare Spot vs Futures</button>
            </div>
          </div>
          <div class="prompt-group">
            <h3>Capital</h3>
            <div class="quick-grid">
              <button class="quick-btn" type="button" data-question="Show current spot and futures capital.">Capital snapshot</button>
              <button class="quick-btn" type="button" data-question="Show open positions for spot and futures.">Open positions</button>
              <button class="quick-btn" type="button" data-question="Show trade lifecycle of FUT-000005">Trade lifecycle</button>
            </div>
          </div>
          <div class="prompt-group">
            <h3>Diagnostics</h3>
            <div class="quick-grid">
              <button class="quick-btn" type="button" data-question="What does diagnostics say right now?">Diagnostics summary</button>
              <button class="quick-btn" type="button" data-question="diagnostics full report summary">Full diagnostics</button>
              <button class="quick-btn" type="button" data-question="runtime access coverage ყველა მეტრიკაზე">Runtime coverage</button>
            </div>
          </div>
          <div class="prompt-group">
            <h3>Tools</h3>
            <div class="quick-grid">
              <button class="quick-btn" type="button" data-question="What internal tools can you inspect?">Internal tools</button>
              <button class="quick-btn" type="button" data-question="news generation status">News status</button>
              <button class="quick-btn" type="button" data-question="Public site SEO audit">Public site SEO</button>
            </div>
          </div>
        </div>
        <div class="tool-panel" id="panel-actions">
          <div class="actions-head">
            <h2>Actions</h2>
            <button class="refresh-actions" id="refresh-actions" type="button">Refresh</button>
          </div>
          <div class="section-caption">Actions are not automatic. Pending commands require explicit confirmation.</div>
          <div class="quick-grid side-section">
            <button class="quick-btn" type="button" data-question="Can you run diagnostics?">Prepare diagnostics</button>
            <button class="quick-btn" type="button" data-question="What actions are pending?">Pending actions</button>
          </div>
          <div class="action-tabs">
            <button class="tab-btn active" id="tab-pending" type="button">Pending</button>
            <button class="tab-btn" id="tab-recent" type="button">Recent</button>
          </div>
          <div id="actions-panel">
            <div class="action-card"><span class="meta">No action data loaded.</span></div>
          </div>
        </div>
        <div class="tool-panel" id="panel-history">
          <div class="actions-head">
            <h2>History</h2>
            <button class="refresh-actions" id="refresh-history" type="button">Refresh</button>
          </div>
          <div class="section-caption">Click a past question to place it in the chat box.</div>
          <div id="history-panel">
            <div class="action-card"><span class="meta">No chat history loaded.</span></div>
          </div>
        </div>
        <div class="tool-panel" id="panel-docs">
          <div class="side-section">
            <h2>Docs</h2>
            <div class="section-caption">Shortcuts for active docs and source-aware project questions.</div>
            <div class="quick-grid">
              <button class="quick-btn" type="button" data-question="Search active docs for AI assistant boundaries">AI assistant docs</button>
              <button class="quick-btn" type="button" data-question="Search active docs for futures rules">Futures rules docs</button>
              <button class="quick-btn" type="button" data-question="Search active docs for risk and permissions">Risk docs</button>
              <button class="quick-btn" type="button" data-question="Search active docs for frontend backend boundary">Frontend boundary docs</button>
            </div>
          </div>
        </div>
      </aside>
    </main>
  </div>
  <script>
    const form = document.getElementById('ask-form');
    const input = document.getElementById('question');
    const send = document.getElementById('send');
    const messages = document.getElementById('messages');
    const statusEl = document.getElementById('status');
    const actionsPanel = document.getElementById('actions-panel');
    const refreshActions = document.getElementById('refresh-actions');
    const historyPanel = document.getElementById('history-panel');
    const refreshHistory = document.getElementById('refresh-history');
    const projectMode = document.getElementById('project-mode');
    const generalMode = document.getElementById('general-mode');
    const modePill = document.getElementById('mode-pill');
    const modeHint = document.getElementById('mode-hint');
    const tabPending = document.getElementById('tab-pending');
    const tabRecent = document.getElementById('tab-recent');
    const toolTabs = Array.from(document.querySelectorAll('[data-tool-tab]'));
    const toolPanels = {
      prompts: document.getElementById('panel-prompts'),
      actions: document.getElementById('panel-actions'),
      history: document.getElementById('panel-history'),
      docs: document.getElementById('panel-docs')
    };
    let currentMode = 'project';
    let actionTab = 'pending';
    let cachedActions = { pending: [], latest: [] };

    function setMode(mode) {
      currentMode = mode;
      const general = mode === 'general';
      projectMode.classList.toggle('active', !general);
      generalMode.classList.toggle('active', general);
      modePill.textContent = general ? 'Mode: General' : 'Mode: Project';
      input.placeholder = general
        ? 'Ask a general question. It will be sent with /general...'
        : 'Ask about latest signals, capital, positions, diagnostics, tools, docs, code...';
      modeHint.textContent = general
        ? 'General mode: for non-project questions. Project files/runtime are not used as source of truth.'
        : 'Project mode: answers must come from real project/runtime sources. Enter sends. Shift+Enter adds a line.';
      input.focus();
    }

    function setToolTab(tab) {
      toolTabs.forEach((button) => {
        button.classList.toggle('active', button.getAttribute('data-tool-tab') === tab);
      });
      Object.entries(toolPanels).forEach(([name, panel]) => {
        if (!panel) return;
        panel.classList.toggle('active', name === tab);
      });
      if (tab === 'actions') loadActions();
      if (tab === 'history') loadHistory();
    }

    function setActionTab(tab) {
      actionTab = tab;
      tabPending.classList.toggle('active', tab === 'pending');
      tabRecent.classList.toggle('active', tab === 'recent');
      renderActions();
    }

    function addMessage(text, kind, error = false) {
      const node = document.createElement('div');
      node.className = `message ${kind}${error ? ' error' : ''}`;
      node.textContent = text;
      messages.appendChild(node);
      messages.scrollTop = messages.scrollHeight;
      return node;
    }

    function pendingActionId(text) {
      if (!text.includes('Pending action created')) return '';
      const match = text.match(/Action ID:\\s*([a-f0-9]{12})/i);
      return match ? match[1] : '';
    }

    function addActionControls(messageNode, actionId) {
      const controls = document.createElement('div');
      controls.className = 'action-controls';

      const confirm = document.createElement('button');
      confirm.type = 'button';
      confirm.textContent = 'Confirm';
      confirm.addEventListener('click', () => {
        controls.remove();
        ask(`confirm action ${actionId}`);
      });

      const cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'cancel-action';
      cancel.textContent = 'Cancel';
      cancel.addEventListener('click', () => {
        controls.remove();
        ask(`cancel action ${actionId}`);
      });

      controls.appendChild(confirm);
      controls.appendChild(cancel);
      messageNode.appendChild(controls);
      messages.scrollTop = messages.scrollHeight;
    }

    function actionRowTitle(row) {
      return row.title || row.action_key || 'action';
    }

    function formatActionMeta(row, status) {
      const id = row.action_id || '--';
      const time = row.timestamp_utc || '--';
      return `${status.toUpperCase()} | ${id} | ${time}`;
    }

    function renderActionRow(row, pending = false) {
      const card = document.createElement('div');
      const status = String(row.status || (pending ? 'pending' : 'unknown'));
      card.className = `action-card status-${status}`;
      const title = document.createElement('strong');
      title.textContent = actionRowTitle(row);
      const meta = document.createElement('div');
      meta.className = 'meta';
      const command = Array.isArray(row.resolved_command) ? row.resolved_command.join(' ') : '';
      meta.textContent = formatActionMeta(row, status);
      card.appendChild(title);
      card.appendChild(meta);
      if (command) {
        const commandNode = document.createElement('div');
        commandNode.className = 'command';
        commandNode.textContent = command;
        card.appendChild(commandNode);
      }
      if (pending && row.action_id) {
        const controls = document.createElement('div');
        controls.className = 'row-actions';
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.textContent = 'Confirm';
        confirm.addEventListener('click', () => ask(`confirm action ${row.action_id}`).then(loadActions));
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'cancel-action';
        cancel.textContent = 'Cancel';
        cancel.addEventListener('click', () => ask(`cancel action ${row.action_id}`).then(loadActions));
        controls.appendChild(confirm);
        controls.appendChild(cancel);
        card.appendChild(controls);
      }
      return card;
    }

    function renderActions() {
      actionsPanel.innerHTML = '';
      const pendingRows = Array.isArray(cachedActions.pending) ? cachedActions.pending : [];
      const latestRows = Array.isArray(cachedActions.latest) ? cachedActions.latest.slice().reverse() : [];
      tabPending.textContent = `Pending (${pendingRows.length})`;
      tabRecent.textContent = `Recent (${latestRows.length})`;
      const rows = actionTab === 'pending' ? pendingRows : latestRows.slice(0, 12);
      if (!rows.length) {
        const empty = document.createElement('div');
        empty.className = 'action-card';
        empty.innerHTML = actionTab === 'pending'
          ? '<span class="meta">No pending actions.</span>'
          : '<span class="meta">No recent action history yet.</span>';
        actionsPanel.appendChild(empty);
        return;
      }
      rows.forEach((row) => actionsPanel.appendChild(renderActionRow(row, actionTab === 'pending')));
    }

    async function loadActions() {
      try {
        const response = await fetch('/api/actions');
        const payload = await response.json();
        cachedActions = {
          pending: Array.isArray(payload.pending) ? payload.pending : [],
          latest: Array.isArray(payload.latest) ? payload.latest : []
        };
        renderActions();
      } catch (error) {
        actionsPanel.innerHTML = '';
        const node = document.createElement('div');
        node.className = 'action-card status-failed';
        node.textContent = `Action load failed: ${error}`;
        actionsPanel.appendChild(node);
      }
    }

    function renderHistory(rows) {
      historyPanel.innerHTML = '';
      if (!Array.isArray(rows) || !rows.length) {
        const empty = document.createElement('div');
        empty.className = 'action-card';
        empty.innerHTML = '<span class="meta">No chat history yet.</span>';
        historyPanel.appendChild(empty);
        return;
      }
      rows.slice(0, 8).forEach((row) => {
        const card = document.createElement('div');
        card.className = 'history-card';
        const question = document.createElement('div');
        question.className = 'question';
        question.textContent = row.question || '--';
        const time = document.createElement('div');
        time.className = 'time';
        time.textContent = `${row.created_at || '--'}${row.ok === false ? ' | failed' : ''}`;
        card.appendChild(question);
        card.appendChild(time);
        card.addEventListener('click', () => {
          input.value = row.question || '';
          input.focus();
        });
        historyPanel.appendChild(card);
      });
    }

    async function loadHistory() {
      try {
        const response = await fetch('/api/history');
        const payload = await response.json();
        renderHistory(Array.isArray(payload.latest) ? payload.latest : []);
      } catch (error) {
        historyPanel.innerHTML = '';
        const node = document.createElement('div');
        node.className = 'action-card status-failed';
        node.textContent = `History load failed: ${error}`;
        historyPanel.appendChild(node);
      }
    }

    async function ask(question) {
      const rawQuestion = question;
      if (currentMode === 'general' && !question.trim().startsWith('/general')) {
        question = `/general ${question}`;
      }
      send.disabled = true;
      statusEl.textContent = 'Runtime: thinking';
      addMessage(rawQuestion, 'user');
      try {
        const response = await fetch('/api/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question })
        });
        const payload = await response.json();
        const answer = payload.answer || payload.error || 'No answer.';
        const node = addMessage(answer, 'assistant', !response.ok || payload.ok === false);
        const actionId = pendingActionId(answer);
        if (actionId) addActionControls(node, actionId);
        loadActions();
        loadHistory();
      } catch (error) {
        addMessage(`Request failed: ${error}`, 'assistant', true);
      } finally {
        send.disabled = false;
        statusEl.textContent = 'Runtime: local';
        input.focus();
      }
    }

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const question = input.value.trim();
      if (!question) return;
      input.value = '';
      ask(question);
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });
    projectMode.addEventListener('click', () => setMode('project'));
    generalMode.addEventListener('click', () => setMode('general'));
    toolTabs.forEach((button) => {
      button.addEventListener('click', () => setToolTab(button.getAttribute('data-tool-tab') || 'prompts'));
    });
    tabPending.addEventListener('click', () => setActionTab('pending'));
    tabRecent.addEventListener('click', () => setActionTab('recent'));
    document.querySelectorAll('[data-question]').forEach((button) => {
      button.addEventListener('click', () => {
        const question = button.getAttribute('data-question') || '';
        if (!question) return;
        input.value = question;
        input.focus();
      });
    });
    refreshActions.addEventListener('click', loadActions);
    refreshHistory.addEventListener('click', loadHistory);
    setMode('project');
    loadActions();
    loadHistory();
  </script>
</body>
</html>
"""
