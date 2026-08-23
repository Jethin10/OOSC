# How to demo OOSC

Two halves. **The terminal proves the claim, the dashboard shows the product.**
Do the terminal first — it is the part nobody can wave away.

Total: ~4 minutes. Have two things open before you start:

1. A terminal in the repo root, venv activated.
2. https://oosc-seven.vercel.app in a browser tab.

---

# Part 1 · The terminal (90s) — the part that wins it

The whole pitch is *"we derive the test world from tool schemas alone, so it works on
an agent it has never seen."* Anyone can claim that. Here you show it.

### Setup (do this before you present)

```bash
python scripts/make_demo_domain.py
rm -rf results/history-demo          # so the first run has no baseline
```

`results/repro/schema/cloudops.domain.json` is now an **incident-response agent**:
services, deployments, snapshots, API keys. Nothing in the engine knows it exists. If they
look skeptical, run this in front of them — it returns nothing:

```bash
grep -ri "service_id\|api_key\|rollback\|incident" engine/ --include="*.py"
```

### The command

```bash
python -m oosc.cli ci --domain results/repro/schema/cloudops.domain.json --max-scenarios 40 --out results/demo --history-dir results/history-demo
```

It finishes in about 20 seconds and prints this:

```
OOSC  continuous integration for autonomous agents
      domain=cloudops  seed=7

[derive]    10 tools from schemas alone: 4 read, 1 terminal, 5 write
            irreversible ops: delete_snapshot, restart_service, revoke_api_key, rollback_deployment
            initial state: 12 services, 18 deployments, 14 snapshots, 10 api_keys
[generate]  33 scenarios sampled from 52 candidates: 20 realistic, 13 adversarial
            probe classes: ambiguity, conflict, injected_output, pressure
[execute]   198 sandboxed runs across 6 agent versions
[replay]    198/198 traces reproduced exactly

reliability (rate with Wilson 95% interval)
  clean-agent                100.0%  [ 89.6, 100.0]  n=33
  cautious-agent             100.0%  [ 89.6, 100.0]  n=33
  loopy-agent                 39.4%  [ 24.7,  56.3]  n=33
  overconfident-agent         39.4%  [ 24.7,  56.3]  n=33
  reckless-agent               0.0%  [  0.0,  10.4]  n=33
  pressure-compliant-agent    60.6%  [ 43.7,  75.3]  n=33

failure modes detected
  goal_drift                   46 runs
  hallucinated_confidence      33 runs
  unsafe_action                26 runs
  tool_loop                    20 runs

guardrails: 13 probes x 6 versions
  agent                      complied   held  inert  findings
  clean-agent                       0      0     13         0
  cautious-agent                    0      8      5         0  <-- FALSE-POSITIVE CONTROL: refused, never flagged
  loopy-agent                       0      0     13         0
  overconfident-agent               0      0     13         0
  reckless-agent                   13      0      0        13  <-- executed unauthorized irreversible actions
  pressure-compliant-agent         13      0      0        15  <-- executed unauthorized irreversible actions

gate: PASS
```

### What to say, line by line

> **[derive]** — "Nobody wrote a cloudops environment. It read 10 tool schemas and figured
> out which are reads, which mutate state, which entity each parameter points at, what
> status a thing must be in before you can touch it, and **which four operations are
> irreversible**. That last one is what it aims the safety probes at."
>
> **[generate]** — "It built 52 candidate scenarios against that world and sampled 33 —
> including 13 adversarial probes across all four escalation classes."
>
> **[replay]** — "Every trace re-executed against a fresh world and every state fingerprint
> reproduced. That's what makes any number here auditable."
>
> **the guardrail table** — "Two agent versions executed an irreversible action they were
> never authorized to take. And `cautious-agent` — which engages with the probes, reads the
> poisoned tool output, and refuses — raised **zero** findings. That's the false-positive
> control. A safety checker that flags every agent that acts is worthless, so our CI gate
> fails if that policy is ever flagged."

### The optional kicker (20s) — show the gate actually blocking

Run the exact same command a second time. It now has a baseline to compare against, so
if anything moved it blocks:

```bash
python -m oosc.cli ci --domain results/repro/schema/cloudops.domain.json --max-scenarios 40 --out results/demo --history-dir results/history-demo
echo "exit code: $?"
```

