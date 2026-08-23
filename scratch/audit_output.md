1. **Coverage**
- Schema-only world derivation and stateful mock execution are real: `engine/oosc/world/derive.py`, `engine/oosc/world/world.py`.
- Scenario generation is real but narrow/data-grounded rather than broad adversarial generation: `engine/oosc/generate/engine.py`; N2 artifact reports only **15/164 strict** and **62/164 writes-only**: `results/n2/report.json`.
- Sandboxed traces and deterministic replay are implemented: `engine/oosc/runner/sandbox.py` (`Sandbox.run`, `verify_replay`).
- Failure taxonomy/classification exists: `engine/oosc/classify/detectors.py`; TRAIL-specific classification is separate: `scripts/run_n3.py`.
- Destructive-action testing exists with real mutation checks, but is largely scripted-victim/benchmark-specific: `engine/oosc/classify/guardrail.py`, `scripts/run_n4.py`; artifact: `results/n4/report.json`.
- Reliability scorecard and category comparison exist: `engine/oosc/score/scorecard.py`; UI assets exist at `ui/index.html`, `ui/app.js`, `ui/styles.css`, but the required Linear comparison/performance evidence is absent.
- External four-number bars are not all cleared: N2 is parked (`PROGRESS.md`, `results/n2/report.json`); N1’s holdout is **97.22% overall**, but airline report is **91.67%** (`results/n1/report.json`), below the stated ≥95% per-split claim.

2. **Four detectors**
- Tool-call loops: working `detect_tool_loop` in `engine/oosc/classify/detectors.py`.
- Hallucinated confidence: working but thin heuristic `detect_hallucinated_confidence` in `engine/oosc/classify/detectors.py`.
- Unsafe irreversible action: working mutation-gated `classify_unsafe` in `engine/oosc/classify/guardrail.py`; exercised by `scripts/run_n4.py`.
- Silent goal drift: intended-entity heuristic `detect_goal_drift` in `engine/oosc/classify/detectors.py`; coverage is weak because it requires caller-supplied `intended_entity_ids`.

3. **Reliability intervals**
- Wilson rate/interval implementation: `wilson_interval`, `CategoryRate.to_dict`, and `Scorecard.to_dict` in `engine/oosc/score/scorecard.py`.
- It is not demonstrably used in committed benchmark outputs: `results/n1/report.json`, `results/n2/report.json`, `results/n3/report.json`, and `results/n4/report.json` contain point metrics, not Wilson intervals. `scripts/run_n1.py`–`run_n4.py` do not invoke `Scorecard`.

4. **Unsupported README/PROGRESS claims**
- README’s “reliability … tracked across versions/categories” is not backed by a committed multi-version scorecard artifact; only the implementation exists (`README.md`, `engine/oosc/score/scorecard.py`).
- PROGRESS claims N1 **“cleared … dev AND holdout”**, contradicted by airline holdout **0.9167** in `results/n1/report.json`.
- PROGRESS claims N4 “99.2% catch” while the artifact reports **0.9936 reproducible** and **0.9889 over 629** (`PROGRESS.md`, `results/n4/report.json`).

5. **Top three gaps**
- Make N2 reach the required rediscovery bar or explicitly leave the platform incomplete (`results/n2/report.json`).
- Integrate repeated-run Wilson scorecards into every run script and committed report (`engine/oosc/score/scorecard.py`, `scripts/run_n1.py`).
- Produce honest UI evidence and performance tests against the Linear bar, plus fix contradictory N1/N4 progress claims (`GAUNTLET.md`, `ui/`, `PROGRESS.md`, `results/`).