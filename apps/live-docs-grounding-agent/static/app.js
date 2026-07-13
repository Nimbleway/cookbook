// Live Docs Grounding Agent — frontend. Talks only to the /api/* endpoints
// in server.py, which themselves just orchestrate agent.py's existing
// Task Agents API client. No Nimble API calls happen directly from here.

const API = "";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getJSON(path) {
  const resp = await fetch(API + path);
  if (!resp.ok) throw await responseError(resp);
  return resp.json();
}

async function postJSON(path, body) {
  const resp = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!resp.ok) throw await responseError(resp);
  return resp.json();
}

async function deleteJSON(path) {
  const resp = await fetch(API + path, { method: "DELETE" });
  if (!resp.ok) throw await responseError(resp);
  return resp.json();
}

async function responseError(resp) {
  let detail = resp.statusText;
  try {
    const body = await resp.json();
    detail = body.detail || detail;
  } catch (_) {
    /* ignore */
  }
  return new Error(detail);
}

// ============================================================================
// Markdown-lite answer rendering (mirrors agent.py's terminal renderer)
// ============================================================================

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function boldInline(escaped) {
  return escaped.replace(/\*\*(.+?)\*\*/g, (_, inner) => `<strong>${inner}</strong>`);
}

const MARKER_PATTERNS = [
  { all: /\*\*\d+\.\s/g, one: /^\*\*\d+\.\s/ },
  { all: /\(\d+\)\s/g, one: /^\(\d+\)\s/ },
];

function normalizeAnswer(text) {
  if (!text) return "";
  if (text.includes("\n")) return text;
  for (const { all, one } of MARKER_PATTERNS) {
    const matches = [...text.matchAll(all)];
    if (matches.length >= 2) {
      const pieces = [];
      let last = 0;
      for (const m of matches) {
        if (m.index > last) pieces.push(text.slice(last, m.index));
        last = m.index;
      }
      pieces.push(text.slice(last));
      const cleaned = pieces.map((p) => p.trim()).filter(Boolean);
      let intro = "";
      let items = cleaned;
      if (cleaned.length && !one.test(cleaned[0])) {
        intro = cleaned[0];
        items = cleaned.slice(1);
      }
      const body = items.join("\n");
      return intro ? `${intro}\n\n${body}` : body;
    }
  }
  return text;
}

function formatAnswerLine(stripped) {
  let m = stripped.match(/^\*\*(\d+)\.\s*(.+?)\*\*\s*(.*)$/);
  if (m) {
    const [, num, label, rest] = m;
    const head = `<strong>${escapeHtml(num)}. ${escapeHtml(label.trim())}</strong>`;
    const restHtml = rest.trim() ? boldInline(escapeHtml(rest.trim())) : "";
    return { html: restHtml ? `${head}  ${restHtml}` : head, isItem: true };
  }
  m = stripped.match(/^(\d+)[.)]\s+(.*)$/);
  if (m) return { html: `${escapeHtml(m[1])}. ${boldInline(escapeHtml(m[2].trim()))}`, isItem: true };

  m = stripped.match(/^\((\d+)\)\s+(.*)$/);
  if (m) return { html: `${escapeHtml(m[1])}. ${boldInline(escapeHtml(m[2].trim()))}`, isItem: true };

  m = stripped.match(/^[-*•]\s+(.*)$/);
  if (m) return { html: `• ${boldInline(escapeHtml(m[1].trim()))}`, isItem: true };

  return { html: boldInline(escapeHtml(stripped)), isItem: false };
}

function renderAnswerHtml(answer) {
  const normalized = normalizeAnswer(answer || "");
  const lines = normalized.split("\n");
  let html = "";
  let inList = false;
  for (const raw of lines) {
    const stripped = raw.trim();
    if (!stripped) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      continue;
    }
    const { html: lineHtml, isItem } = formatAnswerLine(stripped);
    if (isItem) {
      if (!inList) {
        html += '<ul class="answer-list">';
        inList = true;
      }
      html += `<li>${lineHtml}</li>`;
    } else {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += `<p>${lineHtml}</p>`;
    }
  }
  if (inList) html += "</ul>";
  return html || '<p class="dim">(no answer returned)</p>';
}

