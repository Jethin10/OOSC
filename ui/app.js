"use strict";

const state = { data: null, agent: "", filter: "", type: "", selected: -1, visibleRows: [] };
const $ = (selector) => document.querySelector(selector);

function element(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "style") node.style.cssText = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

const formatPercent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
const titleCase = (value) => String(value || "").replace(/[_-]/g, " ").replace(/:\s*/g, ": ").replace(/\b\w/g, (c) => c.toUpperCase());
const activeCard = () => state.data.scorecards[state.agent];

function renderSummary() {
  const data = state.data;
  const overall = activeCard().overall;
  $("#overall-rate").textContent = (overall.reliability * 100).toFixed(1);
  $("#overall-runs").textContent = `${overall.runs} runs · ${data.domain} domain`;
  const interval = $("#overall-ci");
  interval.style.left = `${overall.ci95[0] * 100}%`;
  interval.style.width = `${Math.max(1, (overall.ci95[1] - overall.ci95[0]) * 100)}%`;
  $("#cats").replaceChildren(...activeCard().categories.map((category) => {
    const fill = element("i"); fill.style.transform = `scaleX(${category.reliability})`;
    return element("div", { class: "category" }, element("div", {}, element("span", {}, titleCase(category.category)), element("b", {}, formatPercent(category.reliability))), element("div", { class: "category-bar" }, fill));
  }));
  const counts = {};
  for (const run of data.runs || []) if (run.agent === state.agent) for (const failure of run.failures || []) counts[failure] = (counts[failure] || 0) + 1;
  const colors = { tool_loop: "#f5c451", hallucinated_confidence: "#f06f6f", unsafe_action: "#ec8f6a", goal_drift: "#a78bfa" };
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  $("#legend").replaceChildren(...(entries.length ? entries.map(([kind, count]) => element("div", { class: "legend-row" }, element("span", { class: "legend-dot", style: `background:${colors[kind] || "#88909c"}` }), element("span", {}, titleCase(kind)), element("b", {}, String(count)))) : [element("div", { class: "muted empty-legend" }, "No failures detected")]));
}

function renderTopMetrics() {
  const data = state.data, runs = data.runs || [];
  const uniqueScenarios = new Set(runs.map((run) => run.scenario));
  const adversarial = new Set(runs.filter((run) => String(run.scenario_type || run.category).startsWith("adversarial:")).map((run) => String(run.scenario_type || run.category)));
  $("#metric-scenarios").textContent = data.suite_size ?? uniqueScenarios.size;
  $("#metric-adversarial").textContent = adversarial.size || "4 classes";
  $("#metric-replay").textContent = data.replay_failures === 0 ? "100%" : `${data.replay_failures} failed`;
  $("#metric-replay-detail").textContent = data.replay_failures === 0 ? "all fingerprints reproduced" : "replay mismatches require review";
  const history = data.history_regression || {};
  $("#metric-regression").textContent = history.gate_pass === false ? "Regression" : "No regression";
  $("#metric-baseline").textContent = history.baseline ? `vs ${history.baseline}` : "first recorded baseline";
  const gatePassed = data.replay_failures === 0 && history.gate_pass !== false;
  $("#gate-label").textContent = gatePassed ? "CI gate passed" : "CI gate blocked";
  document.body.dataset.gate = gatePassed ? "passed" : "failed";
}

function filteredRows() {
  const query = state.filter.trim().toLowerCase();
  return (state.data.runs || []).filter((run) => {
    if (run.agent !== state.agent) return false;
    const scenarioType = String(run.scenario_type || (String(run.category).startsWith("adversarial:") ? run.category : "realistic"));
    if (state.type && !scenarioType.startsWith(state.type)) return false;
    return !query || `${run.scenario} ${run.category} ${(run.failures || []).join(" ")}`.toLowerCase().includes(query);
  });
}

