# Search open source first — Intellect, resolved

Date: 2026-09-20
Status: decided and implemented (branch `fsrs-scheduling`)

## The correction that triggered this

> "see for like 'intellect' our project, we did we not jus like use:
> https://github.com/sanidhyy/duolingo-clone. always always search open source
> first buddyy."

The correction was right, and it was already half-applied: commit `7d647c1`
("Rebuild the study interface on the Lingo open-source baseline") replaced the
hand-written `web_static/` app with components derived from that repository,
with attribution in `NOTICE`. What had never been done was the same search for
the part of this project that matters more than the interface: the scheduler.

## What was evaluated

### sanidhyy/duolingo-clone ("Lingo")

- MIT, actively maintained (commits as recent as 2026-09-18), ~226 PRs.
- Stack: Next.js, Clerk, Stripe, Neon, Drizzle, react-admin, Zustand.
- **No test framework at all.** No vitest, jest, or playwright.
- It is a *UI and product shell*. Its learning model is a fixed course tree of
  static units. It has no spaced repetition, no memory model, no scheduling.

Verdict: **already harvested, correctly, and nothing further to take.** The
interface components were worth adopting and were adopted. Adopting it
wholesale would mean deleting 138 passing tests, the LaTeX/KaTeX pipeline, the
content importers, and the exam-pressure scheduler, in exchange for a Stripe
paywall and a database we do not want. That trade is obviously bad, and this
document exists partly so nobody re-proposes it.

### open-spaced-repetition/py-fsrs — the piece actually worth taking

This is where the real gap was. `next_interval()` was hand-rolled:

```python
again -> 10 minutes
hard  -> current * 1.3
good  -> current * 2.5
easy  -> current * 4
```

That is a rough SM-2 impression with invented constants. It models no memory:
no stability, no difficulty, no retrievability, no configurable target
retention, and no way to improve from the review history the app is already
recording in the `reviews` table.

FSRS is the algorithm Anki ships as its default scheduler. `py-fsrs` is the
official Python implementation: MIT, maintained (last commit 2026-08-09), 1,244
lines of its own tests, and — the decisive property — **the core is pure
standard library**. `torch` is only imported for the optional `Optimizer` under
`TYPE_CHECKING`. That means it vendors into a zero-dependency Python app
without changing its dependency story.

Also considered: `ts-fsrs` (same algorithm, wrong language for a Python engine),
and writing SM-2 by hand (strictly worse than FSRS and more code to own).

## Decision

**Keep the project. Harvest FSRS. Do not adopt the clone wholesale.**

The tradeoff stated plainly: vendoring FSRS means this repository now carries
~1,900 lines of third-party scheduling code it did not write, and the intervals
it produces are no longer hand-tunable by reading four constants. What it buys
is a memory model with published empirical backing, per-card stability and
difficulty, and a future path to optimizing parameters from the review log this
app already keeps. For an app whose entire purpose is deciding what to study
next, owning a worse scheduler was the single largest unforced weakness.

## What was integrated

- `vendor/fsrs/` — py-fsrs core at commit `9446cb0`, MIT license included.
  Core modules only; the `torch`-dependent optimizer was deliberately left out.
- `progress` gains `stability`, `difficulty`, `fsrs_state`, `fsrs_step`,
  `last_review`, via the existing forward-only migration pattern. The live
  database migrated cleanly with all 535 questions intact.
- `schedule_review()` advances real memory state. `next_interval()` survives
  with its old signature for callers that only know a previous interval.
- `record_review()` reads memory state from `progress` directly rather than
  from the caller's row, because the TUI and the web API join that table with
  different column lists and a missing column would have silently reset each
  card on every review.
- Fuzzing is disabled so scheduling stays deterministic, which the exam-pressure
  queue and the tests both rely on.

Exam pressure is untouched. FSRS decides *when* a card is due; `attempt_priority`
still decides what to serve now, and that ordering is this project's own idea.

### Two things the tests caught

1. Translating a legacy interval without a `last_review` made FSRS see zero
   elapsed time and inflate a 4-day card to a 155-day interval.
2. Two reviews in the same second correctly do not grow stability. The first
   version of the new test asserted growth over an unspaced pair and failed —
   the test was wrong, not the library.

Tests: 137 -> 138 passing. Health check 200, `/api/path` still serves.

## The standing rule

Before hand-writing any component that is a *known, named problem* —
scheduling, parsing, auth, diffing, text rendering — search for the maintained
open-source implementation first. Check license, activity, test coverage, and
dependency weight, then decide. "We already looked" is only true if there is a
written record of what was looked at, which is what this file is.

The counter-rule, which matters just as much: **searching OSS first does not
mean adopting OSS wholesale.** Working, tested code is an asset. The right move
is usually to harvest the specific piece that is genuinely better and leave the
rest alone.
