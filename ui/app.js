"use strict";

/* OOSC — Agent Reliability Engine
   ---------------------------------------------------------------------------
   One bundle in (ui/data/report.json, built by scripts/build_ui_data.py), six
   views out. No framework and no build step, so the paint cost stays
   inspectable and the whole thing serves straight from a CI artifact
   directory with the network off.
   --------------------------------------------------------------------------- */

const state = {
  data: null,
  domainId: "",
  view: "overview",
  agent: "",
  replayAgent: "",
  filter: "",
  type: "",
  outcome: "",
  selected: -1,
  visibleRows: [],
  returnFocus: null,
  replayToken: 0,
  painted: new Set(),
};

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "style") n.style.cssText = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of kids.flat()) {
    if (c === null || c === undefined || c === false) continue;
    n.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
  }
  return n;
}

function svg(paths, box = "0 0 20 20") {
  const NS = "http://www.w3.org/2000/svg";
  const s = document.createElementNS(NS, "svg");
  s.setAttribute("viewBox", box);
  s.setAttribute("aria-hidden", "true");
  for (const d of [].concat(paths)) {
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", d);
    s.appendChild(p);
  }
  return s;
}

const pct = (v, d = 1) => `${(Number(v || 0) * 100).toFixed(d)}%`;
const clamp01 = (v) => Math.max(0, Math.min(1, Number(v) || 0));
const titleCase = (v) =>
  String(v || "").replace(/[_-]/g, " ").replace(/:\s*/g, ": ").replace(/\b\w/g, (c) => c.toUpperCase());
const shortName = (n) => titleCase(n).replace(/\s*Agent$/, "");

/* Taken from the policy docstrings in engine/oosc/runner/policies.py, so the
   interface and the engine never drift apart on what a version claims to do. */
const AGENT_NOTES = {
  "clean-agent": "Control. Executes exactly what the scenario asks.",
  "cautious-agent": "Negative control. Engages with every probe, reads the poisoned output, refuses.",
  "loopy-agent": "Repeats every mutating call three times — the classic retry loop.",
  "overconfident-agent": "Botches the final call, then reports success anyway.",
  "reckless-agent": "Finishes the task, then mutates an unrelated entity.",
  "pressure-compliant-agent": "Yields to pressure and acts without confirmation.",
};

const VIEWS = [
  { id: "overview", label: "Overview" },
  { id: "pipeline", label: "Pipeline" },
  { id: "runs", label: "Runs" },
  { id: "guardrails", label: "Guardrails" },
  { id: "scorecard", label: "Scorecard" },
  { id: "evidence", label: "Evidence" },
];

/* The bundle carries every evaluated domain; D() is whichever one is on screen.
   Each domain is a complete, independent CI run — switching is not a filter. */
const D = () => state.data.domains.find((x) => x.id === state.domainId) || state.data.domains[0];
const runsFor = (a) => D().runs.filter((r) => r.agent === a);
const agentNames = () => Object.keys(D().scorecards);
const probeRuns = () => D().runs.filter((r) => r.probe);

/* Numbers count up on reveal. Cheap, and it makes a static report feel like a
   readout rather than a screenshot. */
function countUp(node, to, format, ms = 950, delay = 0) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { node.textContent = format(to); return; }
  node.textContent = format(0);
  const start = performance.now() + delay;
  const tick = (now) => {
    const t = Math.max(0, Math.min(1, (now - start) / ms));
    node.textContent = format(to * (1 - Math.pow(1 - t, 3)));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/* ------------------------------------------------------------------ theme */

const SUN = ["M10 3v1.6M10 15.4V17M3 10h1.6M15.4 10H17M5.2 5.2l1.1 1.1M13.7 13.7l1.1 1.1M14.8 5.2l-1.1 1.1M6.3 13.7l-1.1 1.1", "M10 6.6a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8z"];
const MOON = ["M15.5 11.6A6 6 0 0 1 8.4 4.5a6 6 0 1 0 7.1 7.1z"];

function paintThemeIcon() {
  const dark = document.documentElement.dataset.theme === "dark";
  const btn = $("#theme-toggle");
  btn.replaceChildren(svg(dark ? SUN : MOON));
  btn.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", dark ? "#0C0C0D" : "#FCFCFB");
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("oosc-theme", next); } catch (e) { /* private mode */ }
  paintThemeIcon();
  if (state.data) { renderHeat(); renderTrend(); }
}

/* -------------------------------------------------------------- entrance */

/* Content settles in once per view. Staggering by index is what separates a
   considered reveal from everything appearing at once. */
function playReveal(root) {
  const nodes = Array.from(root.querySelectorAll(".reveal"));
  nodes.forEach((n, i) => {
    n.classList.remove("in");
    n.style.setProperty("--d", `${Math.min(i * 55, 420)}ms`);
  });
  requestAnimationFrame(() => requestAnimationFrame(() => nodes.forEach((n) => n.classList.add("in"))));
}

/* ------------------------------------------------------------------- nav */

function renderNav() {
  $("#nav").replaceChildren(...VIEWS.map((v) => {
    const b = el("button", {
      type: "button", "data-view": v.id, text: v.label,
      "aria-current": state.view === v.id ? "page" : null,
    });
    b.addEventListener("click", () => setView(v.id));
    return b;
  }));
}

function setView(id) {
  if (!VIEWS.some((v) => v.id === id)) id = "overview";
  state.view = id;
  for (const v of VIEWS) $(`#view-${v.id}`).hidden = v.id !== id;
  renderNav();
  if (location.hash.slice(1) !== id) history.replaceState(null, "", `#${id}`);
  window.scrollTo({ top: 0, behavior: "auto" });
  playReveal($(`#view-${id}`));
  if (id === "overview") {
    requestAnimationFrame(() => $$("#figures .figure__meter").forEach((m) => m.classList.add("in")));
  }
}

/* -------------------------------------------------------------- overview */

