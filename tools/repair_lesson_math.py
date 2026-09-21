#!/usr/bin/env python3
"""Repair lessons whose maths delimiters were written doubled.

`\\\\(t\\\\)` is LaTeX's line break followed by a parenthesis, not inline maths, so
KaTeX ignores it and the learner reads the backslashes as literal characters.
The generator emits this despite the prompt telling it not to, and it reached
125 of 148 lessons before a screenshot of the teach step caught it.

`study.repair_math` now fixes this at save time, so this pass exists for the
lessons written before that. It rewrites only a complete `\\\\( ... \\\\)` pair,
because a doubled backslash on its own is a real row break inside an aligned
block and rewriting that would corrupt mathematics to fix a delimiter that was
never there.

    python3 tools/repair_lesson_math.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402

# Every learner-visible column, flat text and JSON alike.
FLAT = ("title", "objective", "motivation", "misconception", "source_quote")
NESTED = (
    "prerequisites_json",
    "primitives_json",
    "derivation_steps_json",
    "worked_example_json",
    "checks_json",
)


def repair_tree(value):
    """Apply the delimiter repair to every string inside a decoded JSON value."""
    if isinstance(value, str):
        return study.repair_math(value)
    if isinstance(value, list):
        return [repair_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_tree(item) for key, item in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed = 0
    with study.connect() as db:
        rows = list(db.execute(
            "SELECT id, " + ", ".join((*FLAT, *NESTED)) + " FROM lessons"
        ))
        for row in rows:
            updates: dict[str, str] = {}
            for column in FLAT:
                original = row[column] or ""
                fixed = study.repair_math(original)
                if fixed != original:
                    updates[column] = fixed
            for column in NESTED:
                original = row[column] or ""
                if not original:
                    continue
                try:
                    decoded = json.loads(original)
                except json.JSONDecodeError:
                    continue
                fixed = json.dumps(repair_tree(decoded))
                if fixed != original:
                    updates[column] = fixed
            if not updates:
                continue
            changed += 1
            if not args.dry_run:
                assignments = ", ".join(f"{column}=?" for column in updates)
                db.execute(
                    f"UPDATE lessons SET {assignments} WHERE id=?",
                    [*updates.values(), row["id"]],
                )
        if not args.dry_run:
            db.commit()

    verb = "would be repaired" if args.dry_run else "repaired"
    print(f"{changed} of {len(rows)} lesson(s) {verb}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
