# Adding content

The app is finished in the sense that matters: **you never have to touch code
to add a class.** Import material, and the class, its path, its units, and its
nodes appear on their own. This file is the contract that makes that true.

## The one thing the app needs

A **material**: a title, a class name, and some text. Everything downstream is
derived.

```
material  ──>  questions (topic, prompt, answer, explanation, source_quote)
                 └─> progress (mastery, due_at)  ──> path nodes
                 └─> lessons (optional)          ──> the teach step
```

- A **class** is `materials.campaign`. A new value = a new class in the
  switcher. No config, no enum, no deploy.
- A **unit** is one material. It is the row of nodes under a heading.
- A **node** is one `questions.topic` inside that material.
- A node **completes** when its average mastery clears the recall threshold
  (`STUDY_RECALL_THRESHOLD`, default 0.65). That is the only thing that
  advances the path, so mastery is the single source of progression.
- **Ordering is automatic.** Classes and units sort by exam pressure, so the
  nearest exam floats to the top. Link a material to a course with an exam and
  it reorders itself.

## Three ways to add material

1. **In the app.** Add material, paste or pick a file, done. Works on the phone.
2. **HTTP**, which is what any importer should use:

   ```bash
   curl -X POST localhost:4173/api/materials -H 'Content-Type: application/json' \
     -d '{"title":"PHYS 172 — Ch 3","campaign":"PHYS 172","content":"...","generate":true}'
   ```

3. **CLI**: `./study import notes.md`

`generate: true` runs question generation in the background. Without a working
Claude CLI login, import still succeeds and the questions can be generated
later; nothing is lost.

## Writing questions by hand

Only five fields matter, and one of them is non-negotiable:

| Field | Rule |
|---|---|
| `topic` | Becomes the node label. Keep it short and conceptual. |
| `prompt` | Self-contained. "In 15.2.29" is not a question. |
| `answer` | What a correct recall looks like. |
| `explanation` | Why it is true, not that it is true. |
| `source_quote` | **Required.** An exact quote from the material. |

The source quote is what keeps the app honest: every answer can be traced back
to something the learner actually imported, so a hallucinated question is
visibly unsupported rather than quietly wrong.

## Filling a class out

Importing gives a class one pass of questions. Two gaps are left, and both make
the path worse in ways that are hard to see from inside it.

**A node with one question completes on one lucky answer.** The path advances on
average mastery per topic, so a node holding a single question is finished the
first time it is recalled. Running `study generate` again does not fix this: its
coverage rule pushes the model toward an unexamined section, so a second pass
mostly adds more one-question nodes.

```bash
python3 tools/deepen_bank.py "STAT 350" --dry-run   # how short is it
python3 tools/deepen_bank.py "STAT 350" --target 4
```

**A node with no lesson skips the teach step** and goes straight to being
quizzed, which turns a tutor into a test.

```bash
python3 tools/teach_nodes.py "STAT 350" --dry-run
python3 tools/teach_nodes.py "STAT 350" --per-material 2
```

Both are resumable: they recompute what is missing from the database on every
run, so stopping one loses only the batch in flight. Both take `--shard`/
`--shards` to run several workers at once, split by material so two workers can
never touch the same node. A whole class is hours of model calls.

After a large generation run, typeset anything the model wrote in Unicode:

```bash
python3 tools/latexify_bank.py
```

`tests/test_bank_renders.py` runs against the live database and fails when a
question would show raw notation to the learner, so it is the check that this
worked.

## Exam dates

Ordering is by exam pressure, so a class with no upcoming exam sinks. Sync real
dates rather than typing them:

```bash
python3 study.py exams            # all registered courses
```

Purdue writes a course two ways and the Registrar only answers to the long one:
a learner registers `STAT 350`, the schedule publishes `STAT 35000`.
`study.registrar_code` maps between them, so either spelling works.

## Math

Write inline math as `\( ... \)` and display math as `$$ ... $$` or `\[ ... \]`.

**Do not use single `$` for math.** It is currency. The statistics bank is full
of items like "wins $0 with probability 0.5, $10 with probability 0.3", and
treating `$` as a delimiter turns the text between two prices into silent
garbled math. `web_static/math.js` is the only place this is decided, and it is
covered by tests.

## Where the code is

| Concern | File |
|---|---|
| Scheduling, mastery, generation | `study.py` |
| Unit headings | `titles.py` |
| More questions per node | `deepen.py` |
| The teach step | `lessons.py` |
| HTTP API | `web.py` |
| Transport | `web_static/api.js` |
| Session loop (no DOM, portable) | `web_static/session.js` |
| Device-local state (goal, hearts) | `web_static/player.js` |
| Math rendering | `web_static/math.js` |
| Rendering and input | `web_static/app.js` |

The session loop holds no DOM on purpose: the phone and the laptop render
differently but run the exact same loop, which is why a fix to one is a fix to
both. Tests enforce this boundary.

## Checks

```bash
python3 -m pytest tests -q
```