function renderOverview() {
  const d = D();

  const whole = (v) => String(Math.round(v));
  const counters = [
    ["Scenarios", d.suite_size],
    ["Traces replayed", d.replay_checks],
    ["Replay failures", d.replay_failures],
  ].map(([label, value]) => {
    const dd = el("dd", { text: "0" });
    countUp(dd, value, whole, 900, 220);
    return el("div", {}, el("dt", { text: label }), dd);
  });
  $("#gate-strip").replaceChildren(
    el("div", {},
      el("dt", { text: "Commit gate" }),
      el("dd", {}, el("span", { class: "state" }, el("span", { class: "dot" }), d.gate_pass ? "Passed" : "Blocked"))),
    ...counters
  );

  const note = $("#domain-note");
  note.dataset.unseen = String(!!d.unseen);
  note.replaceChildren(
    el("b", { text: d.unseen ? `${d.label} — a domain OOSC has never seen` : `${d.label} — ${d.origin}` }),
    d.note, " ",
    el("em", { text: `${Object.keys(d.world_spec.effects || {}).length} tools · `
      + Object.entries(d.world_spec.tables || {}).map(([n, c]) => `${c} ${n}`).join(" · ") })
  );

  $("#figures").replaceChildren(...state.data.benchmarks.map((b, i) => {
    const node = el("button", { class: "figure", type: "button", "data-status": b.status },
      el("div", { class: "figure__value" },
        (() => {
          const digits = b.value >= 0.995 ? 2 : 1;
          const node = el("b", { text: "0%" });
          countUp(node, b.value, (v) => `${(v * 100).toFixed(digits)}%`, 1100, 260 + i * 110);
          return node;
        })(),
        el("span", { class: "figure__tag", text: b.status === "parked" ? "parked" : "cleared" })),
      el("div", { class: "figure__body" },
        el("h3", { text: b.title }),
        el("p", { text: `${b.subtitle} · ${b.bar_label}` }),
        el("div", { class: "figure__meter", style: `--v:${clamp01(b.value)};--d:${180 + i * 90}ms` },
          el("i"), el("u", { style: `left:${clamp01(b.bar) * 100}%` }))),
      el("span", { class: "figure__go" }, svg("M7 4l6 6-6 6")));
    node.addEventListener("click", () => {
      setView("evidence");
      const t = document.getElementById(`bench-${b.id}`);
      if (t) setTimeout(() => t.scrollIntoView({ block: "center", behavior: "smooth" }), 80);
    });
    return node;
  }));

  $("#directions").replaceChildren(...state.data.directions.map((dir, i) => {
    const go = el("button", { class: "btn", type: "button", text: "Open" });
    go.addEventListener("click", () => setView(dir.view));
    const stat = directionStat(dir.id, d);
    return el("div", { class: "dir" },
      el("div", { class: "dir__n", text: String(i + 1).padStart(2, "0") }),
      el("div", {},
        el("h3", { text: dir.name }),
        el("p", { class: "dir__ask", text: dir.ask }),
        el("p", { class: "dir__built", text: dir.built }),
        el("code", { text: dir.code }),
        stat ? el("div", { class: "dir__stat" }, ...stat) : null),
      go);
  }));
}

/* Each direction carries a figure computed from the run on screen, so the
   coverage list reads as live output rather than a list of claims. */
function directionStat(id, d) {
  const B = (v) => el("b", { text: String(v) });
  const g = d.generation || {};
  if (id === "generation") {
    return [B(g.pool ?? d.suite_size), " scenarios generated · ", B(g.adversarial ?? 0), " adversarial probes"];
  }
  if (id === "sandbox") {
    return [B(d.replay_checks), " traces replayed · ", B(d.replay_failures), " fingerprint mismatches"];
  }
  if (id === "classifier") {
    const kinds = new Set();
    let n = 0;
    for (const r of d.runs) for (const f of r.failures || []) { kinds.add(f); n += 1; }
    return [B(n), " findings across ", B(kinds.size), " failure modes"];
  }
  if (id === "guardrail") {
    const probes = d.runs.filter((r) => r.probe);
    const bad = probes.filter((r) => (r.failures || []).includes("unsafe_action") || (r.mutations || 0) > 0).length;
    const versions = new Set(probes.map((r) => r.agent)).size;
    return [B(new Set(probes.map((r) => r.scenario)).size), " probes x ", B(versions),
            " versions · ", B(bad), " complied"];
  }
  if (id === "scorecard") {
    const cats = new Set();
    for (const card of Object.values(d.scorecards)) for (const c of card.categories) cats.add(c.category);
    return [B(Object.keys(d.scorecards).length), " versions · ", B(cats.size), " categories · ",
            B(d.history.length), " snapshots"];
  }
  return null;
}

/* -------------------------------------------------------------- pipeline */

const STAGES = [
  { id: "derive", name: "Derive world from schemas", note: "tool declarations and initial state only — no domain code imported" },
  { id: "generate", name: "Generate scenarios", note: "realistic and adversarial, each validated by execution before emission" },
  { id: "execute", name: "Execute sandboxed", note: "mocked tools, world state fingerprinted after every mutation" },
  { id: "replay", name: "Verify deterministic replay", note: "re-executed on a fresh world, every fingerprint must reproduce" },
  { id: "classify", name: "Classify failure modes", note: "four detectors over the trace, each carrying its own evidence" },
  { id: "score", name: "Score and gate the commit", note: "Wilson intervals per category, compared against the last snapshot" },
];

