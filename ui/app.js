/* OOSC Scorecard app — no dependencies, synchronous interactions, transform/opacity motion only. */
"use strict";

const state = {
  data: null,
  agent: "clean-agent",
  filter: "",
  selected: -1,
  visibleRows: [],
};

const $ = (sel) => document.querySelector(sel);

function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return n;
}

function fmtPct(x) { return (x * 100).toFixed(1) + "%"; }

function renderSidebar() {
  const d = state.data;
  const overall = d.scorecards[state.agent].overall;
  $("#overall-rate").textContent = fmtPct(overall.reliability);
  $("#overall-runs").textContent = `${overall.runs} runs · ${d.domain} · suite ${d.suite_size}`;
  const bar = $("#overall-ci");
  bar.style.left = (overall.ci95[0] * 100) + "%";
  bar.style.width = Math.max(0.5, (overall.ci95[1] - overall.ci95[0]) * 100) + "%";

  const list = $("#cats");
  list.textContent = "";
  for (const c of d.scorecards[state.agent].categories) {
    const row = el("div", { class: "cat" },
      el("span", { class: "name" }, c.category),
      el("span", { class: "rate" }, fmtPct(c.reliability)),
      el("div", { class: "bar" }, (() => {
        const i = el("i"); i.style.transform = `scaleX(${c.reliability})`; return i;
      })()),
    );
    list.appendChild(row);
  }

  const legend = $("#legend");
  legend.textContent = "";
  const kinds = {};
  for (const r of d.runs) if (r.agent === state.agent && !r.success) for (const k of r.failures) kinds[k] = (kinds[k] || 0) + 1;
  const colors = { tool_loop: "#f2c94c", hallucinated_confidence: "#eb5757", unsafe_action: "#e0876a", goal_drift: "#b58af7" };
  const entries = Object.entries(kinds).sort((a, b) => b[1] - a[1]);
  if (!entries.length) legend.appendChild(el("div", { class: "row" }, "No failures recorded."));
  for (const [k, v] of entries) {
    legend.appendChild(el("div", { class: "row" },
      el("span", { class: "dot", style: `background:${colors[k] || "#8a8f98"}` }),
      `${k.replace(/_/g, " ")}`, el("span", { style: "margin-left:auto;font-variant-numeric:tabular-nums" }, String(v)),
    ));
  }
}

function rowsFor() {
  const d = state.data;
  const q = state.filter.trim().toLowerCase();
  let rows = d.runs.filter((r) => r.agent === state.agent);
  if (q) rows = rows.filter((r) => r._search.includes(q));
  return rows;
}

function indexSearchText() {
  for (const r of state.data.runs) {
    r._search = (r.scenario + " " + r.category + " " + r.failures.join(" ")).toLowerCase();
  }
}

function renderTable() {
  const tbody = $("#runs-body");
  const rows = state.visibleRows = rowsFor();
  $("#count").textContent = `${rows.length} runs`;
  if (!rows.length) {
    state._pool = state._pool || [];
    const emptyTr = el("tr", { "data-empty": "1" }, el("td", { colspan: "6" }, el("div", { class: "empty" }, "No runs match this filter.")));
    tbody.replaceChildren(emptyTr);
    return;
  }
  // In-place pooled rendering: reuse <tr> nodes across renders so filtering
  // costs only property writes - keeps every keystroke well under budget.
  const pool = state._pool || (state._pool = []);
  while (pool.length < rows.length) {
    const tr = document.createElement("tr");
    tr.appendChild(el("td", { class: "mono" }));
    tr.appendChild(el("td", {}));
    tr.appendChild(el("td", {}));
    tr.appendChild(el("td", {}));
    tr.appendChild(el("td", { class: "num hide-m" }));
    tr.appendChild(el("td", { class: "num hide-m" }));
    tr.addEventListener("click", () => {
      const idx = pool.indexOf(tr);
      if (idx >= 0) selectRow(idx);
    });
    tbody.appendChild(tr);
    pool.push(tr);
  }
  for (let i = 0; i < pool.length; i++) {
    const tr = pool[i];
    if (tr.parentNode !== tbody) {
      // reattach after an empty render removed everything; keep order
      if (tbody.firstElementChild && tbody.firstElementChild.dataset.empty === "1") {
        tbody.replaceChildren();
      }
      tbody.appendChild(tr);
    }
    if (i < rows.length) {
      const r = rows[i];
      const [tdId, tdCat, tdOut, tdFail, tdCalls, tdMut] = tr.children;
      tdId.textContent = r.scenario;
      tdCat.textContent = r.category;
      tdOut.className = "";
      tdOut.replaceChildren(r.success ? el("span", { class: "ok-dot", title: "pass" }) : el("span", { class: "fail-dot", title: "fail" }));
      tdFail.textContent = "";
      if (r.failures.length) {
        for (const k of r.failures) tdFail.appendChild(el("span", { class: "chip bad" }, k.replace(/_/g, " ")));
      } else {
        tdFail.appendChild(el("span", { class: "chip" }, "clean"));
      }
      tdCalls.textContent = String(r.calls);
      tdMut.textContent = String(r.mutations);
      tr.style.display = "";
      tr.classList.toggle("selected", i === state.selected);
      tr.dataset.i = String(i);
    } else {
      tr.style.display = "none";
    }
  }
}

