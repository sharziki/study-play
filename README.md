<div align="center">

# study play

**Turn any notes into a local, adaptive recall game.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-36d7e7?style=flat-square)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/license-MIT-a3e635?style=flat-square)](LICENSE)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-9b72cf?style=flat-square)](#requirements)

Grounded questions · adaptive mastery · evolving companion · terminal native

</div>

```text
 STUDY   2/5   FREE RUN                 Ctrl+E exit
 ────────────────────────────────────────────────────────────────
 RANK E  LV 2  =======········· 47/100   HEAT 6   STREAK 1d
 NYX (◉ ◉)  Wisp  ==········             153 XP

  RECOGNITION   HARD 4/5   mastery 24%

  A  Momentum changes because velocity is a vector.

  B  70 J: net work equals the change in kinetic energy.

  C  The acceleration points with the net force.

  D  Zero work because cos(90°) = 0.

     ↑↓ move   A–D choose   Enter select   Ctrl+E exit
```

## Why

Flashcards often stop at recognition. `study play` begins with multiple choice, tracks mastery by concept, then removes the choices and demands typed recall. Claude Code generates new questions from your material in the background; SQLite—not the model—owns progress and scheduling.

```text
notes → grounded questions → recognition → typed recall → spaced review
                                │                    │
                                └── XP · Nyx · rank · mastery ──┘
```

## Quick start

```bash
git clone https://github.com/sharziki/study-play.git
cd study-play
mkdir -p ~/.local/bin
ln -s "$PWD/study" ~/.local/bin/study

study import path/to/notes.md
study play
```

No notes ready? Start with a bundled deck:

```bash
study import examples/newton.md
study play
```

Also included: `examples/discrete-math.md` and `examples/spanish-basics.md`.

Import starts question generation in the background. Check it with:

```bash
study status
```

## The loop

| Stage | What happens |
|---|---|
| **Recognition** | New concepts use navigable A–D choices. |
| **Calibration** | Stake confidence: Safe, Bold, or Locked. |
| **True Recall** | At 65% concept mastery, choices disappear and you type. |
| **Feedback** | See correction, XP, mastery movement, Heat, and quest progress. |
| **Spacing** | Weak spots return soon; mastered questions fade out. |

Every fifth question is a boss round. Strong retrieval can drop shards. XP evolves Nyx and advances your E→S rank. Misses never remove progress: they reveal the correction, earn honest-effort XP, and schedule another attempt.

## Controls

| Key | Action |
|---|---|
| `↑` / `↓` | Move selection |
| `Enter` | Confirm |
| `A`–`D` or `1`–`4` | Choose directly |
| `B` at the stake screen | Bury a bad question |
| `E` at the stake screen | Quick-edit question, answer, and explanation |
| `Ctrl+E` | Exit anywhere |

## Commands

```bash
study import notes.md     # import material + generate in background
study play                # due reviews, or a free run when nothing is due
study generate            # generate questions in foreground
study pet                 # Nyx, shards, streak, milestones
study stats               # local learning stats
study status              # stats + Claude worker log
study doctor              # Claude auth, DB, and content health
```

Set when concepts switch from choices to typed recall:

```bash
STUDY_RECALL_THRESHOLD=0.55 study play   # default: 0.65
```

## Requirements

- Python 3.11+
- An authenticated [`claude`](https://docs.anthropic.com/en/docs/claude-code) CLI for question generation
- A terminal with ANSI color support

No Python packages. No hosted database. Study history stays in `.study/study.db`, which Git ignores.

Typed recall uses conservative local scoring. Clear high-confidence matches and clear low-confidence misses are graded automatically; ambiguous answers still ask you. Recall quality remains the main mastery signal, with small adjustments for pre-reveal confidence calibration and response pace. Perfect high-confidence retrieval also gets a small shard-drop boost. Session exit stays under five lines: mastery growth, regressions, Nyx progress, and next due concept.

## Grounding and safety

Imported notes are untrusted data, never instructions. Generated questions must include a verbatim source quote; unsupported questions are rejected before storage. Claude receives weak-topic and review context, but cannot own or mutate scheduling state.

Read [CLAUDE.md](CLAUDE.md) for generator rules and [RESEARCH.md](RESEARCH.md) for the learning and gamification evidence behind the product decisions.

## Architecture

```text
study (shell entrypoint)
└── study.py
    ├── Claude Code worker → structured grounded questions
    ├── SQLite            → material, mastery, reviews, profile
    ├── scheduler         → due, weak, and interleaved concepts
    └── terminal UI       → recall wizard + reward loop
```

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile study.py
```

## License

[MIT](LICENSE) © 2026 sharziki