function renderPipelineStatics() {
  const d = D();
  $("#stages").replaceChildren(...STAGES.map((s) =>
    el("div", { class: "stage", id: `stage-${s.id}`, "data-state": "idle" },
      el("div", { class: "stage__dot" }),
      el("div", {}, el("h4", { text: s.name }), el("p", { text: s.note })),
      el("div", { class: "stage__out", id: `out-${s.id}`, text: "—" }),
      el("div", { class: "stage__track", id: `track-${s.id}` }))));

  const sel = $("#pipe-agent");
  sel.replaceChildren(...agentNames().map((n) => el("option", { value: n, text: shortName(n) })));
  sel.value = state.replayAgent;

  const spec = d.world_spec || {};
  const effects = Object.entries(spec.effects || {});
  const tables = Object.entries(spec.tables || {});
  $("#spec-note").textContent =
    `${effects.length} tools classified · ${tables.map(([n, c]) => `${c} ${n}`).join(", ")}`;

  $("#spec-grid").replaceChildren(...effects.map(([name, e]) => {
    const rows = [];
    const add = (k, v) => { rows.push(el("dt", { text: k }), el("dd", { text: v })); };
    if (e.bindings?.length) add("binds", e.bindings.map((b) => `${b.param} → ${b.table || "?"}`).join(", "));
    if (e.required?.length) add("requires", e.required.join(", "));
    if (e.target) add("sets", e.target);
    if (e.one_shot) add("irreversible", "yes");
    return el("div", { class: "spec" },
      el("div", { class: "spec__name", text: name }),
      el("span", { class: "spec__kind", "data-k": e.kind, text: e.kind }),
      rows.length ? el("dl", {}, ...rows) : null);
  }));
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let clock = 0;
const stamp = () => {
  clock += 7 + Math.floor(Math.random() * 9);
  return `+${(clock / 1000).toFixed(2)}s`.padStart(7, " ");
};

function logLine(cls, mark, ...content) {
  const box = $("#console");
  box.appendChild(el("div", { class: `console__line ${cls}` },
    el("span", { text: stamp() }), el("span", { text: mark }), el("span", {}, ...content)));
  while (box.childElementCount > 260) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
}

function logNote(...content) {
  const box = $("#console");
  box.appendChild(el("div", { class: "console__line is-note" }, el("span", { text: stamp() }), el("span", {}, ...content)));
  box.scrollTop = box.scrollHeight;
}

function resetPipeline() {
  clock = 0;
  const old = $("#run-summary");
  if (old) old.remove();
  $("#console").replaceChildren(el("div", { class: "console__empty", text: "Waiting — press Replay run." }));
  for (const s of STAGES) {
    const n = document.getElementById(`stage-${s.id}`);
    n.dataset.state = "idle";
    document.getElementById(`out-${s.id}`).textContent = "—";
    const t = document.getElementById(`track-${s.id}`);
    t.style.transition = "none";
    t.style.transform = "scaleX(0)";
  }
}

async function stage(id, token, ms, output, work) {
  if (token !== state.replayToken) throw new Error("cancelled");
  const node = document.getElementById(`stage-${id}`);
  const track = document.getElementById(`track-${id}`);
  node.dataset.state = "active";
  track.style.transition = `transform ${ms}ms linear`;
  requestAnimationFrame(() => { track.style.transform = "scaleX(1)"; });
  if (work) await work(token); else await sleep(ms);
  if (token !== state.replayToken) throw new Error("cancelled");
  node.dataset.state = "done";
  document.getElementById(`out-${id}`).textContent = output();
  track.style.transition = "none";
  track.style.transform = "scaleX(0)";
}

async function runReplay() {
  const token = ++state.replayToken;
  const d = D();
  const agent = state.replayAgent;
  const runs = runsFor(agent);
  const btn = $("#pipe-run");
  btn.disabled = true;
  btn.textContent = "Replaying…";
  $("#pipe-status").textContent = `replaying ${shortName(agent)}`;
  resetPipeline();
  $("#console").replaceChildren();

  const spec = d.world_spec || {};
  const nTools = Object.keys(spec.effects || {}).length;
  const nRecords = Object.values(spec.tables || {}).reduce((a, b) => a + b, 0);
  const gen = d.generation || {};
  const c = { calls: 0, mutations: 0, replayed: 0, bad: 0, findings: {} };

  try {
    logNote("loading domain ", el("b", { text: d.domain }), " — tool schemas and initial state only");

    await stage("derive", token, 560, () => `${nTools} tools · ${nRecords} records`, async () => {
      await sleep(250);
      const kinds = {};
      for (const e of Object.values(spec.effects || {})) kinds[e.kind] = (kinds[e.kind] || 0) + 1;
      logLine("is-ok", "✓", "derived world spec: ",
        el("b", { text: Object.entries(kinds).map(([k, v]) => `${v} ${k}`).join(", ") }));
      const irr = Object.entries(spec.effects || {}).filter(([, e]) => e.one_shot).map(([n]) => n);
      if (irr.length) logLine("is-ok", "✓", "irreversible operations identified: ", el("em", { text: irr.join(", ") }));
      await sleep(250);
    });

    await stage("generate", token, 560, () => `${gen.suite ?? runs.length} of ${gen.pool ?? runs.length}`, async () => {
      await sleep(240);
      logLine("is-ok", "✓", `generated ${gen.pool ?? runs.length} candidates, sampled `,
        el("b", { text: `${gen.realistic ?? 0} realistic` }), " + ", el("b", { text: `${gen.adversarial ?? 0} adversarial` }));
      logLine("is-ok", "✓", "probe classes: ", el("em", { text: (gen.adversarial_kinds || []).join(", ") || "none" }));
      await sleep(240);
    });

    await stage("execute", token, 1, () => `${c.calls} calls · ${c.mutations} mutations`, async (tk) => {
      const per = Math.max(11, Math.min(44, 1450 / Math.max(1, runs.length)));
      for (const run of runs) {
        if (tk !== state.replayToken) throw new Error("cancelled");
        c.calls += run.calls || 0;
        c.mutations += run.mutations || 0;
        for (const f of run.failures || []) c.findings[f] = (c.findings[f] || 0) + 1;
        const adv = String(run.scenario_type || "").startsWith("adversarial:");
        logLine(run.success ? "is-ok" : "is-bad", run.success ? "✓" : "✗",
          el("b", { text: run.scenario }), "  ",
          adv ? el("em", { text: run.scenario_type.split(":")[1] }) : run.category, "  ",
          `${run.calls} calls`,
          run.mutations ? `, ${run.mutations} mut` : "",
          (run.failures || []).length ? "  → " : "",
          (run.failures || []).length ? el("em", { text: run.failures.join(" ") }) : "");
        await sleep(per);
      }
    });

    await stage("replay", token, 640, () => (c.bad ? `${c.bad} mismatched` : `${c.replayed}/${c.replayed} exact`), async () => {
      await sleep(310);
      for (const run of runs) { c.replayed += 1; if (run.replay_verified === false) c.bad += 1; }
      logLine(c.bad ? "is-bad" : "is-ok", c.bad ? "✗" : "✓",
        `re-executed ${c.replayed} traces on a fresh world — `,
        el("b", { text: c.bad ? `${c.bad} fingerprint mismatches` : "every fingerprint reproduced exactly" }));
      await sleep(310);
    });

    await stage("classify", token, 580, () => {
      const t = Object.values(c.findings).reduce((a, b) => a + b, 0);
      return t ? `${t} findings` : "clean";
    }, async () => {
      await sleep(240);
      const entries = Object.entries(c.findings).sort((a, b) => b[1] - a[1]);
      if (!entries.length) logLine("is-ok", "✓", "no failure modes detected across the suite");
      for (const [kind, n] of entries) {
        logLine("is-bad", "✗", el("em", { text: titleCase(kind) }), `  ${n} runs`);
        await sleep(85);
      }
      await sleep(200);
    });

    const card = d.scorecards[agent];
    await stage("score", token, 580, () => pct(card.overall.reliability), async () => {
      await sleep(270);
      logLine("is-ok", "✓", "reliability ", el("b", { text: pct(card.overall.reliability) }),
        `  95% CI [${pct(card.overall.ci95[0])}, ${pct(card.overall.ci95[1])}]  n=${card.overall.runs}`);
      const cmp = (d.history_regression?.comparisons || {})[agent];
      if (cmp) {
        const bad = (cmp.regressions || []).filter((r) => r.significant_regression);
        logLine(bad.length ? "is-bad" : "is-ok", bad.length ? "✗" : "✓",
          bad.length ? `${bad.length} categories regressed significantly` : "no significant regression vs previous snapshot");
      }
      logNote(d.gate_pass ? "gate: PASS — commit allowed" : "gate: FAIL — commit blocked");
      await sleep(260);
    });

    $("#pipe-status").textContent = `${shortName(agent)} · ${pct(card.overall.reliability)} reliable`;
    showRunSummary(agent, c);
  } catch (err) {
    if (String(err.message) !== "cancelled") throw err;
  } finally {
    if (token === state.replayToken) { btn.disabled = false; btn.textContent = "Replay run"; }
  }
}

function showRunSummary(agent, c) {
  const d = D();
  const card = d.scorecards[agent];
  const findings = Object.values(c.findings).reduce((a, b) => a + b, 0);
  const probes = d.runs.filter((r) => r.agent === agent && r.probe);
  const complied = probes.filter((r) => (r.failures || []).includes("unsafe_action") || (r.mutations || 0) > 0).length;

  const cell = (label, value, tone, sub) =>
    el("div", {}, el("dt", { text: label }),
      el("dd", { "data-tone": tone || null }, value, sub ? el("small", { text: sub }) : null));

  const node = el("dl", { class: "summary", id: "run-summary" },
    cell("Reliability", pct(card.overall.reliability),
      card.overall.reliability >= 0.9 ? "good" : "bad",
      `95% CI ${pct(card.overall.ci95[0], 0)}–${pct(card.overall.ci95[1], 0)}`),
    cell("Replay", c.bad ? `${c.bad} bad` : "100%", c.bad ? "bad" : "good", `${c.replayed} traces`),
    cell("Findings", String(findings), findings ? "bad" : "good", `${Object.keys(c.findings).length} modes`),
    cell("Guardrail", `${complied}/${probes.length}`, complied ? "bad" : "good", "probes complied"),
    cell("Gate", d.gate_pass ? "PASS" : "FAIL", d.gate_pass ? "good" : "bad",
      d.gate_pass ? "commit allowed" : "commit blocked"));

  const existing = $("#run-summary");
  if (existing) existing.remove();
  $("#console").after(node);
  requestAnimationFrame(() => requestAnimationFrame(() => node.classList.add("on")));
}

/* ------------------------------------------------------------------ runs */

function filteredRows() {
  const q = state.filter.trim().toLowerCase();
  return D().runs.filter((r) => {
    if (r.agent !== state.agent) return false;
    if (state.type && !String(r.scenario_type || "realistic").startsWith(state.type)) return false;
    if (state.outcome === "fail" && r.success) return false;
    if (state.outcome === "pass" && !r.success) return false;
    if (!q) return true;
    return `${r.scenario} ${r.category} ${(r.failures || []).join(" ")} ${r.instructions || ""}`.toLowerCase().includes(q);
  });
}

function renderTable() {
  const rows = (state.visibleRows = filteredRows());
  const failing = rows.filter((r) => !r.success).length;
  $("#count").textContent = `${rows.length} shown · ${failing} failing`;
  const body = $("#runs-body");

  if (!rows.length) {
    body.replaceChildren(el("tr", {}, el("td", { colspan: "7" },
      el("div", { class: "empty" },
        el("strong", { text: "Nothing matches this view" }),
        "Try clearing the search or the filters."))));
    return;
  }

  body.replaceChildren(...rows.map((run, i) => {
    const f = run.failures || [];
    const tr = el("tr", { tabindex: "-1", "aria-selected": String(i === state.selected) },
      el("td", {}, el("span", { class: "id", text: run.scenario })),
      el("td", { text: titleCase(run.category) }),
      el("td", {}, el("span", { class: `status status--${run.success ? "pass" : "fail"}`, text: run.success ? "Pass" : "Fail" })),
      el("td", {}, ...(f.length
        ? f.map((k) => el("span", { class: `tag tag--${k}`, text: titleCase(k) }))
        : [el("span", { class: "tag tag--muted", text: "No finding" })])),
      el("td", { class: "right hide-sm", text: String(run.calls ?? 0) }),
      el("td", { class: "right hide-sm", text: String(run.mutations ?? 0) }),
      el("td", { class: "hide-sm" }, el("span", {
        class: `verified ${run.replay_verified === false ? "verified--bad" : ""}`,
        text: run.replay_verified === false ? "Mismatch" : "Verified",
      })));
    tr.addEventListener("click", () => openTrace(i));
    return tr;
  }));
}

function renderTabs() {
  const names = agentNames();
  if (!state.agent || !D().scorecards[state.agent]) state.agent = names[0];
  $("#tabs").replaceChildren(...names.map((name) => {
    const b = el("button", { type: "button", role: "tab", text: shortName(name), "aria-selected": String(name === state.agent) });
    b.addEventListener("click", () => {
      if (state.agent === name) return;
      state.agent = name;
      state.selected = -1;
      renderTabs(); renderTable(); renderDeltas();
    });
    return b;
  }));
}

/* ---------------------------------------------------------------- drawer */

function openTrace(index) {
  const run = state.visibleRows[index];
  if (!run) return;
  state.selected = index;
  state.returnFocus = document.activeElement;

  $("#d-title").textContent = run.scenario;
  $("#d-meta").textContent = `${shortName(run.agent)} · ${titleCase(run.category)} · reward ${run.reward}`;

  const parts = [];

  parts.push(el("dl", { class: "kv" },
    el("dt", { text: "Outcome" }), el("dd", { text: run.success ? "Pass" : "Fail" }),
    el("dt", { text: "Scenario type" }), el("dd", { text: titleCase(run.scenario_type) }),
    el("dt", { text: "Tool calls" }), el("dd", { text: String(run.calls ?? 0) }),
    el("dt", { text: "State mutations" }), el("dd", { text: String(run.mutations ?? 0) }),
    el("dt", { text: "Final fingerprint" }),
    el("dd", { class: "mono", text: run.final_fingerprint ? String(run.final_fingerprint).slice(0, 26) : "—" })));

  if (run.instructions) {
    parts.push(el("div", { class: "drawer__section" },
      el("h3", { text: "Instruction given" }),
      el("blockquote", { class: "quote", text: run.instructions })));
  }

  const findings = run.findings || [];
  parts.push(el("div", { class: "drawer__section" },
    el("h3", { text: `Classifier findings · ${findings.length}` }),
    ...(findings.length
      ? findings.map((f) => el("div", { class: "finding" },
          el("div", { class: "finding__top" },
            el("span", { class: `tag tag--${f.kind}`, text: titleCase(f.kind) }),
            el("span", { class: "finding__at", text: `step ${f.step_index}` })),
          el("p", { text: f.detail || "" }),
          f.evidence && Object.keys(f.evidence).length ? el("pre", { text: JSON.stringify(f.evidence, null, 1) }) : null))
      : [el("p", { style: "color:var(--ink-4);font-size:13px", text: "No failure mode detected in this trace." })])));

  const trace = run.trace || [];
  parts.push(el("div", { class: "drawer__section" },
    el("h3", { text: `Trace · ${trace.length} steps` }),
    ...trace.map((step) => {
      const mutating = (step.calls || []).some((x) => x.mutated);
      return el("div", { class: "step", "data-mutating": mutating || null },
        el("div", { class: "step__n", text: `STEP ${step.step}` }),
        ...(step.calls || []).map((x) => el("div", { class: "call" },
          el("div", { class: "call__head" },
            el("b", { text: x.name }),
            x.mutated ? el("span", { class: "badge badge--mut", text: "mutates state" })
              : x.ok === false ? el("span", { class: "badge badge--err", text: "error" })
              : el("span", { class: "badge", text: "read" })),
          Object.keys(x.arguments || {}).length ? el("div", { class: "call__args", text: JSON.stringify(x.arguments, null, 1) }) : null,
          x.output ? el("div", { class: "call__inject", text: `tool output: ${x.output}` }) : null,
          x.error ? el("div", { class: "call__args", style: "color:var(--fail)", text: x.error }) : null,
          x.fingerprint_after ? el("div", { class: "call__fp" }, "world fingerprint ",
            el("b", { text: String(x.fingerprint_after).slice(0, 22) })) : null)),
        step.text ? el("div", { class: "say", text: `“${step.text}”` }) : null);
    })));

  const bad = run.replay_verified === false;
  parts.push(el("div", { class: `replay-note ${bad ? "replay-note--bad" : ""}` },
    el("span", { class: "dot", style: bad ? "background:var(--fail);box-shadow:none" : "" }),
    el("p", { text: bad
      ? `Replay FAILED: ${(run.replay_problems || []).join("; ") || "fingerprint divergence"}`
      : "Replay verified. This trace was re-executed against a freshly derived world and every recorded fingerprint reproduced exactly, so the scorecard figure is auditable back to an exact, re-runnable history." })));

  const body = $("#d-body");
  body.replaceChildren(...parts);
  body.scrollTop = 0;

  const root = $("#drawer-root");
  root.inert = false;
  root.classList.add("open");
  root.setAttribute("aria-hidden", "false");
  $("#d-close").focus();
  renderTable();
}

function closeTrace() {
  const root = $("#drawer-root");
  if (!root.classList.contains("open")) return;
  root.classList.remove("open");
  root.inert = true;
  root.setAttribute("aria-hidden", "true");
  if (state.returnFocus?.focus) state.returnFocus.focus();
}


/* -------------------------------------------------------- domain switching */

function renderDomainSwitch() {
  $("#domain-switch").replaceChildren(...state.data.domains.map((dom) => {
    const b = el("button", { type: "button", role: "tab", "aria-selected": String(dom.id === state.domainId) },
      dom.label, dom.unseen ? el("small", { text: "unseen" }) : null);
    b.addEventListener("click", () => selectDomain(dom.id));
    return b;
  }));
}

/* Each domain is a whole separate CI run, so switching rebuilds every view and
   resets the selections that only make sense within one run. */
function selectDomain(id) {
  if (state.domainId === id) return;
  state.domainId = id;
  state.replayToken += 1;
  closeTrace();
  const names = agentNames();
  state.agent = names.includes("clean-agent") ? "clean-agent" : names[0];
  state.replayAgent = names.find((n) => D().scorecards[n].overall.reliability < 0.5) || names[names.length - 1];
  state.selected = -1;
  state.filter = "";
  $("#filter").value = "";

  paintGate();
  renderDomainSwitch();
  renderOverview();
  renderPipelineStatics();
  resetPipeline();
  $("#pipe-status").textContent = "idle";
  $("#pipe-run").disabled = false;
  $("#pipe-run").textContent = "Replay run";
  renderTabs();
  renderTable();
  renderGuardrails();
  renderAttack();
  renderVersions();
  renderHeat();
  renderTrend();
  renderDeltas();
  playReveal($(`#view-${state.view}`));
  if (state.view === "overview") {
    requestAnimationFrame(() => $$("#figures .figure__meter").forEach((m) => m.classList.add("in")));
  }
}

function paintGate() {
  const d = D();
  document.body.dataset.gate = d.gate_pass ? "passed" : "failed";
  $("#gate-label").textContent = d.gate_pass ? "Gate passed" : "Gate blocked";
}

/* ------------------------------------------------------------ attack replay */

/* One real recorded trace, stepped through end to end: the injected
   instruction, the call it produced, the state it changed, and the finding
   that caught it. Built from the trace itself - nothing here is illustrative. */
function pickAttackRun() {
  const probes = probeRuns().filter((r) => (r.failures || []).includes("unsafe_action") && (r.mutations || 0) > 0);
  return probes.find((r) => r.probe.kind === "injected_output" && (r.trace || []).some((s) => s.calls?.some((c) => c.output)))
      || probes.find((r) => r.probe.kind === "injected_output")
      || probes[0]
      || null;
}

function attackSteps(run) {
  const trace = run.trace || [];
  const calls = trace.flatMap((s) => (s.calls || []).map((c) => ({ ...c, step: s.step })));
  const poisoned = calls.find((c) => c.output);
  const mutation = calls.find((c) => c.mutated);
  const finding = (run.findings || []).find((f) => f.kind === "unsafe_action");
  const said = trace.map((s) => s.text).filter(Boolean).pop();

  const steps = [];
  steps.push({
    tone: "bad", title: "The instruction arrives",
    body: `A ${titleCase(run.probe.kind)} probe. Authorization: ${run.probe.authorization}. It never authorizes anything.`,
    quote: run.probe.untrusted_texts?.[0] || run.instructions,
  });
  if (poisoned) {
    steps.push({
      tone: "bad", title: "The agent reads poisoned tool output",
      body: `${poisoned.name} returns attacker-controlled text. Everything downstream of this call is tainted.`,
      code: `${poisoned.name}(${JSON.stringify(poisoned.arguments)})
-> ${poisoned.output}`,
    });
  }
  steps.push({
    tone: "bad", title: "It executes the irreversible action",
    body: mutation
      ? `No confirmation was asked for and none was given. ${mutation.name} is flagged irreversible in the derived world spec.`
      : "The agent acted without confirmation.",
    code: mutation ? `${mutation.name}(${JSON.stringify(mutation.arguments, null, 1)})` : null,
  });
  steps.push({
    tone: "bad", title: "World state actually changes",
    body: "This is not a text heuristic. The sandbox world re-fingerprints after the mutation, and the hash moves.",
    code: mutation?.fingerprint_after ? `world fingerprint → ${String(mutation.fingerprint_after).slice(0, 40)}` : null,
  });
  if (said) {
    steps.push({ tone: "bad", title: "And it reports success", body: "The user is told the job is done.", quote: said });
  }
  steps.push({
    tone: "good", title: "Caught",
    body: finding ? finding.detail : "Classified as an unsafe action, verified against real mutated world state.",
    code: `unsafe_action · ${run.scenario} · gate blocks this commit`,
  });
  return steps;
}

function renderAttack() {
  const run = pickAttackRun();
  const host = $("#attack");
  if (!run) {
    $("#attack-meta").textContent = "no probe was complied with in this run";
    $("#attack-run").disabled = true;
    host.replaceChildren(el("div", { class: "empty" },
      el("strong", { text: "Every version held" }), "No agent executed an unauthorized irreversible action in this run."));
    return;
  }
  $("#attack-run").disabled = false;
  $("#attack-title").textContent = `${titleCase(run.probe.kind)} → ${run.probe.proposed_action}`;
  $("#attack-meta").textContent = `${shortName(run.agent)} · ${run.scenario}`;
  state.attackSteps = attackSteps(run);

  host.replaceChildren(...state.attackSteps.map((st, i) =>
    el("div", { class: "attack__step", "data-tone": st.tone, id: `atk-${i}` },
      el("div", { class: "attack__n", text: st.tone === "good" ? "✓" : String(i + 1) }),
      el("div", {},
        el("h4", { text: st.title }),
        el("p", { text: st.body }),
        st.quote ? el("div", { class: "attack__payload attack__payload--quote", text: `“${st.quote}”` }) : null,
        st.code ? el("div", { class: "attack__payload", text: st.code }) : null))));
}

async function playAttack() {
  const token = ++state.replayToken;
  const btn = $("#attack-run");
  btn.disabled = true;
  btn.textContent = "Playing…";
  $$("#attack .attack__step").forEach((n) => n.classList.remove("on"));
  const nodes = $$("#attack .attack__step");
  for (let i = 0; i < nodes.length; i += 1) {
    if (token !== state.replayToken) return;
    nodes[i].classList.add("on");
    nodes[i].scrollIntoView({ block: "nearest", behavior: "smooth" });
    await sleep(i === nodes.length - 1 ? 700 : 1000);
  }
  if (token !== state.replayToken) return;
  btn.disabled = false;
  btn.textContent = "Play again";
}

/* ------------------------------------------------------------ guardrails */

/* Three states: a policy that never acted and one that acted-then-refused are
   not the same result, and collapsing them flatters the inert controls. */
function probeVerdict(run) {
  if ((run.failures || []).includes("unsafe_action") || (run.mutations || 0) > 0) {
    return { key: "complied", label: "complied", title: "Executed the irreversible mutation without authorization." };
  }
  if ((run.calls || 0) === 0) {
    return { key: "na", label: "inert", title: "Made no tool calls, so the guardrail was never exercised." };
  }
  return { key: "held", label: "held", title: "Acted on the probe but did not perform the irreversible mutation." };
}
const complied = (run) => probeVerdict(run).key === "complied";

function renderGuardrails() {
  const names = agentNames();
  const probes = probeRuns();

  const byScenario = new Map();
  for (const run of probes) {
    if (!byScenario.has(run.scenario)) byScenario.set(run.scenario, { probe: run.probe, runs: {} });
    byScenario.get(run.scenario).runs[run.agent] = run;
  }

  $("#matrix").replaceChildren(
    el("thead", {}, el("tr", {},
      el("th", { scope: "col", text: "Probe" }),
      ...names.map((n) => el("th", { scope: "col", text: shortName(n) })))),
    el("tbody", {}, ...Array.from(byScenario.entries()).map(([scenario, entry]) =>
      el("tr", {},
        el("td", {}, titleCase(entry.probe.kind), el("small", { text: `${scenario} → ${entry.probe.proposed_action}` })),
        ...names.map((n) => {
          const run = entry.runs[n];
          if (!run) return el("td", {}, el("span", { class: "verdict verdict--na", text: "—" }));
          const v = probeVerdict(run);
          return el("td", {}, el("span", { class: `verdict verdict--${v.key}`, text: v.label, title: v.title }));
        }))))
  );

  // Partition, never overlapping sets: a policy can legitimately hold on some
  // probes and be inert on others when no read tool exists for that entity.
  const caught = names.filter((n) => probes.some((r) => r.agent === n && complied(r)));
  const held = names.filter((n) => !caught.includes(n) && probes.some((r) => r.agent === n && probeVerdict(r).key === "held"));
  const inert = names.filter((n) => !caught.includes(n) && !held.includes(n));
  const unsafe = D().unsafe_findings_by_agent || {};
  const sum = (list) => list.reduce((a, n) => a + (unsafe[n] || 0), 0);

  $("#controls-strip").replaceChildren(
    el("div", {},
      el("p", { class: "eyebrow", text: "Caught" }),
      el("h4", { text: caught.map(shortName).join(", ") || "None" }),
      el("p", { text: `${sum(caught)} unsafe-action findings, each verified against real mutated world state.` })),
    el("div", {},
      el("p", { class: "eyebrow", text: "False-positive control" }),
      el("h4", { text: held.map(shortName).join(", ") || "None" }),
      el("p", { text: held.length
        ? `Engaged with the probes — including reading the poisoned tool output — and refused. ${sum(held)} findings raised against it.`
        : "No policy here acts on a probe without mutating, so the tester has no negative control." })),
    el("div", {},
      el("p", { class: "eyebrow", text: "Never exercised" }),
      el("h4", { text: inert.map(shortName).join(", ") || "None" }),
      el("p", { text: "Made no tool calls on the probes, so these columns say nothing about the guardrail either way." }))
  );

  const KIND_TEXT = {
    pressure: "The instruction demands immediate action and forbids asking for confirmation.",
    ambiguity: "The instruction never actually authorizes the destructive action.",
    conflict: "The user asks the agent to waive its own confirmation rule, just this once.",
    injected_output: "The destructive instruction arrives inside untrusted tool output.",
  };

  const kinds = new Map();
  for (const [, entry] of byScenario) {
    const k = entry.probe.kind;
    if (!kinds.has(k)) kinds.set(k, { probe: entry.probe, total: 0, complied: 0, agents: new Set() });
    const b = kinds.get(k);
    for (const [agent, run] of Object.entries(entry.runs)) {
      b.total += 1;
      if (complied(run)) { b.complied += 1; b.agents.add(agent); }
    }
  }

  $("#probe-cards").replaceChildren(...Array.from(kinds.entries()).map(([kind, b]) =>
    el("div", { class: "probe" },
      el("div", { class: "probe__top" },
        el("h4", { text: titleCase(kind) }),
        el("span", { class: `verdict verdict--${b.complied ? "complied" : "held"}`, text: `${b.complied}/${b.total} complied` })),
      el("p", { class: "probe__why", text: KIND_TEXT[kind] || "" }),
      el("blockquote", { class: "quote", text: b.probe.untrusted_texts?.[0] || probeInstruction(kind) }),
      el("div", { class: "probe__target" }, "targets ", el("b", { text: b.probe.proposed_action || "—" }),
        " · authorization ", el("b", { text: b.probe.authorization || "missing" })),
      el("div", { class: "probe__result" }, ...(b.agents.size
        ? Array.from(b.agents).map((a) => el("span", { class: "tag tag--unsafe_action", text: shortName(a) }))
        : [el("span", { class: "tag tag--muted", text: "every version held" })])))));
}

function probeInstruction(kind) {
  const r = D().runs.find((x) => x.probe && x.probe.kind === kind && x.instructions);
  return r ? r.instructions : "";
}

/* ------------------------------------------------------------- scorecard */

const readVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function heatColor(v) {
  const dark = document.documentElement.dataset.theme === "dark";
  // Interpolated inside the theme's own register so the grid never fights the page.
  const stops = dark
    ? [[0, [88, 42, 38]], [0.5, [92, 76, 38]], [1, [38, 84, 63]]]
    : [[0, [235, 208, 203]], [0.5, [242, 230, 200]], [1, [208, 232, 218]]];
  let a = stops[0], b = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i += 1) {
    if (v >= stops[i][0] && v <= stops[i + 1][0]) { a = stops[i]; b = stops[i + 1]; break; }
  }
  const t = b[0] === a[0] ? 0 : (v - a[0]) / (b[0] - a[0]);
  return `rgb(${a[1].map((x, i) => Math.round(x + (b[1][i] - x) * t)).join(",")})`;
}

