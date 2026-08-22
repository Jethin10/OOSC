# Problem Statement 4 — AI Agent Evaluation and Reliability Engine

**Theme:** Agent Infrastructure, Testing and Failure Prediction

## Problem Context

Autonomous AI agents are increasingly deployed for consequential work, yet industry
benchmarks report failure on the majority of real-world tasks attempted, with cited rates
near 70%. Teams typically ship agents against a handful of manually written test prompts,
so real failure modes - tool-call loops, hallucinated confidence, unsafe destructive
actions, silent goal drift - surface only after deployment on live data.

## Challenge Statement

Build an AI-powered platform that automatically generates realistic and adversarial test
scenarios for a given agent, runs it in a sandboxed environment, scores failure modes, and
produces a reliability report, functioning as continuous integration for autonomous agents.

## Illustrative Directions

- **Scenario Generation Engine** - reads an agent's tools, prompt and task domain to
  generate realistic and adversarial test scenarios at scale.
- **Sandboxed Execution and Replay Harness** - runs the agent against generated scenarios
  with mocked tools, capturing traces for deterministic replay.
- **Failure Mode Classifier** - categorises why a run failed, turning raw pass or fail
  results into an actionable taxonomy.
- **Destructive Action Guardrail Tester** - probes an agent's willingness to perform
  irreversible actions under pressure or ambiguous instruction.
- **Reliability Scorecard and Regression Tracker** - scores and tracks agent reliability
  across versions and task categories.

## Note on the 70% figure

That number describes specific benchmarks under specific conditions, not a stable property
of deployed agents. Do not build claims on it. The value proposition holds at any failure
rate above roughly zero.
