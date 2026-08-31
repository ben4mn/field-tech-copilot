const token = document.querySelector('meta[name="fieldtech-token"]').content;

const state = {
  cases: [],
  current: null,
};

const el = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

async function api(path, options = {}) {
  const headers = {
    "X-Fieldtech-Token": token,
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const message = (await response.text()) || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response;
}

function setBusy(active) {
  el("busy").classList.toggle("hidden", !active);
}

function toast(message) {
  const node = el("toast");
  node.textContent = message;
  node.classList.remove("hidden");
  window.setTimeout(() => node.classList.add("hidden"), 3500);
}

async function withBusy(work) {
  setBusy(true);
  try {
    return await work();
  } catch (error) {
    toast(error.message);
    throw error;
  } finally {
    setBusy(false);
  }
}

async function loadHealth() {
  try {
    const response = await api("/api/health");
    const health = await response.json();
    const node = el("health");
    const localAiReady = health.diagnostic_capable && health.model_ready;
    node.className = `health ${localAiReady || health.reasoning_mode === "demo_fixture" ? "health-ready" : "health-degraded"}`;
    node.textContent = localAiReady
      ? `Local AI ready · ${health.model} · ${health.knowledge_cards} cards`
      : health.reasoning_mode === "demo_fixture"
        ? `Offline notebook ready · demo reasoning only · ${health.knowledge_cards} cards`
        : `Needs attention · ${health.model_message}`;
    el("quit-app").classList.toggle("hidden", !health.can_quit);
  } catch (error) {
    el("health").className = "health health-degraded";
    el("health").textContent = "Local stack unavailable";
  }
}

async function loadCases(selectId = null) {
  const response = await api("/api/cases");
  state.cases = await response.json();
  renderCaseList();
  const target = selectId || state.current?.id;
  if (target) {
    const current = state.cases.find((item) => item.id === target);
    if (current) showCase(current);
  }
}

function renderCaseList() {
  const list = el("case-list");
  if (!state.cases.length) {
    list.innerHTML = '<p class="muted sidebar-empty">No cases yet.</p>';
    return;
  }
  list.innerHTML = state.cases
    .map(
      (item) => `
        <button class="case-list-item ${state.current?.id === item.id ? "active" : ""}" data-case-id="${escapeHtml(item.id)}" type="button">
          <span class="case-list-title">${escapeHtml(item.title)}</span>
          <span class="case-list-meta"><span class="status-dot ${escapeHtml(item.status)}"></span>${escapeHtml(item.status)} · ${escapeHtml(formatDate(item.updated_at))}</span>
        </button>
      `,
    )
    .join("");
  list.querySelectorAll("[data-case-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = state.cases.find((candidate) => candidate.id === button.dataset.caseId);
      if (item) showCase(item);
    });
  });
}

function showCase(item) {
  state.current = item;
  el("empty-state").classList.add("hidden");
  el("case-view").classList.remove("hidden");
  el("view-title").textContent = item.title;
  el("view-complaint").textContent = item.complaint;
  el("close-case").disabled = item.status === "closed";
  renderCaseList();
  renderCase(item);
}

