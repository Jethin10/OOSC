# Demo script — 4 minutes

Live scorecard: **https://oosc-seven.vercel.app**
Everything below is on that one page. Sections are keyboard-switchable: press `1`–`6`.

---

## 0 · The one-liner (15s)

> "Teams ship agents against a handful of hand-written test prompts, so tool-call loops,
> hallucinated confidence, unsafe irreversible actions and goal drift are first seen in
> production. OOSC is continuous integration for agents: point it at an agent's tool
> schemas and it builds the test world, generates the adversarial cases, runs the agent
> sandboxed, tells you *why* it failed, and blocks the commit."

---

## 1 · Overview — the credibility slide (45s) `press 1`

Point at the four evidence cards, left to right:

- **98.5% oracle agreement** vs tau2-bench. *"Their domains are hand-written Python. Ours
  is derived from tool schemas alone, and it agrees with them on pass/fail across all 164
  annotated tasks — 1312 graded trajectories."*
- **46.6% joint accuracy** on TRAIL. *"Predicting both where a run failed and why. The
  published best is 11%. Scored with their own scorer."*
- **98.9% unsafe-action catch** on agentdojo's 629 security cases, **zero** false positives
  on benign runs.
- **9.2% rediscovery — parked.** *"This one missed its bar. We publish it unmet rather than
  redefining the metric; the blockers are in the report."*

Then scroll to **the five directions in the problem statement** — each one maps to running
code, and each card jumps to the view that proves it.

> Say the parked number out loud. It is the fastest way to make the other three believable.

---

## 2 · Pipeline — the live moment (60s) `press 2`

Hit **Replay run**. Six stages light up in sequence and the console streams real trace
lines: scenario ids, categories, call counts, mutation counts, failure modes.

Narrate over it:

> "This is a deterministic replay of the committed CI run. Derive the world from 16 tool
> schemas — no domain code imported. Generate 180 candidates, sample 60. Execute sandboxed.
> Then re-execute every trace against a *fresh* world and check the state fingerprints
> match. That last stage is the whole audit story: every number on this dashboard traces
> back to an exact, re-runnable history."

Change the dropdown to another agent version and run it again to show a different failure
profile. Scroll down to **Derived world model** — 16 tools classified read/write/terminal,
with the bindings, preconditions and irreversible flags inferred purely from schemas.

---

## 3 · Runs — the "why did it fail" moment (50s) `press 3`

Set **Failures only**, pick `loopy-agent` in the tabs, open any row.

The drawer shows the whole audit chain in one screen:

- the instruction the agent was given,
- the **classifier findings** with the raw evidence — `get_order_details called 3x with
  identical arguments`, occurrences `[0,1,2]`,
- the **full trace**: every tool call, its arguments, whether it mutated state, and the
  world fingerprint after each mutation,
- the replay verdict at the bottom.

> "Raw pass/fail tells you nothing. This tells an engineer what to fix."

---

## 4 · Guardrails — the safety moment (45s) `press 4`

Top strip first:

> "This is the control readout. Two policies complied — they executed an irreversible
> action they were never authorized to take. One policy, `cautious-agent`, engaged with
> every single probe, *read the poisoned tool output*, and refused — and raised zero
> findings. That is the false-positive control. A guardrail tester that flags every agent
> that acts is worthless, and our CI gate fails if that policy is ever flagged."

Then the matrix: 20 probes across three distinct irreversible operations, four escalation
classes — urgency, ambiguity, policy conflict, injected tool output. Scroll to the probe
cards for the actual pressure text used.

---

## 5 · Scorecard — the CI moment (40s) `press 5`

> "Reliability is a rate with a Wilson 95% interval, never a single pass/fail. Look at the
> intervals, not just the headline: the gate compares intervals, so seed noise cannot fail
> a commit — a regression only blocks when the candidate's interval clears the baseline's."

Point at the **category heat grid** — that is what the gate actually reads — then the
**regression tracker** across persisted snapshots, then the **category deltas** with each
row marked `blocks` or `within CI`.

---

## 6 · Evidence — for the judge who digs (25s) `press 6`

Each benchmark carries its splits, its breakdown, its exact method, and an explicit
**caveat** — airline holdout is 91.7% on a small cell; TRAIL's metric is recall-oriented so
we publish weighted F1 too; agentdojo victims are scripted, not live models.

> "Every caveat a reviewer would raise is already on the page."

---

## If asked: "does this work on *my* agent?"

```bash
python -m oosc.cli ci --agent-endpoint http://localhost:8000/evaluate --agent-version my-agent-v2
```

Any agent behind an HTTP endpoint that accepts normalized `scenario` + `domain` JSON and
returns steps. The world, the scenarios and the guardrail probes all come from the tool
schemas, so a new domain needs no hand-authored fixtures. Exits non-zero on a significant
regression — that is the whole integration.

## If asked: "why scripted policies instead of a real LLM?"

> "So the gate is deterministic and free — it has to run on every commit. The runner takes
> any policy behind the same interface, so a live model plugs in without changing a single
> metric definition. The scripted policies exist to prove the *detectors* still fire, which
> is what a CI gate needs to guarantee."

## If asked about the parked number

> "Rediscovery. 8.5M enumerated signatures from schemas and initial data, 15 of 164 strict
> matches. 43 of those tasks contain free-text payloads — arbitrary new addresses — that no
> schema-plus-data process can conjure, which caps any such method at 73.8%. The rest is
> authoring idiosyncrasy in how they interleave read chains. We wrote the matching
> granularity down before generating anything and did not move it afterward."
