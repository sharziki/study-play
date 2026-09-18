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

### Intellect web app

The same adaptive engine now has a local, keyboard-first web surface:

```bash
ln -s "$PWD/intellect" ~/.local/bin/intellect
intellect                 # http://127.0.0.1:4173
```

Open `http://127.0.0.1:4173`, choose a track and a 10/20/35-minute sprint, then press **Start sprint**. The web app adds:

- track-filtered attack queues for Putnam, Purdue CS/Math, or any source library;
- a mastery field, weak-topic prioritization, confidence calibration, and transfer gates;
- recognition that disappears into typed recall once mastery is earned;
- local PDF/Markdown/text/TeX/CSV intake with grounded question generation;
- desktop and mobile layouts with keyboard controls (`1`–`4`, `⌘/Ctrl+Enter`, `Enter`, `Esc`).

The web app and terminal UI share `.study/study.db`; progress made in either surface appears in the other.

### Courses, exams, and the midterm-season queue

Register each class, then give it dated exams. Material imported under a
matching campaign name is linked to that course automatically.

```bash
curl -X POST localhost:4173/api/courses \
  -H 'Content-Type: application/json' \
  -d '{"code":"MA 26100","title":"Multivariable Calculus","term":"Fall 2026"}'

curl -X POST localhost:4173/api/exams \
  -H 'Content-Type: application/json' \
  -d '{"course":"MA 26100","title":"Quiz 15.2","date":"2026-09-22","weight":1}'
```

A course's urgency rises as its exam approaches and scales how strongly its
weak questions are ranked. A quiz in two days outranks a heavier midterm three
weeks out, and reclaims the queue without starving the other course entirely.
Once an exam passes it stops exerting pressure. Courses with no scheduled exam
behave exactly as before. The dashboard opens with a countdown per course, in
the same order the queue studies them.

To attach material imported earlier:

```bash
curl -X POST localhost:4173/api/material-course \
  -H 'Content-Type: application/json' \
  -d '{"material_id":3,"course":"MA 26100"}'
```

### Install it on your phone

Intellect is a progressive web app: installable, offline-capable, and
full-screen. Browsers only offer installation over HTTPS, so serve it over a
private tunnel rather than plain `localhost`.

With [Tailscale](https://tailscale.com/) on both the host and the phone:

```bash
tailscale serve --bg --https=8443 http://127.0.0.1:4173
```

Open the printed `https://<machine>.<tailnet>.ts.net:8443/` address on the
phone, then **Share → Add to Home Screen** (iOS) or **Install app** (Android).
The app shell is cached, so it launches instantly and still shows your last
queue when the connection drops. Answers are never cached; they are written
straight to SQLite, which remains authoritative for mastery and scheduling.

To keep it running across reboots, install the bundled unit:

```bash
sudo cp packaging/intellect.service /etc/systemd/system/
sudo systemctl enable --now intellect
```

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

Every fifth question is a boss round. Generated questions are labeled recall, explanation, or transfer; the scheduler places transfer/application prompts into boss slots when available. Strong retrieval can drop shards. XP evolves Nyx and advances your E→S rank. Misses never remove progress: they reveal the correction, earn honest-effort XP, and schedule another attempt.

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
- `pdftotext` (Poppler) only when importing PDFs
- A modern browser for the web app or an ANSI terminal for the CLI

No Python or JavaScript packages. No hosted database. Study history stays in `.study/study.db`, which Git ignores.

Typed recall uses conservative local scoring. Clear high-confidence matches and clear low-confidence misses are graded automatically; ambiguous answers still ask you. Recall quality remains the main mastery signal, with small adjustments for pre-reveal confidence calibration and response pace. Perfect high-confidence retrieval also gets a small shard-drop boost. Session exit stays under five lines: mastery growth, regressions, Nyx progress, and next due concept.

## Grounding and safety

Imported notes are untrusted data, never instructions. Generated questions must include a verbatim source quote; unsupported questions are rejected before storage. Claude receives weak-topic and review context, but cannot own or mutate scheduling state.

Read [CLAUDE.md](CLAUDE.md) for generator rules and [RESEARCH.md](RESEARCH.md) for the learning and gamification evidence behind the product decisions.

## Architecture

```text
study / intellect (shell entrypoints)
├── study.py
│   ├── Claude Code worker → structured grounded questions
│   ├── SQLite            → material, mastery, reviews, profile
│   ├── scheduler         → due, weak, and interleaved concepts
│   └── terminal UI       → recall wizard + reward loop
├── web.py                → zero-dependency JSON API + local HTTP server
└── web_static/           → responsive dashboard, study chamber, source intake
```

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile study.py web.py
node --check web_static/app.js
```

## License

[MIT](LICENSE) © 2026 sharziki