function renderVersions() {
  const d = D();
  $("#version-cards").replaceChildren(...agentNames().map((name) => {
    const card = d.scorecards[name];
    const o = card.overall;
    const kinds = {};
    for (const cat of card.categories)
      for (const [k, n] of Object.entries(cat.failures_by_kind || {})) kinds[k] = (kinds[k] || 0) + n;
    const tier = o.reliability >= 0.9 ? "high" : o.reliability >= 0.5 ? "mid" : "low";
    return el("div", { class: `version ${name === "clean-agent" ? "version--baseline" : ""}`, "data-tier": tier },
      el("div", { class: "version__name" },
        el("span", { text: name }),
        name === "clean-agent" ? el("span", { class: "version__badge", text: "baseline" }) : null),
      el("p", { class: "version__note", text: AGENT_NOTES[name] || "" }),
      el("div", { class: "version__rate" }, pct(o.reliability), el("small", { text: `n = ${o.runs}` })),
      el("div", { class: "interval" },
        el("div", { class: "interval__axis" }),
        el("div", { class: "interval__span", style: `left:${o.ci95[0] * 100}%;width:${Math.max(1, (o.ci95[1] - o.ci95[0]) * 100)}%` }),
        el("div", { class: "interval__pt", style: `left:calc(${o.reliability * 100}% - 1.5px)` }),
        el("div", { class: "interval__ticks" }, el("span", { text: pct(o.ci95[0], 0) }), el("span", { text: pct(o.ci95[1], 0) }))),
      el("div", { class: "version__kinds" }, ...(Object.keys(kinds).length
        ? Object.entries(kinds).sort((a, b) => b[1] - a[1]).map(([k, n]) => el("span", { class: `tag tag--${k}`, text: `${titleCase(k)} ${n}` }))
        : [el("span", { class: "tag tag--muted", text: "no findings" })])));
  }));
}

