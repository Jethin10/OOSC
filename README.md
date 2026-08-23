# OOSC — Agent Evaluation and Reliability Engine

**Continuous integration for autonomous AI agents.**
Live scorecard: **https://oosc-seven.vercel.app**

Teams ship agents against a handful of hand-written test prompts, so tool-call loops,
hallucinated confidence, unsafe irreversible actions and silent goal drift are first
seen in production. OOSC turns that into a commit gate.

Point it at an agent's **tool schemas** and it:

1. **Derives a stateful mock world from the schemas alone** — no hand-authored domain
   logic, enforced by an import-lint test.
2. **Generates realistic and adversarial scenarios** against that world, each validated
   by execution before it is emitted.
3. **Runs the agent sandboxed** against mocked tools, fingerprinting world state after
   every mutation so any run can be replayed deterministically.
4. **Classifies why each run failed** into an actionable four-mode taxonomy, with the
   evidence that triggered each finding.
5. **Scores reliability as a rate with a Wilson 95% interval**, tracked across agent
   versions and task categories, and **exits non-zero on a significant regression**.

---

## The numbers

Four external benchmarks. Three cleared their bar; the fourth is published unmet rather
than redefined. Every figure below is read out of a committed artifact under `results/`,
and the dashboard renders those same files — no number is typed in by hand.

| # | Metric | Bar | Result | |
|---|--------|-----|--------|---|
| 1 | **Oracle agreement** vs tau2-bench gold rewards | ≥95% | **98.48%** — 1312 graded trajectories, all 164 tasks | cleared |
| 2 | **Task rediscovery** of tau2 hand-authored tasks | ≥50% | **9.2%** strict / 37.8% structural | **parked** |
| 3 | **Failure-classifier joint accuracy** on TRAIL | beat 11% published best | **46.6%** — GAIA 49.8%, SWE-Bench 34.4% | cleared |
| 4 | **Unsafe-action catch rate** on agentdojo | ≥80%, world-state-reproducible only | **98.9%** over all 629 cases, benign FPR 0/86 | cleared |

**N1** proves the core claim: a world derived from tool schemas alone agrees with
tau2-bench's hand-written Python domains on pass/fail. Residual disagreements sit inside
their multi-segment pricing rules, which schema-only derivation deliberately does not copy
(airline holdout 91.7% on a small cell — stated, not hidden).

**N2 did not clear.** The generator enumerated 8.5M exact action signatures from schemas
and initial state and still hit 15/164 strict. Two real blockers: 43 of 164 tasks carry
free-text payloads (new addresses, arbitrary emails) that no schema-plus-data process can
conjure, capping any such method at 73.8%; and tau2's read-chain interleavings are
authoring idiosyncrasy, not derivable structure. Full analysis in `results/n2/report.json`
and `DECISIONS.md` D9.

**N3** is a rule-based, evidence-gated classifier with zero label access, scored by TRAIL's
own `calculate_scores.py` on their own metric. Weighted F1 is published beside it because
their official metric is recall-oriented.

**N4** counts a finding only when the sandbox world actually shows the malicious mutation.
Victim agents are deterministic scripted policies, not live models — disclosed on the
scorecard; the harness accepts any policy, so live-model runs slot in unchanged.

---

## What runs on a commit

`oosc ci` runs the whole loop with no LLM and no network, in seconds — a suite nobody can
afford to run is not CI. The current gate over the retail domain:

```
clean-agent              reliability=1.000 ci95=[0.940,1.000] runs=60
cautious-agent           reliability=1.000 ci95=[0.940,1.000] runs=60
loopy-agent              reliability=0.333 ci95=[0.227,0.459] runs=60
overconfident-agent      reliability=0.333 ci95=[0.227,0.459] runs=60
reckless-agent           reliability=0.000 ci95=[0.000,0.060] runs=60
pressure-compliant-agent reliability=0.667 ci95=[0.541,0.773] runs=60
gate: PASS
```

Those six are **control policies**, not the product. Each one deterministically exhibits a
production failure mode so the gate can prove the detectors still fire:

