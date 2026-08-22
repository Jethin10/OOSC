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

## Status

Work in progress — see `PROGRESS.md` for the live scoreboard.
