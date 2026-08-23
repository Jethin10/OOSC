# OOSC — Agent Evaluation & Reliability Engine

Continuous integration for autonomous AI agents. Given an agent's tool schemas,
system prompt, and task domain, the engine:

1. **Derives a stateful mock world from the tool schemas alone** — no hand-authored
   domain logic.
2. **Generates realistic and adversarial scenarios at scale** against that world.
3. **Runs the agent sandboxed** with mocked tools, capturing traces good enough for
   deterministic replay.
4. **Classifies why runs fail**: tool-call loops, hallucinated confidence, unsafe
   irreversible actions under pressure, silent goal drift.
5. **Scores reliability as a rate with confidence intervals**, tracked across agent
   versions and task categories.

Judged against `PROBLEM.md` under the gauntlet rules in `GAUNTLET.md`.

## Layout

```
engine/        Python package: world derivation, generation, sandbox, classifier, scoring
ui/            Scorecard interface (static, zero-dependency)
results/       Committed run artifacts backing every number we claim
vendor/        Benchmark clones used for external validation (gitignored; see DECISIONS.md)
tests/         Engine unit + integration tests
PROGRESS.md    Live night log — numbers, wins, parked items
DECISIONS.md   Every non-obvious decision and why
```

## Run locally

```bash
pip install -e engine
python scripts/run_tests.py
oosc ci --domain results/repro/schema/retail.domain.json --max-scenarios 60
python -m http.server 4173 -d ui
```

To evaluate a real agent, expose an HTTP endpoint that accepts normalized
`scenario` and `domain` JSON and returns `{"steps": [{"text": "...", "calls": []}]}`:

```bash
oosc ci --agent-endpoint http://localhost:8000/evaluate --agent-version my-agent-v2
```

The CI command persists scorecards under `results/history/`, compares the
current agent version with its previous baseline, and exits non-zero on a
significant reliability regression.

## Status

The platform now covers all five challenge directions. See `PROGRESS.md` for
the benchmark evidence and remaining research targets.
