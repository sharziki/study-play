# Intellect — Product Thesis

## Mission
Compress the loop between **not knowing** and **durable mastery** for one ambitious, fast first-principles learner. Intellect is not a course catalog or flashcard manager. It is a local learning control plane that chooses the next highest-value challenge, gets out of the way while Sharvil solves it, diagnoses the miss, and immediately updates the next move.

## Product thesis
The fastest path across Putnam, Purdue CS, and arbitrary new material is one keyboard-first daily sprint that unifies grounded question generation, hard transfer practice, confidence calibration, and adaptive scheduling. The central artifact is the **attack queue**: a short, interleaved sequence of weak, due, new, and keep-alive problems.

## Core loop
1. Drop in notes, a syllabus, a chapter, or a problem set and assign it to a track.
2. Intellect generates source-grounded recall, explanation, and transfer questions in the background.
3. Start a 10-, 20-, or 35-minute sprint in one click.
4. Answer one challenge at a time. New concepts may use recognition; mastered concepts require typed recall.
5. Lock confidence before reveal. Ambiguous typed answers remain learner-graded.
6. See the exact correction, why, source evidence, mastery movement, and next due state.
7. The queue adapts: weak concepts return, proven concepts retire, every fifth prompt favors transfer.

## Initial tracks
- **Putnam** — proof strategy, method selection, reusable patterns, postmortems, and hard transfer.
- **Purdue CS** — proficiency/exam preparation, implementation reasoning, syntax facts only when irreducible.
- **General** — any uploaded material.

## Decisions
- Local-first: SQLite owns history and scheduling.
- Source-grounded: generated answers require an exact supporting quote.
- One active task: no feed, social layer, or decorative dashboard maze.
- Advanced-learner tuned: derivable ideas get a concise why-pass, then hard problems; rote gets minimal repetition.
- Keep the existing trusted Study TUI engine and data; add a zero-dependency local web surface.
- Retain Nyx/XP as quiet competence feedback, never as a hostage mechanic.

## Non-goals
- Replacing authoritative textbooks, instructors, or official problem archives.
- Inventing unsupported Putnam solutions.
- Global leaderboards, social feeds, streak punishment, or an elaborate virtual economy.
- Accounts, cloud sync, billing, or multi-user permissions in the first local release.
- Letting an LLM own scheduling or silently grade ambiguous proofs.

## Acceptance gates
- Existing SQLite data opens without migration loss.
- Dashboard shows due work, mastery by topic, materials, and profile state.
- A sprint begins in one click and reaches a question in under 10 seconds.
- Answers are never exposed by the question endpoint.
- Recognition is graded deterministically; typed recall is auto-graded only for clear cases.
- Every committed review updates mastery, scheduling, XP, and review history.
- Material can be pasted or uploaded and assigned to a track.
- Question generation can be started from the web UI and remains grounded by the existing quality gate.
- Complete loop works with keyboard and on desktop/mobile.
- Unit tests, Python compile, real server startup, and browser journey all pass.
