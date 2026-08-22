# The Gauntlet Brief

## What to build

A platform that takes a given AI agent - its tools, its system prompt, its task domain -
and acts as continuous integration for it. It derives a stateful mock world from those tool
schemas with no human authoring, generates realistic and adversarial scenarios against it
at scale, runs the agent sandboxed against mocked tools while capturing traces good enough
for deterministic replay, classifies why each run failed into an actionable taxonomy, and
produces a reliability scorecard that tracks the agent across versions and task categories.

It has to catch the four failures that normally only surface in production:

1. Tool-call loops
2. Hallucinated confidence - the agent reports success it never achieved
3. Unsafe or irreversible actions taken under pressure or ambiguous instruction
4. Silent goal drift

Reliability is a rate with an interval across repeated runs, never a single pass or fail.
And it has to be cheap and fast enough to genuinely run on a commit - a suite nobody can
afford to run is not CI.

## The bar

Sierra's tau2-bench: https://github.com/sierra-research/tau2-bench (MIT).

Clone it and get it actually running before building anything. Work against the real thing,
not a description of it. Their domains are hand-written Python. Ours has to be auto-derived
from tool schemas alone.

## The four numbers

All four must clear. Do not call the run won on the easy ones.

1. **Oracle agreement** - agreement between our oracle and tau2-bench's gold rewards across
   their 164 annotated retail and airline tasks.
2. **Rediscovery rate** - how many of their hand-authored tasks our generator finds without
   ever reading `tasks.json`.
3. **Classifier joint accuracy** - on https://huggingface.co/datasets/PatronusAI/TRAIL,
   where the published best is 11 percent.
4. **Unsafe-action catch rate** - against the 629 security cases in
   https://github.com/ethz-spylab/agentdojo, counting only findings reproducible against
   real mutated world state.

## How the loop runs

Break this into the smallest pieces that can be improved and judged on their own. For each
piece, fan out a builder and a separate critic with fresh context. The critic runs the
actual code, then puts our artifact next to tau2-bench's blind with all provenance stripped
- two environments, two failure reports, two scorecards - says which one an engineer would
trust enough to gate a deploy on, and names the single biggest remaining gap. Then it goes
back to the builder.

The critic is a harsh critic. Praise is not useful. If ours does not win, it keeps going.

## Do not game the numbers

Do not weaken the bar, relax a metric definition, narrow the task set, stub a check, or
soften the critic to make a number clear. A number that moved because the test got easier
is a failed round, not a passed one. If a number will not clear honestly, park the piece
and say so.

## Running unattended

Never stop to ask a question. When a decision comes up, take the option defensible in the
morning and write down why.

If a piece has not won after several rounds, park it with a note on what is blocking it,
move to the next one, and come back later. Never let one stuck piece hold the whole run.

Commit and push as described below. Do not deploy, and do not write anywhere outside this
directory.

## The interface

The scorecard is the thing a human actually looks at, so it gets its own bar.

The bar for the interface is Linear, https://linear.app. Open it in a real browser and
screenshot it at desktop and mobile. Compare against those screenshots directly, not
against a description of them or a memory of what good design looks like. Density,
typography, spacing rhythm, keyboard behaviour, empty states, loading states, and the
restraint of its motion are all in scope.

The measurable half: no interaction takes longer than 100ms to give feedback, and no
animation drops below 60fps while a full scorecard of real run data is on screen. Pretty
and janky is a failed round.

No stock gradients, no glassmorphism, no emoji as iconography, no purple-to-blue hero, no
generic dashboard template. If it looks like it came out of a model, it is not done.

## Pushing

The remote is https://github.com/Jethin10/OOSC.git, already configured as origin with main
tracking. Auth is set up and verified.

Commit in small honest steps as work lands, and push to origin main every time a piece wins
its blind comparison, plus any time the progress page changes materially. Write real commit
messages saying what won and which number moved. The progress page lives in the repo so it
can be read from a phone. Never force push, never rewrite history, never touch any other
remote or repository.

## Progress reporting

Keep a live progress page updating as the work evolves. Pin the four numbers, what has won,
and what is parked at the top so the whole night reads in ten seconds.

`PROBLEM.md` in this directory is what this is judged against. Read it when writing the
morning summary and map what won onto it. Do not let it steer the rounds before that.

## Exit

Keep looping on each piece until the critic picks ours blind against that piece's own bar,
and all four engine numbers plus the interface budget clear honestly. Do not stop before
that.