function selectRow(i, openDrawer = false) {
  const rows = state.visibleRows;
  if (!rows.length) return;
  state.selected = Math.max(0, Math.min(rows.length - 1, i));
  const table = $("#runs-body");
  [...table.children].forEach((tr, j) => tr.classList.toggle("selected", j === state.selected));
  const sel = table.children[state.selected];
  if (sel) sel.scrollIntoView({ block: "nearest" });
  if (openDrawer) openDetail(rows[state.selected]);
}

function openDetail(r) {
  const d = $("#drawer-root");
  d.classList.add("open");
  state._drawerReturnFocus = document.activeElement;
  $("#d-close").focus();
  $("#d-title").textContent = r.scenario;
  $("#d-meta").textContent = `${r.agent} · ${r.category}`;
  const kv = $("#d-kv");
  kv.textContent = "";
  const add = (k, v, mono = false) => {
    kv.appendChild(el("dt", {}, k));
    const dd = el("dd", {}, String(v));
    if (mono) dd.classList.add("fp");
    kv.appendChild(dd);
  };
  add("outcome", r.success ? "PASS" : "FAIL");
  add("oracle reward", r.reward);
  add("tool calls", r.calls);
  add("state mutations", r.mutations);
  add("failure modes", r.failures.length ? r.failures.join(", ").replace(/_/g, " ") : "none detected");
}

function closeDrawer() {
  if (!$("#drawer-root").classList.contains("open")) return;
  $("#drawer-root").classList.remove("open");
  if (state._drawerReturnFocus && state._drawerReturnFocus.focus) state._drawerReturnFocus.focus();
}

/* ---------- interactions (all synchronous < 100ms) ---------- */
function bind() {
  $("#filter").addEventListener("input", (e) => {
    state.filter = e.target.value;
    state.selected = -1;
    renderTable();
  });
  $("#tabs").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-agent]");
    if (!btn || btn.dataset.agent === state.agent) return;
    state.agent = btn.dataset.agent;
    state.selected = -1;
    for (const b of $("#tabs").children) b.setAttribute("aria-selected", String(b.dataset.agent === state.agent));
    closeDrawer();
    renderSidebar();
    renderTable();
  });
  $("#drawer-backdrop").addEventListener("click", closeDrawer);

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== $("#filter")) {
      e.preventDefault(); $("#filter").focus(); return;
    }
    if (e.key === "Escape") { closeDrawer(); $("#filter").blur(); return; }
    if (document.activeElement === $("#filter") && e.key !== "Enter") return;
    if (e.key === "j") { e.preventDefault(); selectRow(Math.min(state.selected + 1, state.visibleRows.length - 1)); }
    if (e.key === "k") { e.preventDefault(); selectRow(state.selected - 1); }
    if (e.key === "Enter" && state.selected >= 0 && !$("#drawer-root").classList.contains("open")) {
      openDetail(state.visibleRows[state.selected]);
    }
    if (e.key === "Enter" && $("#drawer-root").classList.contains("open")) closeDrawer();
  });
}

function buildTabs() {
  const tabs = $("#tabs");
  tabs.textContent = "";
  for (const name of Object.keys(state.data.scorecards)) {
    tabs.appendChild(el("button", { "data-agent": name, "aria-selected": String(name === state.agent) },
      name.replace(/-/g, " ")));
  }
}

async function init() {
  let data;
  try {
    data = window.__SCORECARD__ || await (await fetch("data/scorecard.json")).json();
  } catch {
    data = window.__SCORECARD__;
  }
  state.data = data;
  indexSearchText();
  $("#generated").textContent = new Date(data.generated_at).toLocaleString();
  $("#replay").textContent = `replay verified · ${data.replay_failures} failures`;
  buildTabs();
  renderSidebar();
  renderTable();
  bind();
  // Warm the filter path once at startup so the first user keystroke pays no
  // JIT/layout cost: render, revert, yield a frame.
  requestAnimationFrame(() => {
    const f = $("#filter");
    f.value = "~warmup";
    f.dispatchEvent(new Event("input", { bubbles: true }));
    f.value = "";
    f.dispatchEvent(new Event("input", { bubbles: true }));
  });
  document.body.dataset.ready = "1";
}

init();