function renderTable() {
  const rows = state.visibleRows = filteredRows();
  $("#count").textContent = `${rows.length} visible`;
  if (!rows.length) { $("#runs-body").replaceChildren(element("tr", {}, element("td", { colspan: "6", class: "empty-state" }, "No runs match this view."))); return; }
  $("#runs-body").replaceChildren(...rows.map((run, index) => {
    const failures = run.failures || [];
    const row = element("tr", { tabindex: "-1", "aria-selected": String(index === state.selected) },
      element("td", { class: "mono" }, run.scenario), element("td", {}, titleCase(run.category)),
      element("td", {}, element("span", { class: `outcome ${run.success ? "pass" : "fail"}` }, run.success ? "Pass" : "Fail")),
      element("td", { class: "failure-cell" }, ...(failures.length ? failures.map((failure) => element("span", { class: `failure-chip ${failure}` }, titleCase(failure))) : [element("span", { class: "clean-label" }, "No finding")])),
      element("td", { class: "number hide-mobile" }, String(run.calls ?? 0)),
      element("td", { class: "hide-mobile" }, element("span", { class: `replay-check ${run.replay_verified === false ? "bad" : ""}` }, run.replay_verified === false ? "Mismatch" : "Verified")));
    row.addEventListener("click", () => openDetails(index)); return row;
  }));
}

function renderTabs() {
  const names = Object.keys(state.data.scorecards);
  if (!state.agent || !state.data.scorecards[state.agent]) state.agent = names[0];
  $("#tabs").replaceChildren(...names.map((name) => {
    const button = element("button", { type: "button", role: "tab", "aria-selected": String(name === state.agent) }, titleCase(name));
    button.addEventListener("click", () => { if (state.agent === name) return; state.agent = name; state.selected = -1; renderTabs(); renderSummary(); renderTable(); });
    return button;
  }));
}

function openDetails(index) {
  const run = state.visibleRows[index]; if (!run) return;
  state.selected = index;
  state.returnFocus = document.activeElement;
  const root = $("#drawer-root"); root.inert = false; root.classList.add("open"); root.setAttribute("aria-hidden", "false");
  $("#d-title").textContent = run.scenario; $("#d-meta").textContent = `${titleCase(run.agent)} · ${titleCase(run.category)}`;
  const pairs = [["Outcome", run.success ? "Pass" : "Fail"], ["Oracle reward", run.reward], ["Tool calls", run.calls ?? 0], ["State mutations", run.mutations ?? 0], ["Failure modes", (run.failures || []).length ? (run.failures || []).map(titleCase).join(", ") : "None"], ["Replay", run.replay_verified === false ? "Fingerprint mismatch" : "Verified"]];
  $("#d-kv").replaceChildren(...pairs.flatMap(([key, value]) => [element("dt", {}, key), element("dd", {}, String(value))]));
  $("#d-close").focus(); renderTable();
}
function closeDetails() { const root = $("#drawer-root"); root.classList.remove("open"); if (state.returnFocus?.focus) state.returnFocus.focus(); else $("#filter").focus(); root.inert = true; root.setAttribute("aria-hidden", "true"); }

function bindInteractions() {
  $("#filter").addEventListener("input", (event) => { state.filter = event.target.value; state.selected = -1; renderTable(); });
  $("#scenario-type").addEventListener("change", (event) => { state.type = event.target.value; state.selected = -1; renderTable(); });
  $("#drawer-backdrop").addEventListener("click", closeDetails); $("#d-close").addEventListener("click", closeDetails);
  $("#export-button").addEventListener("click", () => { const blob = new Blob([JSON.stringify(state.data, null, 2)], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "oosc-reliability-report.json"; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 0); });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement !== $("#filter")) { event.preventDefault(); $("#filter").focus(); return; }
    if (event.key === "Escape") { closeDetails(); return; }
    if (document.activeElement === $("#filter")) return;
    if (event.key === "j" || event.key === "k") { event.preventDefault(); const delta = event.key === "j" ? 1 : -1; state.selected = Math.max(0, Math.min(state.visibleRows.length - 1, state.selected + delta)); renderTable(); const row = $("#runs-body").children[state.selected]; if (row) { row.focus(); row.scrollIntoView({ block: "nearest" }); } }
    if (event.key === "Enter" && state.selected >= 0) openDetails(state.selected);
  });
}

async function init() {
  try { const response = await fetch("data/ci-report.json", { cache: "no-store" }); if (!response.ok) throw new Error(`Report request failed: ${response.status}`); state.data = await response.json(); }
  catch (error) { document.body.innerHTML = `<main class="load-error"><h1>Report unavailable</h1><p>${error.message}</p><p>Run the OOSC CI command to generate <code>ui/data/ci-report.json</code>.</p></main>`; return; }
  $("#generated").textContent = new Date(state.data.generated_at || Date.now()).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  renderTabs(); renderSummary(); renderTopMetrics(); renderTable(); bindInteractions(); document.body.dataset.ready = "true";
}
init();