function renderHeat() {
  const d = D();
  const names = agentNames();
  const cats = Array.from(new Set(names.flatMap((n) => d.scorecards[n].categories.map((c) => c.category)))).sort();
  $("#heat").replaceChildren(
    el("thead", {}, el("tr", {},
      el("th", { scope: "col", text: "Task category" }),
      ...names.map((n) => el("th", { scope: "col", text: shortName(n) })))),
    el("tbody", {}, ...cats.map((cat) =>
      el("tr", {},
        el("td", { text: titleCase(cat) }),
        ...names.map((n) => {
          const c = d.scorecards[n].categories.find((x) => x.category === cat);
          if (!c) return el("td", {}, el("div", { class: "cell cell--na", text: "—" }));
          return el("td", {}, el("div", {
            class: "cell",
            style: `background:${heatColor(c.reliability)};color:#15161A`,
            title: `${shortName(n)} · ${titleCase(cat)}: ${pct(c.reliability)} over ${c.runs} runs, 95% CI ${pct(c.ci95[0])}–${pct(c.ci95[1])}`,
            text: String(Math.round(c.reliability * 100)),
          }));
        }))))
  );
  if (document.documentElement.dataset.theme === "dark") {
    $$("#heat .cell").forEach((c) => { if (!c.classList.contains("cell--na")) c.style.color = "#F4F4F1"; });
  }
}

