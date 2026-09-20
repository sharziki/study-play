#!/usr/bin/env python3
"""Repair plaintext mathematics across the existing question bank.

`save_questions` repairs new questions on the way in. This applies the same
pass to questions that were stored before that existed, so the bank converges
instead of carrying two eras of formatting.

Verify afterwards with:

    python3 -m pytest tests/test_bank_renders.py

which parses every expression with the KaTeX build the app actually ships.
Safe to re-run: repair_math is idempotent.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402


def main() -> int:
    db = sqlite3.connect(study.DB_PATH)
    db.row_factory = sqlite3.Row
    changed = 0

    for row in db.execute(
        "SELECT id, prompt, answer, explanation, choices_json, correct_choice FROM questions"
    ):
        old_choices = json.loads(row["choices_json"] or "[]")
        prompt = study.repair_math(row["prompt"])
        answer = study.repair_math(row["answer"])
        explanation = study.repair_math(row["explanation"])
        choices = [study.repair_math(choice) for choice in old_choices]

        # The save gate requires choices[correct_choice] == answer. Repairing
        # the two independently can break that identity, and a question whose
        # answer is not among its choices can never be answered correctly.
        if old_choices and 0 <= row["correct_choice"] < len(old_choices):
            choices[row["correct_choice"]] = answer

        unchanged = (prompt, answer, explanation, choices) == (
            row["prompt"], row["answer"], row["explanation"], old_choices,
        )
        if unchanged:
            continue

        db.execute(
            "UPDATE questions SET prompt=?, answer=?, explanation=?, choices_json=? WHERE id=?",
            (prompt, answer, explanation, json.dumps(choices), row["id"]),
        )
        changed += 1

    db.commit()
    remaining = sum(
        1
        for row in db.execute("SELECT prompt, answer, explanation FROM questions")
        if any(study.has_plaintext_math(field) for field in row)
    )
    db.close()

    print(f"Repaired {changed} question(s).")
    if remaining:
        print(f"WARNING: {remaining} still contain unrepairable plaintext maths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
