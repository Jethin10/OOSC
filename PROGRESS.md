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
| 4 | agentdojo unsafe-action catch rate | 629 cases; only world-state-reproducible findings count; target ≥80% + benign FPR reported | **99.2%** catch (622/629), reproducible 626, benign FPR 0/86 | ✅ WON |
| UI | Linear-bar scorecard | every interaction ≤100ms feedback; ≥60fps full-data screen; desktop+mobile vs linear.app screenshots | — | ⏳ queued |

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
- **02:55** N1 final: **98.48%** — cleared on dev AND holdout. Frozen honestly;
  residual airline gaps sit exactly in their hand-written business rules
  (multi-segment pricing, passenger checks) that schema-only derivation
  intentionally does not copy.
- **03:40** N2 rounds: generator rewritten twice (route/product-read variants,
  compound ops, full-context prefixes, digest-scale enumeration to 2.1M sigs).
  Strict stuck at 9-15/164; writes-only 62/164. **Parked** with documented
  blockers (authoring idiosyncrasy + free-text ceiling).
- **04:30** N4 agentdojo: pinned v0.1.2 (D10), 629-case universe restored.
  Guardrail classifier (argument taint + poisoned-read proximity, mutation-
  verified) catches 622/629 = **99.2%**, benign FPR 0. **WON**.
- **05:10** N3 TRAIL: rule-based span-evidence classifier scores **46.6%**
  joint accuracy with their own scorer vs ~11% published best. **WON**.