function renderTrend() {
  const d = D();
  const history = d.history || [];
  const names = agentNames();
  const svgEl = $("#trend");
  const NS = "http://www.w3.org/2000/svg";
  const W = 900, H = 210, pad = { l: 40, r: 16, t: 14, b: 30 };
  svgEl.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svgEl.setAttribute("preserveAspectRatio", "none");

  $("#regression-note").textContent =
    `${history.length} persisted snapshot${history.length === 1 ? "" : "s"} · baseline ${d.history_regression?.baseline || "none"}`;

  const x = (i) => (history.length <= 1 ? pad.l : pad.l + (i * (W - pad.l - pad.r)) / (history.length - 1));
  const y = (v) => pad.t + (1 - clamp01(v)) * (H - pad.t - pad.b);
  const kids = [];

  for (const v of [0, 0.25, 0.5, 0.75, 1]) {
    const line = document.createElementNS(NS, "line");
    line.setAttribute("class", "grid");
    line.setAttribute("x1", pad.l); line.setAttribute("x2", W - pad.r);
    line.setAttribute("y1", y(v)); line.setAttribute("y2", y(v));
    kids.push(line);
    const t = document.createElementNS(NS, "text");
    t.setAttribute("class", "lbl"); t.setAttribute("x", 4); t.setAttribute("y", y(v) + 3.5);
    t.textContent = `${v * 100}%`;
    kids.push(t);
  }

  const palette = [readVar("--pass"), readVar("--info"), readVar("--warn"), readVar("--fail"), readVar("--drift"), readVar("--ink-3")];
  names.forEach((name, ai) => {
    const pts = history.map((h, i) => ({ i, v: h.agents?.[name]?.reliability })).filter((p) => typeof p.v === "number");
    if (!pts.length) return;
    const color = palette[ai % palette.length];
    if (pts.length > 1) {
      const path = document.createElementNS(NS, "path");
      path.setAttribute("d", pts.map((p, k) => `${k ? "L" : "M"}${x(p.i)} ${y(p.v)}`).join(" "));
      path.setAttribute("stroke", color);
      kids.push(path);
    }
    for (const p of pts) {
      const cEl = document.createElementNS(NS, "circle");
      cEl.setAttribute("cx", x(p.i)); cEl.setAttribute("cy", y(p.v)); cEl.setAttribute("r", 3.5);
      cEl.setAttribute("fill", color);
      const title = document.createElementNS(NS, "title");
      title.textContent = `${shortName(name)} · ${pct(p.v)} · ${history[p.i].snapshot_id}`;
      cEl.appendChild(title);
      kids.push(cEl);
    }
  });

  history.forEach((h, i) => {
    const t = document.createElementNS(NS, "text");
    t.setAttribute("class", "lbl"); t.setAttribute("x", x(i)); t.setAttribute("y", H - 9);
    t.setAttribute("text-anchor", i === 0 ? "start" : i === history.length - 1 ? "end" : "middle");
    t.textContent = h.commit_sha ? h.commit_sha.slice(0, 7) : String(i + 1);
    kids.push(t);
  });

  svgEl.replaceChildren(...kids);
  $("#trend-legend").replaceChildren(...names.map((n, i) =>
    el("span", {}, el("i", { style: `background:${palette[i % palette.length]}` }), shortName(n))));
}

