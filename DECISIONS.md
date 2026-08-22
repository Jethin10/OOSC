# Decision Log

Every non-obvious decision made during this run, with the reason. Newest at the bottom.
Written so each call is defensible in the morning.

## D1 — Engine language: Python 3.12+

tau2-bench is Python (requires >=3.12,<3.14). The oracle-agreement number requires
importing their evaluator to produce gold rewards. TRAIL and agentdojo evaluation
ecosystems are also Python. One language for all four numbers; Node only for the UI.

## D2 — World derivation consumes schemas only, enforced architecturally

The derivation module (`engine/oosc/world/derive.py`) may consume only: tool names,
parameter JSON schemas, tool docstrings/descriptions, the domain policy text, and the
initial DB state JSON. It must not import or execute any benchmark's Python tool code.
Enforced by an import-lint test. Rationale: "derived from schemas alone" is the core
claim of PROBLEM.md/GAUNTLET.md; a derivation that peeked at domain code would be
contaminated and the claim false. Their code IS used to compute gold labels for the
agreement metric itself — that is the metric definition, not contamination.

## D3 — Oracle agreement scope: deterministic reward components, all 164 tasks

tau2's gold reward = product of components in each task's `reward_basis`
(DB / ACTION / COMMUNICATE / NL_ASSERTION). NL_ASSERTION is judged by an LLM
(offline-hostile, non-deterministic). We measure agreement over the deterministic
components (DB + ACTION + COMMUNICATE) for **all 164 tasks** — none are dropped —
and apply the same convention symmetrically to both oracles. NL-assertion behavior
is reported separately. This uses every task; nothing is narrowed.

## D4 — Corruption distribution frozen before measurement

To keep the agreement number honest, the trajectory-corruption taxonomy (drop-action,
wrong-argument-value, wrong-entity-id, extra-destructive-write, benign-extra-read,
repeat-write) and its sampling weights were written down BEFORE first measurement and
are not tuned afterward against results. Seeded RNG; every number reproducible from
a single command.

## D5 — Scripted victim policies for agentdojo reproduction

agentdojo attacks require an LLM victim agent. Overnight runs use deterministic
scripted victims with parameterized vulnerability profiles (complies-with-injected-
instruction on/off), plus pluggable live-model mode. Catch rates are reported per
victim profile; "reproducible against real mutated world state" means our sandbox's
world state actually shows the malicious mutation. Disclosed on the scorecard.

## D6 — Interface: zero-dependency static app

The scorecard UI is hand-written HTML/CSS/JS with no framework and no build step:
instant load, full control of paint cost (60fps budget), trivially servable from CI
artifacts. A framework buys nothing here and costs the perf budget.

## D7 — Reliability is a rate with a Wilson interval

Every reliability figure is `successes/trials` with a 95% Wilson score interval over
repeated seeded runs, never a single pass/fail. Categories tracked separately.

## D8 — vendor/ clones are gitignored

The two benchmark repos stay local-only (gitignored): committing forks' trees into
OOSC pollutes history and risks license confusion (they are MIT, but vendoring whole
repos is noise). Instead, `results/` commits the small extracted artifacts (schemas,
task counts, hashes) needed to reproduce every number, plus exact clone instructions
(commit SHA pinned) in `results/repro/`.

## D9 — Rediscovery definition and target (frozen before generation)

Data analysis first: 121/164 tau2 tasks have golden-action arguments fully
derivable from the initial DB alone (retail 73/114, airline 48/50); the rest
contain free-text payloads (arbitrary addresses/emails from persona
instructions) that no schema+data process can conjure. Primary metric: STRICT
exact-match rediscovery (action names + complete argument equality) over all
164 tasks, target >= 50%. Structural rediscovery (action names + entity-id
bindings, free-text ignored) reported alongside with the 73.8% derivability
ceiling stated. Matching granularity fixed before any generation ran.
Communicate-info criteria excluded from both sides symmetrically (text-phrasing,
not tool behavior).