// ============================================================================
// Onboarding
// ============================================================================

const onboardingEl = document.getElementById("onboarding");
const stepsEl = document.getElementById("onboardingSteps");
const keyFormEl = document.getElementById("keyForm");
const keyInputEl = document.getElementById("keyInput");
const keySubmitBtn = document.getElementById("keySubmitBtn");
const keyErrorEl = document.getElementById("keyError");
const mainAppEl = document.getElementById("mainApp");

function addStep(label) {
  const li = document.createElement("li");
  li.className = "step active";
  li.innerHTML = `<span class="step-icon"></span><span class="step-label">${escapeHtml(label)}</span>`;
  stepsEl.appendChild(li);
  return li;
}

function completeStep(li, finalLabel) {
  if (finalLabel) li.querySelector(".step-label").textContent = finalLabel;
  li.classList.remove("active");
  li.classList.add("done");
}

async function withMinDelay(promise, minMs) {
  const [result] = await Promise.all([promise, sleep(minMs)]);
  return result;
}

async function promptForKey() {
  keyFormEl.classList.remove("hidden");
  keyErrorEl.classList.add("hidden");
  keyInputEl.value = "";
  keyInputEl.focus();

  return new Promise((resolve) => {
    async function submit() {
      const apiKey = keyInputEl.value.trim();
      if (!apiKey) return;
      keySubmitBtn.disabled = true;
      keySubmitBtn.textContent = "Validating…";
      keyErrorEl.classList.add("hidden");
      try {
        const result = await withMinDelay(postJSON("/api/setup/key", { api_key: apiKey }), 400);
        if (result.valid) {
          keyFormEl.classList.add("hidden");
          keySubmitBtn.disabled = false;
          keySubmitBtn.textContent = "Continue";
          resolve();
        } else {
          keyErrorEl.textContent = result.message;
          keyErrorEl.classList.remove("hidden");
          keySubmitBtn.disabled = false;
          keySubmitBtn.textContent = "Continue";
        }
      } catch (exc) {
        keyErrorEl.textContent = `Unexpected error: ${exc.message}`;
        keyErrorEl.classList.remove("hidden");
        keySubmitBtn.disabled = false;
        keySubmitBtn.textContent = "Continue";
      }
    }
    keySubmitBtn.onclick = submit;
    keyInputEl.onkeydown = (e) => {
      if (e.key === "Enter") submit();
    };
  });
}

let agentConfigCache = null;

async function runOnboarding() {
  stepsEl.innerHTML = "";
  onboardingEl.classList.remove("hidden", "fade-out");

  const status = await getJSON("/api/setup/status");

  if (status.has_key && status.has_agent) {
    // Returning user — quick reconnect beat instead of an instant jump cut.
    const step = addStep("Reconnecting to existing agent…");
    await sleep(500);
    completeStep(step, `Reconnected to ${status.agent_name}`);
    agentConfigCache = status;
    await sleep(350);
    finishOnboarding(status);
    return;
  }

  let step = addStep(status.has_key ? `Found existing API key (...${status.key_suffix})` : "Checking for a saved API key…");
  await sleep(450);
  if (status.has_key) {
    completeStep(step);
  } else {
    completeStep(step, "No API key found");
    await promptForKey();
    const validated = addStep("Key validated");
    await sleep(300);
    completeStep(validated);
  }

  const agentStep = addStep(status.has_agent ? "Reconnecting to existing agent…" : "Creating agent…");
  let agentResult;
  try {
    agentResult = await withMinDelay(postJSON("/api/setup/agent", {}), 700);
  } catch (exc) {
    completeStep(agentStep, `Setup failed: ${exc.message}`);
    return;
  }
  completeStep(agentStep, agentResult.created ? `Created agent: ${agentResult.agent_name}` : `Connected to agent: ${agentResult.agent_name}`);

  const readyStep = addStep("Ready.");
  await sleep(350);
  completeStep(readyStep);

  const finalStatus = await getJSON("/api/setup/status");
  agentConfigCache = finalStatus;
  await sleep(450);
  finishOnboarding(finalStatus);
}