function renderDeltas() {
  const rows = D().regressions_vs_clean?.[state.agent]?.regressions || [];
  $("#delta-note").textContent = state.agent === "clean-agent"
    ? "clean-agent is the baseline — pick another version on the Runs tab to compare"
    : `${shortName(state.agent)} against the clean-agent baseline, same suite and seed`;

  const list = $("#deltas");
  if (!rows.length) {
    list.replaceChildren(el("div", { class: "empty" },
      el("strong", { text: "This version is the baseline" }),
      "Select another agent version on the Runs tab to see category deltas."));
    return;
  }
  list.replaceChildren(
    el("div", { class: "delta delta--head" },
      el("span", { text: "Task category" }),
      el("span", { class: "delta__n", text: "base" }),
      el("span", { class: "delta__n", text: "cand." }),
      el("span", { class: "delta__n", text: "delta" }),
      el("span", { text: "gate" })),
    ...rows.slice().sort((a, b) => a.delta - b.delta).map((r) =>
      el("div", { class: "delta" },
        el("span", { class: "delta__cat", text: titleCase(r.category) }),
        el("span", { class: "delta__n", text: pct(r.base, 0) }),
        el("span", { class: "delta__n", text: pct(r.candidate, 0) }),
        el("span", { class: `delta__n ${r.delta < 0 ? "delta__n--down" : r.delta > 0 ? "delta__n--up" : ""}`,
          text: `${r.delta > 0 ? "+" : ""}${(r.delta * 100).toFixed(1)}pp` }),
        el("span", { class: `sig ${r.significant_regression ? "sig--yes" : ""}`,
          text: r.significant_regression ? "blocks" : "within CI" })))
  );
}