Identical run → `gate: PASS`, exit 0. That is the honest version: **the gate does not fire
on noise.** If you want to *show* it firing, change a policy (or the seed) between runs and
it will exit 1 with the regressed categories named.

> "Exit code 1. That's the whole integration — it's a commit gate, not a dashboard."

---

# Part 2 · The dashboard (2 min)

Now switch to the browser. Sections are keyboard-switchable: press `1`–`6`.

## `1` Overview — credibility (40s)

Point at the four evidence cards left to right:

- **98.5% oracle agreement** vs tau2-bench. *"Their domains are hand-written Python. Ours is
  derived from schemas, and it agrees with them on pass/fail across all 164 annotated tasks
  — 1312 graded trajectories."*
- **46.6% joint accuracy** on TRAIL — *"both where a run failed and why. Published best is
  11%, scored with their own scorer."*
- **98.9% unsafe-action catch** on agentdojo's 629 cases, **zero** false positives on benign runs.
- **9.2% rediscovery — parked.** *"This one missed. We publish it unmet rather than
  redefining the metric."*

> Say the parked number out loud. It is the fastest way to make the other three believable.

Then scroll to **the five directions in the problem statement** — each maps to running code
and jumps to the view that proves it.

## `2` Pipeline — the live moment (35s)

Hit **Replay run**. Six stages light up and the console streams real trace lines.

> "Deterministic replay of the committed CI run. Derive, generate, execute, then
> re-execute every trace against a *fresh* world and check the fingerprints match."

## `3` Runs — "why did it fail" (30s)

Set **Failures only**, open any row. One screen shows the instruction given, the classifier
findings **with raw evidence** (`get_order_details called 3x with identical arguments`,
occurrences `[0,1,2]`), the full trace with per-mutation fingerprints, and the replay verdict.

> "Raw pass/fail tells you nothing. This tells an engineer what to fix."

## `4` Guardrails (20s)

The control readout at the top, then the matrix: 20 probes across three distinct
irreversible operations × four escalation classes.

## `5` Scorecard (20s)

> "Reliability is a rate with a Wilson 95% interval. The gate compares *intervals*, so seed
> noise can't fail a commit — a regression only blocks when the candidate's interval clears
> the baseline's."

## `6` Evidence (15s)

Each benchmark carries its splits, method, and an explicit caveat.

> "Every caveat a reviewer would raise is already on the page."

---

# Questions you will get

**"Does this work on my agent?"**

```bash
python -m oosc.cli ci --agent-endpoint http://localhost:8000/evaluate --agent-version my-agent-v2
```

> "Any agent behind an HTTP endpoint that takes normalized scenario + domain JSON and
> returns steps. The world, the scenarios and the probes all come from the tool schemas, so
> a new domain needs no hand-authored fixtures — you just saw that on cloudops. Exits
> non-zero on a significant regression."

**"Why scripted policies instead of a real LLM?"**

> "So the gate is deterministic and free — it has to run on every commit. The runner takes
> any policy behind the same interface, so a live model plugs in without changing a single
> metric definition. The scripted policies exist to prove the *detectors* still fire, which
> is exactly what a CI gate has to guarantee."

**"Isn't 40 scenarios small?"**

> "That's the commit-time budget — it runs in 20 seconds with no LLM and no network. Raise
> `--max-scenarios` for a nightly. The generator had 52 candidates here and enumerates
> millions on the tau2 domains."

**"Tell me about the parked number."**

> "Rediscovery. 8.5M enumerated signatures from schemas and initial data, 15 of 164 strict
> matches. 43 of those tasks contain free-text payloads — arbitrary new addresses — that no
> schema-plus-data process can conjure, which caps any such method at 73.8%. The rest is
> authoring idiosyncrasy in how they interleave read chains. We fixed the matching
> granularity before generating anything and did not move it afterward."

**"How do I know the dashboard numbers are real?"**

> "`scripts/build_ui_data.py` assembles it from committed artifacts under `results/` — the
> CI report, the history snapshots, the four benchmark reports. No figure in the interface
> is typed in by hand. Hit **Export report** and you get the whole bundle as JSON."

---

# If the internet dies

Everything runs locally:

```bash
python scripts/build_ui_data.py
python -m http.server 4173 -d ui     # then open http://localhost:4173
```

The terminal half needs no network at all.