function finishOnboarding(status) {
  onboardingEl.classList.add("fade-out");
  setTimeout(() => {
    onboardingEl.classList.add("hidden");
    showMainApp(status);
  }, 300);
}

// ============================================================================
// Main app
// ============================================================================

const heroDescriptionEl = document.getElementById("heroDescription");
const heroSubtitleEl = document.getElementById("heroSubtitle");
const chipsEl = document.getElementById("chips");
const questionInputEl = document.getElementById("questionInput");
const askBtn = document.getElementById("askBtn");
const threadEl = document.getElementById("thread");
const cardTemplate = document.getElementById("cardTemplate");

function showMainApp(status) {
  mainAppEl.classList.remove("hidden");
  if (status.description) heroDescriptionEl.textContent = status.description;
  heroSubtitleEl.textContent = `Powered by the Nimble Task Agents API — effort: ${status.effort || "unknown"}`;

  chipsEl.innerHTML = "";
  for (const q of status.suggested_questions || []) {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = q;
    chip.onclick = () => {
      questionInputEl.value = q;
      questionInputEl.focus();
    };
    chipsEl.appendChild(chip);
  }

  requestAnimationFrame(() => mainAppEl.classList.add("in"));
}

function autoResize() {
  questionInputEl.style.height = "auto";
  questionInputEl.style.height = Math.min(questionInputEl.scrollHeight, 220) + "px";
}
questionInputEl.addEventListener("input", autoResize);

async function submitQuestion() {
  const question = questionInputEl.value.trim();
  if (!question) return;
  askBtn.disabled = true;
  questionInputEl.value = "";
  autoResize();

  const card = cardTemplate.content.firstElementChild.cloneNode(true);
  card.querySelector(".card-question").textContent = question;
  threadEl.appendChild(card);
  card.scrollIntoView({ behavior: "smooth", block: "start" });

  const loadingEl = card.querySelector(".card-loading");
  const statusEl = card.querySelector(".loading-status");
  const cancelBtn = card.querySelector(".cancel-btn");
  const resultEl = card.querySelector(".card-result");
  const errorEl = card.querySelector(".card-error");

  try {
    const { run_id } = await postJSON("/api/run", { question });
    cancelBtn.onclick = async () => {
      cancelBtn.disabled = true;
      cancelBtn.textContent = "Cancelling…";
      try {
        await postJSON(`/api/run/${run_id}/cancel`, {});
      } catch (_) {
        /* ignore — polling below will surface the final state */
      }
    };

    await pollRun(run_id, statusEl);

    const final = await getJSON(`/api/run/${run_id}`);
    if (final.status === "completed") {
      const { result } = await getJSON(`/api/run/${run_id}/result`);
      renderResult(resultEl, result);
      loadingEl.remove();
      resultEl.classList.remove("hidden");
      requestAnimationFrame(() => resultEl.classList.add("in"));
    } else if (final.status === "cancelled") {
      loadingEl.remove();
      errorEl.textContent = "Cancelled.";
      errorEl.classList.remove("hidden");
    } else {
      loadingEl.remove();
      errorEl.textContent = final.error || `Run ended with status=${final.status}`;
      errorEl.classList.remove("hidden");
    }
  } catch (exc) {
    loadingEl.remove();
    errorEl.textContent = `Unexpected error: ${exc.message}`;
    errorEl.classList.remove("hidden");
  } finally {
    askBtn.disabled = false;
    loadHistory();
  }
}

async function pollRun(runId, statusEl) {
  const terminal = new Set(["completed", "failed", "cancelled"]);
  while (true) {
    const state = await getJSON(`/api/run/${runId}`);
    statusEl.textContent = formatElapsed(state.elapsed) + " — " + state.status;
    if (terminal.has(state.status)) return;
    await sleep(1500);
  }
}

function formatElapsed(seconds) {
  const s = Math.floor(seconds || 0);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return m > 0 ? `${m}m${String(rem).padStart(2, "0")}s` : `${s}s`;
}

