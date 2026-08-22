# OOSC Night Log — live

> Pinned: the four engine numbers, the interface budget, what has won, what is parked.
> Updated as work lands. Full decisions in `DECISIONS.md`.

## Scoreboard (pinned)

| # | Metric | Bar | Current | Status |
|---|--------|-----|---------|--------|
| 1 | Oracle agreement vs tau2-bench gold rewards | 164/164 tasks in scope; target ≥95% | — not yet measured | 🔨 building |
| 2 | Rediscovery of tau2 hand-authored tasks | generator never reads tasks.json; target ≥50% of 164 | — not yet measured | 🔨 building |
| 3 | TRAIL classifier joint accuracy | beat published best 11% | — not yet measured | 🔨 building |
| 4 | agentdojo unsafe-action catch rate | 629 cases; only world-state-reproducible findings count; target ≥80% + benign FPR reported | — not yet measured | 🔨 building |
| UI | Linear-bar scorecard | every interaction ≤100ms feedback; ≥60fps full-data screen; desktop+mobile vs linear.app screenshots | — | ⏳ queued |

**Won:** nothing yet. **Parked:** nothing yet.

## Timeline

- **00:xx** Repo scaffolded. tau2-bench and agentdojo cloned to `vendor/` (gitignored).
  Read tau2 evaluator end-to-end: gold reward = product over `reward_basis`
  (DB-hash match × ACTION subset check × COMMUNICATE × optional NL-judge).
  Retail: 114 tasks (112 DB+NL, 2 DB-only; 36 with communicate_info). Airline: 50
  (all DB+COMMUNICATE). Total = 164 ✓ matches the brief.
- **00:xx** Decision D1–D8 recorded in `DECISIONS.md`.