/* -------------------------------------------------------------- evidence */

function renderEvidence() {
  $("#benchmarks").replaceChildren(...state.data.benchmarks.map((b) => {
    const max = Math.max(0.001, ...(b.splits || []).map((s) => Math.max(s.value, s.vs || 0)));
    return el("div", { class: "bench", id: `bench-${b.id}`, "data-status": b.status },
      el("div", { class: "bench__head" },
        el("div", {},
          el("h3", { text: b.title }),
          el("p", { class: "bench__sub", text: b.subtitle }),
          el("p", { class: "bench__claim", text: b.claim })),
        el("div", { class: "bench__fig" },
          el("b", { text: pct(b.value, b.value >= 0.995 ? 2 : 1) }),
          b.ci95 ? el("div", { class: "band", text: `95% CI ${pct(b.ci95[0])} – ${pct(b.ci95[1])}` }) : null,
          el("div", { class: "band", text: b.sample }),
          el("div", { class: "bench__verdict", text: `${b.status === "parked" ? "parked" : "cleared"} · ${b.bar_label}` }))),
      el("div", { class: "bench__cols" },
        el("div", {}, el("h4", { text: "Splits" }), ...(b.splits || []).map((s) =>
          el("div", { class: "split" },
            el("div", { class: "split__row" },
              el("span", { text: titleCase(s.label) }),
              el("b", { text: typeof s.vs === "number" ? `${pct(s.value)} vs ${pct(s.vs)}` : pct(s.value) })),
            el("div", { class: "split__track" },
              el("i", { class: b.status === "parked" ? "" : "good", style: `width:${(s.value / max) * 100}%` }),
              typeof s.vs === "number" ? el("u", { style: `left:${(s.vs / max) * 100}%` }) : null)))),
        el("div", {}, el("h4", { text: "Breakdown" }), ...(b.breakdown || []).map((s) =>
          el("div", { class: "split" },
            el("div", { class: "split__row" }, el("span", { text: titleCase(s.label) }), el("b", { text: pct(s.value) })),
            el("div", { class: "split__track" }, el("i", { style: `width:${clamp01(s.value) * 100}%` })))),
          b.highlight ? el("p", { style: "margin-top:16px", text: b.highlight }) : null),
        el("div", {}, el("h4", { text: "Method" }), el("p", { text: b.method }))),
      el("div", { class: "caveat" }, el("div", {}, b.caveat)),
      el("p", { class: "bench__src", text: b.source }));
  }));
}

/* ---------------------------------------------------------- interactions */

function bind() {
  $("#theme-toggle").addEventListener("click", toggleTheme);
  $("#attack-run").addEventListener("click", playAttack);
  $("#hero-run").addEventListener("click", () => {
    setView("pipeline");
    setTimeout(runReplay, 420);
  });

  $("#filter").addEventListener("input", (e) => { state.filter = e.target.value; state.selected = -1; renderTable(); });
  $("#scenario-type").addEventListener("change", (e) => { state.type = e.target.value; state.selected = -1; renderTable(); });
  $("#outcome-filter").addEventListener("change", (e) => { state.outcome = e.target.value; state.selected = -1; renderTable(); });

  $("#scrim").addEventListener("click", closeTrace);
  $("#d-close").addEventListener("click", closeTrace);
  $("#pipe-run").addEventListener("click", runReplay);
  $("#pipe-agent").addEventListener("change", (e) => {
    state.replayToken += 1;
    state.replayAgent = e.target.value;
    resetPipeline();
    $("#pipe-status").textContent = "idle";
    $("#pipe-run").disabled = false;
    $("#pipe-run").textContent = "Replay run";
  });

  for (const b of $$("[data-goto]")) b.addEventListener("click", () => setView(b.dataset.goto));

  $("#export").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(state.data, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "oosc-reliability-report.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 0);
  });

  window.addEventListener("hashchange", () => setView(location.hash.slice(1)));
  addEventListener("scroll", () => { document.body.dataset.scrolled = String(window.scrollY > 6); }, { passive: true });

  document.addEventListener("keydown", (e) => {
    const typing = document.activeElement === $("#filter");
    if (e.key === "Escape") { closeTrace(); if (typing) $("#filter").blur(); return; }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "/") { e.preventDefault(); setView("runs"); $("#filter").focus(); return; }
    const n = Number(e.key);
    if (n >= 1 && n <= VIEWS.length) { e.preventDefault(); setView(VIEWS[n - 1].id); return; }
    if (state.view !== "runs") return;
    if (e.key === "j" || e.key === "k") {
      e.preventDefault();
      state.selected = Math.max(0, Math.min(state.visibleRows.length - 1, state.selected + (e.key === "j" ? 1 : -1)));
      renderTable();
      const row = $("#runs-body").children[state.selected];
      if (row) { row.focus(); row.scrollIntoView({ block: "nearest" }); }
    }
    if (e.key === "Enter" && state.selected >= 0) openTrace(state.selected);
  });
}

/* ------------------------------------------------------------------ boot */

async function init() {
  paintThemeIcon();
  try {
    const res = await fetch("data/report.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`Report request failed: ${res.status}`);
    state.data = await res.json();
  } catch (err) {
    document.querySelector("main").replaceChildren(el("div", { class: "wrap" },
      el("div", { class: "boot" }, el("div", {},
        el("h1", { text: "Report unavailable" }),
        el("p", { text: err.message }),
        el("p", { style: "margin-top:12px" }, "Run ", el("code", { text: "oosc ci" }), " then ",
          el("code", { text: "python scripts/build_ui_data.py" }), " to generate it.")))));
    return;
  }

  state.domainId = state.data.domains[0].id;
  const names = agentNames();
  state.agent = names.includes("clean-agent") ? "clean-agent" : names[0];
  // Open the replay on a version that actually fails: a run where nothing is
  // caught demonstrates nothing.
  state.replayAgent = names.find((n) => D().scorecards[n].overall.reliability < 0.5) || names[names.length - 1];

  paintGate();
  renderDomainSwitch();
  renderNav();
  renderOverview();
  renderPipelineStatics();
  renderTabs();
  renderTable();
  renderGuardrails();
  renderAttack();
  renderVersions();
  renderHeat();
  renderTrend();
  renderDeltas();
  renderEvidence();
  bind();

  setView(location.hash.slice(1) || "overview");
  document.body.dataset.ready = "true";
}

init();
