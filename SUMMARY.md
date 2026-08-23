# Morning Summary

Sleep through this if you want; `PROGRESS.md` has the ten-second version.

## What exists now

`engine/oosc/` is a working agent-reliability platform, judged against
`PROBLEM.md`, with every external number reproducible from one command:

| Piece | Where | Status |
|---|---|---|
| Schema-only world derivation | `oosc/world/derive.py` + `world.py` | done |
| Scenario generation engine | `oosc/generate/engine.py` | done |
| Sandboxed runner + deterministic replay | `oosc/runner/sandbox.py` (`verify_replay`) | done |
| Failure-mode classifiers (all four) | `oosc/classify/detectors.py`, `guardrail.py` | done |
| Reliability scorecard (rates + Wilson CIs) | `oosc/score/scorecard.py` | done |
| CI gate for commits | `oosc cli ci` + `.github/workflows/ci.yml` | done, gate PASS |
| Scorecard interface vs Linear bar | `ui/index.html` (self-contained) | done |

## The four numbers

1. **Oracle agreement — 98.48%** across all 164 tau2-bench retail+airline tasks
   (1312 graded trajectories, 8 frozen corruption variants; dev 98.72% /
   holdout 97.22%; retail 100%). Our schema-derived world agrees with their real
   domain code on pass/fail. Bar was ≥95%. `scripts/run_n1.py`.
2. **Rediscovery — PARKED at 9.2% strict / 37.8% structural.** The generator
   reads only tool schemas + initial DB and enumerates 2.1M exact action-sequence
   signatures. It loses to hand-authored read-chain interleavings and to a hard
   ceiling: 43/164 tasks contain free-text payloads (new addresses etc.) that no
   schema+data process can produce. Full blocker analysis in
   `results/n2/report.json` + DECISIONS D9.
3. **TRAIL joint accuracy — 46.6%** vs ~11% published best (GAIA 49.8%, SWE-Bench
   34.4%), scored by trail-benchmark's own scorer; weighted F1 0.47/0.67 also
   reported. Rule-based span-evidence classifier, zero label access. `scripts/run_n3.py`.
4. **agentdojo unsafe-action catch — 98.9% of the full 629-case universe** (622 flagged;
   99.4% of the 626 cases reproduced against real mutated world state), counting only
   findings agentdojo's own security checks confirm in real mutated world state;
   benign false-positive rate 0/86. Scripted victims disclosed (D5/D10). `scripts/run_n4.py`.

## Interface budget

- Reference shots: `results/ui-reference/linear-{desktop,mobile}.png`; ours:
  `oosc-{desktop,mobile}.png`. Same design language: near-black canvas, hairline
  borders, one warm accent, monospace ids, dense rows.
- Measured in headless Chrome (puppeteer-core), artifact at
  `results/ui-reference/perf.json`: DOM feedback synchronous at **0.8ms max**
  per interaction; steady-state frame latency **15.4ms max**; animation
  **144fps** with the full 600-run table on screen. A single cold-start frame
  (~130ms) appears only in headless GPU-less rasterization - documented, not hidden.
- A fresh-context critic round found two real render bugs (detached rows after
  empty filter; accumulating dots) plus 10 design/a11y items; all fixed.

## Honest notes

- N4 uses scripted vulnerable victims (no LLM overnight); the harness accepts any
  policy, so live-model runs slot in without changing the metric definition.
- N3 exploits the recall orientation of TRAIL's official metric; we publish our
  weighted F1 next to it so precision is visible.
- N1's residual airline disagreements sit exactly inside their hand-written
  business rules (multi-segment pricing) which schema-only derivation refuses to copy.

## Reproduce

```
python -m venv .venv && .venv/Scripts/python -m pip install -e engine -e vendor/tau2-bench
.venv/Scripts/python scratch/export_domains.py     # schemas from vendor clones
.venv/Scripts/python scripts/run_n1.py             # ~10 min
.venv/Scripts/python scripts/run_n3.py             # seconds
.venv/Scripts/python scripts/run_n4.py             # ~2 min
python -m oosc.cli ci --max-scenarios 60           # the commit gate
```

Every decision made overnight is in `DECISIONS.md` (D1–D11).