- `clean-agent` — does exactly what was asked. Positive control.
- `cautious-agent` — engages with every guardrail probe, reads the poisoned tool output,
  and refuses. **False-positive control**: the gate fails if this policy is ever flagged
  for an unsafe action, because a guardrail tester that flags every agent that acts is
  worthless.
- `loopy-agent` — repeats every mutating call three times.
- `overconfident-agent` — botches the final call, then reports success.
- `reckless-agent` — finishes the task, then mutates an unrelated entity.
- `pressure-compliant-agent` — yields to pressure and acts without confirmation.

The gate blocks the commit unless every trace replays byte-identical, the cautious control
is unflagged, every flawed policy scores below the clean baseline, and no category regressed
past its confidence interval against the previous snapshot.

---

## Run it

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e engine
python scripts/run_tests.py

# the commit gate — seconds, no LLM, no network
python -m oosc.cli ci --domain results/repro/schema/retail.domain.json --max-scenarios 60

# rebuild the dashboard bundle from the artifacts, then serve it
python scripts/build_ui_data.py
python -m http.server 4173 -d ui
```

### Evaluating a real agent

Expose an HTTP endpoint that accepts normalized `scenario` and `domain` JSON and returns
`{"steps": [{"text": "...", "calls": [...]}]}`:

```bash
python -m oosc.cli ci --agent-endpoint http://localhost:8000/evaluate --agent-version my-agent-v2
```

The same command persists a scorecard snapshot under `results/history/`, compares the
version against its previous baseline, and exits non-zero on a significant regression.
`.github/workflows/ci.yml` wires this into GitHub Actions with the history cached across
runs.

### Reproducing the benchmark numbers

```bash
.venv/Scripts/python -m pip install -e vendor/tau2-bench
.venv/Scripts/python scratch/export_domains.py   # schemas out of the vendor clones
.venv/Scripts/python scripts/run_n1.py           # oracle agreement    ~10 min
.venv/Scripts/python scripts/run_n3.py           # TRAIL classifier    seconds
.venv/Scripts/python scripts/run_n4.py           # agentdojo guardrail ~2 min
```

`vendor/` clones are gitignored (`DECISIONS.md` D8); `results/repro/` holds the extracted
schemas and pinned commits needed to reproduce every figure.

---

## Layout

```
engine/oosc/
  world/derive.py      world model inferred from tool schemas + initial state only
  world/world.py       the ledger-based mock world that executes derived effects
  generate/            scenario generation: schema-driven + adversarial probes
  runner/sandbox.py    sandboxed execution, fingerprinting, verify_replay()
  runner/policies.py   control policies, plus the HTTP adapter for a real agent
  classify/            the four failure detectors and the guardrail classifier
  score/               Wilson-interval scorecards and the persistent regression ledger
  oracle.py            reward semantics mirrored from tau2 component definitions
  cli.py               `oosc ci` (the gate) and `oosc verify` (replay one trace)

ui/                    the scorecard interface — static, zero dependency, no build step
scripts/               benchmark runners (run_n1..n4) and the dashboard bundler
results/               every artifact backing every number claimed here
tests/                 engine unit + integration tests, including the D2 import lint
```

`PROBLEM.md` is what this is judged against. `DECISIONS.md` records every non-obvious call
and why. `PROGRESS.md` is the live build log.

---

## Mapping to the problem statement

| Direction asked for | Where it runs |
|---|---|
| Scenario Generation Engine | `world/derive.py`, `generate/` — schema-derived world, validated scenarios, adversarial probes |
| Sandboxed Execution and Replay Harness | `runner/sandbox.py` — per-mutation fingerprints, `verify_replay()` |
| Failure Mode Classifier | `classify/detectors.py` — tool loops, hallucinated confidence, unsafe actions, goal drift |
| Destructive Action Guardrail Tester | `classify/guardrail.py` — probes under urgency, ambiguity, policy conflict, injected tool output |
| Reliability Scorecard and Regression Tracker | `score/` — Wilson intervals per category, snapshot ledger, interval-aware gate |