function renderCase(item) {
  const error = el("case-error");
  error.classList.toggle("hidden", !item.last_error);
  error.textContent = item.last_error || "";

  const assessment = item.assessment;
  el("assessment-card").innerHTML = assessment
    ? `
      <div class="panel-heading">
        <div><div class="eyebrow">Current assessment</div><h2>${escapeHtml(assessment.disposition.replaceAll("_", " "))}</h2></div>
        <span class="disposition">${escapeHtml(formatDate(assessment.generated_at))}</span>
      </div>
      <p class="assessment-summary">${escapeHtml(assessment.summary)}</p>
      <p class="technician-message">${escapeHtml(assessment.technician_message)}</p>
      ${assessment.uncertainties?.length ? `<div class="uncertainties"><strong>Still uncertain</strong><ul>${assessment.uncertainties.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul></div>` : ""}
    `
    : '<div class="eyebrow">Current assessment</div><p class="muted">No validated assessment yet.</p>';

  renderNextAction(item);
  renderHypotheses(assessment?.hypotheses || []);
  renderCitations(assessment?.citations || []);
  renderTimeline(item);
  renderDevice(item.device);
}

function renderNextAction(item) {
  const node = el("next-action-card");
  const assessment = item.assessment;
  if (assessment?.next_test) {
    const test = assessment.next_test;
    node.innerHTML = `
      <div class="next-label"><span>Next best test</span><span class="risk risk-${escapeHtml(test.risk)}">${escapeHtml(test.risk)}</span></div>
      <h2>${escapeHtml(test.title)}</h2>
      <p>${escapeHtml(test.rationale)}</p>
      <ol class="steps">${test.instructions.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
      ${test.expected_results?.length ? `<div class="expected"><strong>Useful result branches</strong><ul>${test.expected_results.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul></div>` : ""}
      ${test.repeat_reason ? `<div class="alert alert-warning"><strong>Repeat requested:</strong> ${escapeHtml(test.repeat_reason)}</div>` : ""}
      ${test.requires_confirmation ? `<div class="alert alert-warning"><strong>Confirmation required.</strong> Review prerequisites and rollback before performing this step.</div>` : ""}
      <form id="test-result-form" class="test-result-form">
        <label>What happened?<textarea id="test-result" required rows="3" maxlength="8000" placeholder="Record the observed result in normal language."></textarea></label>
        <div class="test-result-controls">
          <label>Outcome<select id="test-outcome"><option value="other">Other</option><option value="pass">Pass / expected</option><option value="fail">Fail / abnormal</option><option value="inconclusive">Inconclusive</option><option value="blocked">Blocked</option></select></label>
          ${test.requires_confirmation ? '<label class="confirm"><input id="test-confirmed" type="checkbox"> I reviewed and confirmed this risky step</label>' : ""}
          <button class="primary" type="submit">Record result &amp; reassess</button>
        </div>
      </form>
    `;
    el("test-result-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      await completeCurrentTest(test);
    });
    return;
  }

  if (assessment?.intervention) {
    const action = assessment.intervention;
    node.innerHTML = `
      <div class="next-label"><span>Proposed intervention</span><span class="risk risk-${escapeHtml(action.risk)}">${escapeHtml(action.risk)}</span></div>
      <h2>${escapeHtml(action.title)}</h2>
      <p>${escapeHtml(action.rationale)}</p>
      <ol class="steps">${action.steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
      <div class="expected"><strong>Verify afterward</strong><ul>${action.verification.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul></div>
      ${action.requires_confirmation ? '<div class="alert alert-warning"><strong>Technician confirmation required.</strong> The app will not execute this intervention.</div>' : ""}
    `;
    return;
  }

  node.innerHTML = `
    <div class="next-label"><span>No action proposed</span></div>
    <h2>Record more evidence or escalate.</h2>
    <p>The latest validated assessment did not provide a safe next test or supported intervention.</p>
  `;
}

function renderHypotheses(items) {
  el("hypotheses").innerHTML = items.length
    ? items
        .map(
          (item) => `
            <article class="hypothesis">
              <div><span class="hypothesis-status status-${escapeHtml(item.status)}">${escapeHtml(item.status)}</span><span class="confidence">${escapeHtml(item.confidence)}</span></div>
              <strong>${escapeHtml(item.label)}</strong>
              ${item.evidence_for?.length ? `<p>For: ${escapeHtml(item.evidence_for.join(" · "))}</p>` : ""}
              ${item.evidence_against?.length ? `<p>Against: ${escapeHtml(item.evidence_against.join(" · "))}</p>` : ""}
            </article>
          `,
        )
        .join("")
    : '<p class="muted">No hypotheses yet.</p>';
}

function renderCitations(items) {
  el("citations").innerHTML = items.length
    ? items
        .map((item) => {
          const url = safeUrl(item.source_url);
          const title = escapeHtml(item.title);
          return `
            <article class="citation">
              ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${title}</a>` : `<strong>${title}</strong>`}
              <span>${escapeHtml(item.source_title)}</span>
              <span>Verified ${escapeHtml(item.verified_at || "unknown")}</span>
            </article>
          `;
        })
        .join("")
    : '<p class="muted">No local sources cited.</p>';
}

function renderTimeline(item) {
  const events = [
    ...item.observations.map((value) => ({
      at: value.created_at,
      label: "Observation",
      title: value.text,
      detail: value.source,
    })),
    ...item.completed_tests.map((value) => ({
      at: value.completed_at,
      label: "Test completed",
      title: value.proposal.title,
      detail: `${value.outcome}: ${value.result}`,
    })),
  ].sort((a, b) => new Date(b.at) - new Date(a.at));
  el("timeline").innerHTML = events.length
    ? events
        .map(
          (event) => `
            <article class="timeline-item">
              <div class="timeline-marker"></div>
              <div><span>${escapeHtml(event.label)} · ${escapeHtml(formatDate(event.at))}</span><strong>${escapeHtml(event.title)}</strong><p>${escapeHtml(event.detail)}</p></div>
            </article>
          `,
        )
        .join("")
    : '<p class="muted">No observations or completed tests yet.</p>';
}

function renderDevice(device) {
  const values = [
    ["Manufacturer", device.manufacturer],
    ["Model", device.model],
    ["OS", device.operating_system],
    ["Notes", device.notes],
  ].filter(([, value]) => value);
  el("device-details").innerHTML = values.length
    ? values.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")
    : '<p class="muted">Not recorded.</p>';
}

async function completeCurrentTest(test) {
  const body = {
    result: el("test-result").value.trim(),
    outcome: el("test-outcome").value,
    confirmed: el("test-confirmed")?.checked || false,
  };
  const response = await withBusy(() =>
    api(`/api/cases/${state.current.id}/tests/${test.id}/complete`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  );
  showCase(await response.json());
  await loadCases(state.current.id);
}

function toggleNewCase(show = null) {
  const form = el("new-case-form");
  const shouldShow = show ?? form.classList.contains("hidden");
  form.classList.toggle("hidden", !shouldShow);
  if (shouldShow) el("case-complaint").focus();
}

el("new-case-toggle").addEventListener("click", () => toggleNewCase());
el("empty-new-case").addEventListener("click", () => toggleNewCase(true));
el("new-case-cancel").addEventListener("click", () => toggleNewCase(false));
el("reload-cases").addEventListener("click", () => withBusy(() => loadCases()));
el("quit-app").addEventListener("click", async () => {
  el("quit-app").disabled = true;
  try {
    await api("/api/system/shutdown", { method: "POST" });
    document.body.innerHTML = `
      <main class="stopped-screen">
        <div class="brand-mark">FT</div>
        <h1>Field Tech Copilot has stopped.</h1>
        <p>You can close this browser tab. Your local cases are saved.</p>
      </main>`;
  } catch (error) {
    el("quit-app").disabled = false;
    toast(error.message);
  }
});

el("new-case-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const deviceText = el("case-device").value.trim();
  const response = await withBusy(() =>
    api("/api/cases", {
      method: "POST",
      body: JSON.stringify({
        title: el("case-title").value.trim() || null,
        complaint: el("case-complaint").value.trim(),
        device: { notes: deviceText || null },
      }),
    }),
  );
  const item = await response.json();
  event.target.reset();
  toggleNewCase(false);
  await loadCases(item.id);
});

el("observation-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await withBusy(() =>
    api(`/api/cases/${state.current.id}/observations`, {
      method: "POST",
      body: JSON.stringify({ text: el("observation-text").value.trim() }),
    }),
  );
  el("observation-text").value = "";
  showCase(await response.json());
  await loadCases(state.current.id);
});

el("refresh-case").addEventListener("click", async () => {
  const response = await withBusy(() =>
    api(`/api/cases/${state.current.id}/refresh`, { method: "POST" }),
  );
  showCase(await response.json());
  await loadCases(state.current.id);
});

el("close-case").addEventListener("click", async () => {
  const response = await withBusy(() =>
    api(`/api/cases/${state.current.id}/close`, { method: "POST" }),
  );
  showCase(await response.json());
  await loadCases(state.current.id);
});

el("delete-case").addEventListener("click", async () => {
  if (!window.confirm("Permanently delete this local case and its event history?")) return;
  await withBusy(() => api(`/api/cases/${state.current.id}`, { method: "DELETE" }));
  state.current = null;
  el("case-view").classList.add("hidden");
  el("empty-state").classList.remove("hidden");
  await loadCases();
});

el("export-case").addEventListener("click", async () => {
  const response = await api(`/api/cases/${state.current.id}/export`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `fieldtech-${state.current.id}.md`;
  link.click();
  URL.revokeObjectURL(url);
});

Promise.all([loadHealth(), loadCases()]).catch((error) => toast(error.message));