function renderResult(resultEl, result) {
  const library = result.library || "unknown";
  const version = result.version ? ` · ${result.version}` : "";
  resultEl.querySelector(".result-library").textContent = `📦 ${library}${version}`;
  resultEl.querySelector(".result-answer").innerHTML = renderAnswerHtml(result.answer);

  const codeWrap = resultEl.querySelector(".result-code-wrap");
  const codeEl = resultEl.querySelector(".result-code");
  if (result.code_snippet && result.code_snippet.trim()) {
    codeEl.textContent = result.code_snippet;
    codeWrap.classList.remove("hidden");
  } else {
    codeWrap.classList.add("hidden");
  }

  const citationsEl = resultEl.querySelector(".result-citations");
  citationsEl.innerHTML = "";
  const citations = result.citation_urls || [];
  if (citations.length) {
    citations.forEach((url, i) => {
      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = `[${i + 1}] ${url}`;
      citationsEl.appendChild(a);
    });
  } else {
    citationsEl.innerHTML = '<span class="dim">(no citations found)</span>';
  }
}

askBtn.addEventListener("click", submitQuestion);
questionInputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submitQuestion();
  }
});

// ============================================================================
// History panel
// ============================================================================

const historyToggleBtn = document.getElementById("historyToggleBtn");
const closeHistoryBtn = document.getElementById("closeHistoryBtn");
const historyPanel = document.getElementById("historyPanel");
const historyOverlay = document.getElementById("historyOverlay");
const historyList = document.getElementById("historyList");

function openHistory() {
  historyPanel.classList.add("open");
  historyOverlay.classList.add("open");
  loadHistory();
}

function closeHistory() {
  historyPanel.classList.remove("open");
  historyOverlay.classList.remove("open");
}

historyToggleBtn.addEventListener("click", openHistory);
closeHistoryBtn.addEventListener("click", closeHistory);
historyOverlay.addEventListener("click", closeHistory);

async function loadHistory() {
  let entries = [];
  try {
    entries = await getJSON("/api/history");
  } catch (_) {
    return;
  }
  historyList.innerHTML = "";
  if (!entries.length) {
    historyList.innerHTML = '<div class="history-empty">No questions asked yet.</div>';
    return;
  }
  for (const entry of entries) {
    const item = document.createElement("div");
    item.className = "history-item";
    item.innerHTML = `
      <div class="history-item-body">
        <div class="history-item-question">${escapeHtml(entry.question || "")}</div>
        <div class="history-item-meta">${escapeHtml(entry.library || "?")} · ${escapeHtml(entry.timestamp || "")}</div>
      </div>
      <button class="history-item-delete" title="Delete">🗑</button>
    `;
    item.querySelector(".history-item-body").onclick = () => viewHistoryEntry(entry.run_id);
    item.querySelector(".history-item-delete").onclick = async (e) => {
      e.stopPropagation();
      try {
        await deleteJSON(`/api/history/${entry.run_id}`);
        loadHistory();
      } catch (exc) {
        alert(`Could not delete: ${exc.message}`);
      }
    };
    historyList.appendChild(item);
  }
}

async function viewHistoryEntry(runId) {
  let entry;
  try {
    entry = await getJSON(`/api/history/${runId}`);
  } catch (exc) {
    alert(`Could not load entry: ${exc.message}`);
    return;
  }
  closeHistory();

  const card = cardTemplate.content.firstElementChild.cloneNode(true);
  card.querySelector(".card-question").textContent = entry.question;
  card.querySelector(".card-loading").remove();
  const resultEl = card.querySelector(".card-result");
  renderResult(resultEl, entry.result);
  resultEl.classList.remove("hidden");
  threadEl.appendChild(card);
  requestAnimationFrame(() => resultEl.classList.add("in"));
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ============================================================================
// Settings menu
// ============================================================================

const settingsBtn = document.getElementById("settingsBtn");
const settingsMenu = document.getElementById("settingsMenu");
const rerunSetupBtn = document.getElementById("rerunSetupBtn");

settingsBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  settingsMenu.classList.toggle("open");
});
document.addEventListener("click", () => settingsMenu.classList.remove("open"));

rerunSetupBtn.addEventListener("click", async () => {
  settingsMenu.classList.remove("open");
  await postJSON("/api/setup/reset", {});
  mainAppEl.classList.remove("in");
  mainAppEl.classList.add("hidden");
  runOnboarding();
});

// ============================================================================
// Boot
// ============================================================================

runOnboarding();
