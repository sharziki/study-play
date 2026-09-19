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
