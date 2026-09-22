// Vanilla JS -- no build step, no framework. Every value that came from the
// uploaded CSV (theme labels, keywords, quotes, notes) is written to the DOM
// with textContent, never innerHTML, so a hostile CSV cell can't inject markup.
"use strict";

const API_BASE = "/api";
let currentSession = null;

const uploadForm = document.getElementById("upload-form");
const csvInput = document.getElementById("csv-input");
const uploadStatus = document.getElementById("upload-status");
const resultsSection = document.getElementById("results-section");
const themesList = document.getElementById("themes-list");
const opportunitiesList = document.getElementById("opportunities-list");
const generateBriefBtn = document.getElementById("generate-brief");
const briefOutput = document.getElementById("brief-output");
const downloadBriefLink = document.getElementById("download-brief");

function setStatus(message, kind) {
  uploadStatus.textContent = message;
  uploadStatus.className = "status" + (kind ? " " + kind : "");
}

function errorMessageFrom(body, fallback) {
  // Our own HTTPException(...) calls send {"detail": "a plain string"}.
  // FastAPI's built-in 422s (e.g. from a Pydantic field_validator) send
  // {"detail": [{"msg": "...", "loc": [...], ...}, ...]} instead -- without
  // this branch that array stringifies to the useless "[object Object]".
  if (!body || body.detail === undefined || body.detail === null) return fallback;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail) && body.detail.length && body.detail[0].msg) {
    return body.detail[0].msg;
  }
  return fallback;
}

async function apiFetch(path, options) {
  const response = await fetch(API_BASE + path, options);
  let body = null;
  try {
    body = await response.json();
  } catch (err) {
    // No JSON body (or a network-level failure) -- fall through to statusText.
  }
  if (!response.ok) {
    throw new Error(errorMessageFrom(body, response.statusText));
  }
  return body;
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = csvInput.files[0];
  if (!file) return;

  const submitButton = uploadForm.querySelector("button");
  setStatus("Analyzing...", "");
  submitButton.disabled = true;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const session = await apiFetch("/sessions", { method: "POST", body: formData });
    currentSession = session;
    setStatus(
      `Found ${session.themes.length} theme(s) across ${session.total_feedback_items} feedback item(s).`,
      "ok"
    );
    render(session);
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    submitButton.disabled = false;
  }
});

function render(session) {
  resultsSection.classList.remove("hidden");
  renderThemes(session);
  renderOpportunities(session);
  briefOutput.classList.add("hidden");
  downloadBriefLink.classList.add("hidden");
}

function renderThemes(session) {
  themesList.innerHTML = "";
  for (const theme of session.themes) {
    const li = document.createElement("li");
    li.className = "theme-row";

    const input = document.createElement("input");
    input.type = "text";
    input.value = theme.label;
    input.addEventListener("change", () => renameTheme(theme.id, input.value));

    const count = document.createElement("span");
    count.className = "theme-count";
    count.textContent = `${theme.count} item(s)`;

    li.appendChild(input);
    li.appendChild(count);
    themesList.appendChild(li);
  }
}

async function renameTheme(themeId, label) {
  try {
    const updated = await apiFetch(`/sessions/${currentSession.session_id}/themes/${themeId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label }),
    });
    currentSession = updated;
    // Re-render both: the server may have normalized the label (trimmed
    // whitespace), and a rejected/blank rename must not leave a stale or
    // out-of-sync value sitting in the input -- see the catch branch below.
    renderThemes(updated);
    renderOpportunities(updated);
  } catch (err) {
    setStatus(err.message, "error");
    // The PATCH failed (e.g. a blank label was rejected server-side); reset
    // the input back to the last known-good state instead of leaving the
    // user's rejected edit visible as if it had been saved.
    if (currentSession) renderThemes(currentSession);
  }
}

function evidenceBlock(title, evidenceItems) {
  const wrap = document.createElement("div");
  wrap.className = "evidence-block";

  const heading = document.createElement("h4");
  heading.textContent = title;
  wrap.appendChild(heading);

  if (!evidenceItems.length) {
    const empty = document.createElement("p");
    empty.className = "evidence-row";
    empty.textContent = "None found.";
    wrap.appendChild(empty);
    return wrap;
  }

  const ul = document.createElement("ul");
  for (const evidence of evidenceItems) {
    const li = document.createElement("li");

    const quote = document.createElement("span");
    quote.textContent = `"${evidence.quote}"`;

    const row = document.createElement("span");
    row.className = "evidence-row";
    row.textContent = ` (row ${evidence.source_row})`;

    li.appendChild(quote);
    li.appendChild(row);
    ul.appendChild(li);
  }
  wrap.appendChild(ul);
  return wrap;
}

function renderOpportunities(session) {
  opportunitiesList.innerHTML = "";
  for (const opportunity of session.opportunities) {
    opportunitiesList.appendChild(buildOpportunityCard(opportunity));
  }
}

function buildOpportunityCard(opportunity) {
  const card = document.createElement("div");
  card.className = "opportunity-card";

  const h3 = document.createElement("h3");
  h3.textContent = opportunity.title;
  card.appendChild(h3);

  const meta = document.createElement("div");
  meta.className = "opportunity-meta";

  const select = document.createElement("select");
  for (const level of ["Unset", "High", "Medium", "Low"]) {
    const option = document.createElement("option");
    option.value = level;
    option.textContent = level;
    if (level === opportunity.priority) option.selected = true;
    select.appendChild(option);
  }

  const notes = document.createElement("textarea");
  notes.placeholder = "Notes for the team...";
  notes.value = opportunity.notes || "";

  const savePriority = () => setPriority(opportunity.id, select.value, notes.value);
  select.addEventListener("change", savePriority);
  notes.addEventListener("change", savePriority);

  const countSpan = document.createElement("span");
  countSpan.className = "theme-count";
  countSpan.textContent = `${opportunity.count} item(s)`;

  meta.appendChild(select);
  meta.appendChild(countSpan);
  card.appendChild(meta);
  card.appendChild(notes);
  card.appendChild(evidenceBlock("Supporting evidence", opportunity.supporting_evidence));
  card.appendChild(evidenceBlock("Conflicting evidence", opportunity.conflicting_evidence));
  return card;
}

async function setPriority(opportunityId, priority, notes) {
  try {
    const updated = await apiFetch(
      `/sessions/${currentSession.session_id}/opportunities/${opportunityId}/priority`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ priority, notes }),
      }
    );
    currentSession = updated;
  } catch (err) {
    setStatus(err.message, "error");
  }
}

generateBriefBtn.addEventListener("click", async () => {
  if (!currentSession) return;
  try {
    const response = await fetch(
      `${API_BASE}/sessions/${currentSession.session_id}/brief?format=markdown`
    );
    if (!response.ok) throw new Error("Could not generate the brief.");
    const text = await response.text();
    briefOutput.textContent = text;
    briefOutput.classList.remove("hidden");

    const blob = new Blob([text], { type: "text/markdown" });
    downloadBriefLink.href = URL.createObjectURL(blob);
    downloadBriefLink.classList.remove("hidden");
  } catch (err) {
    setStatus(err.message, "error");
  }
});