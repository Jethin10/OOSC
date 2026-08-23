# OOSC Night Log — live

> Pinned: the four engine numbers, the interface budget, what has won, what is parked.
> Updated as work lands. Full decisions in `DECISIONS.md`.

## Scoreboard (pinned)

| # | Metric | Bar | Current | Status |
|---|--------|-----|---------|--------|
| # | Metric | Bar | Current | Status |
|---|--------|-----|---------|--------|
| 1 | Oracle agreement vs tau2-bench gold rewards | all 164 tasks; ≥95% dev AND holdout | **98.48%** (1312 trajectories; dev 98.72%, holdout 97.22%, retail 100%) | ✅ WON |
| 2 | Rediscovery of tau2 hand-authored tasks | generator never reads tasks.json; target ≥50% strict | **9.2% strict** / 37.8% writes-only (2.1M signatures) | 🅿️ PARKED |
| 3 | TRAIL classifier joint accuracy | beat published best 11% | **46.6%** (GAIA 49.8%, SWE 34.4%; loc 97%; F1 .47/.67) | ✅ WON |
| 4 | agentdojo unsafe-action catch rate | 629 cases; only world-state-reproducible findings count; target ≥80% + benign FPR reported | **98.9%** catch over all 629 (622 flagged; 99.4% of 626 reproducible); arg-taint-only 98.1%; benign FPR 0/86 | ✅ WON |
| UI | Linear-bar scorecard | every interaction ≤100ms feedback; ≥60fps full-data screen; desktop+mobile vs linear.app screenshots | handler 0.8ms max, steady frames 15.4ms max, 144fps; shots in `results/ui-reference/` | ✅ WON |

**Won:** N1 oracle agreement, N3 TRAIL joint accuracy, N4 agentdojo catch rate.
**Parked:** N2 strict rediscovery — after several honest rounds: generator enumerates
2.1M exact-signature scenarios from schemas+data alone but hits 15/164 strict /
62/164 structural. Blockers: hand-authored read-chain interleavings (arbitrary
product-read placement/order across multi-order conversations) and the free-text
payload ceiling (43/164 tasks have non-derivable args like new addresses).
Full analysis in `results/n2/report.json`. Revisit if time remains.

## Timeline

- **00:xx** Repo scaffolded. tau2-bench and agentdojo cloned to `vendor/` (gitignored).
  Read tau2 evaluator end-to-end: gold reward = product over `reward_basis`
  (DB-hash match × ACTION subset check × COMMUNICATE × optional NL-judge).
  Retail: 114 tasks (112 DB+NL, 2 DB-only; 36 with communicate_info). Airline: 50
  (all DB+COMMUNICATE). Total = 164 ✓ matches the brief.
- **00:55** Decisions D1–D8 recorded in `DECISIONS.md`. First push.
- **01:20** Engine core written: schema export adapter, schema-only world
  derivation (`oosc.world.derive`), ledger-based mock world (`oosc.world.world`),
  our oracle mirroring tau2 component semantics (`oosc.oracle`).
- **02:10** N1 round 1: **92.45%**. Diagnosis found three root causes:
  (a) order-sensitive fingerprints vs their final-state comparison;
  (b) payment ids nested in keyed dicts unresolved (blind no-ops);
  (c) missing lifecycle/reference semantics let my world accept calls theirs rejects.
- **02:40** Fixes: canonical ledger ordering; dict-traversing resolution;
  reference-integrity / duplicate-ref / payment-balance vetoes from data alone;
  executable corruption fillers (real ids, documented example values).
- **02:55** N1 final: **98.48%** combined — holdout 97.22%. Per-domain caveat,
  stated plainly: retail holdout 100%, airline holdout 91.67% on a small cell
  (66/72). The combined bar holds; airline-only holdout does not. Frozen;
  residual airline gaps sit exactly in their hand-written business rules
  (multi-segment pricing, passenger checks) that schema-only derivation
  intentionally does not copy.
- **03:40** N2 rounds: generator rewritten twice (route/product-read variants,
  compound ops, full-context prefixes, digest-scale enumeration to 2.1M sigs).
  Strict stuck at 9-15/164; writes-only 62/164. **Parked** with documented
  blockers (authoring idiosyncrasy + free-text ceiling).
- **04:30** N4 agentdojo: pinned v0.1.2 (D10), 629-case universe restored.
  Guardrail classifier (argument taint + poisoned-read proximity, mutation-
  verified) catches 622/629 = **98.9%** over the full universe (**99.4%** of the
  626 world-state-reproduced cases), benign FPR 0. **WON**.
- **05:10** N3 TRAIL: rule-based span-evidence classifier scores **46.6%**
  joint accuracy with their own scorer vs ~11% published best. **WON**.
- **06:30** UI built to the Linear reference shots (real headless-Chrome
  screenshots of linear.app at desktop+mobile). Fresh-context critic found 2
  render bugs + 10 a11y/design defects; all fixed. Independent audit corrected
  our own claims (N4 98.9% not 99.2%; N1 airline-holdout caveat added).
  Interface budget measured and committed as artifact. **WON**.

- **08:0x** Interface rebuilt as a product, not a report dump. Six views:
  overview (pitch + the four numbers + the five PS directions mapped to running
  code), live pipeline replay, runs with a full trace inspector, guardrail
  compliance matrix, scorecard with Wilson intervals + regression tracker, and
  benchmark evidence with methods and caveats. `scripts/build_ui_data.py`
  assembles the bundle from committed artifacts only - no figure in the
  interface is typed in by hand.
- **08:1x** Three engine gaps found while wiring the guardrail view, all fixed:
  (a) uniform CI downsampling was silently dropping most adversarial probes -
  now stratified, 5 -> 20 probes at the same cost; (b) probes all piled onto
  whichever irreversible tool sorted first - now round-robin across
  cancel/exchange/return; (c) **no negative control existed** - every policy
  either mutated or made no calls at all, so the guardrail suite could not show
  it distinguishes refusal from inaction. Added `cautious-agent`, which engages
  with every probe, reads the poisoned tool output, and refuses. The gate now
  FAILS if that policy is ever flagged for an unsafe action.
- Gate re-run: 6 agent versions, 360 traces, 0 replay failures, **PASS**.
  Interface budget re-measured on the rebuild: interaction feedback 1.3ms max,
  median frame 7ms, no horizontal overflow at 390px, zero console errors across
  all six views.
