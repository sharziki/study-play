#!/usr/bin/env python3
"""Bury questions that examine the source document rather than the subject.

`study.tests_the_subject` rejects these at save time, but it was tightened
after the first imports, so questions written before it still sit in the bank:

    "The material introduces the interquartile range (IQR) and five-number
     summary as alternatives to the sample variance..."

The learner is shown one prompt at a time and never sees the source, so a
question about how the source is arranged is unanswerable and teaches nothing.
It still consumes a repetition and still gates a node.

These are buried rather than deleted. A bury is what the app already does when
a learner rejects a question: it stops being served, the review history survives,
and the decision is reversible. Deleting rows that `reviews` and `progress`
reference would take real history with them.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402


def offenders(db) -> list:
    """Ready questions whose prompt the current guard would reject."""
    return [
        row
        for row in db.execute("SELECT id, topic, prompt FROM questions WHERE status='ready'")
        if not study.tests_the_subject(row["prompt"]) or not study.is_self_contained(row["prompt"])
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = study.connect()
    found = offenders(db)
    for row in found:
        print(f"[{row['id']}] {row['prompt'][:96]}")
    if args.dry_run:
        print(f"\n{len(found)} question(s) would be buried.")
        return 0
    for row in found:
        db.execute("UPDATE questions SET status='buried' WHERE id=?", (row["id"],))
    db.commit()
    print(f"\n{len(found)} question(s) buried." if found else "\nNothing to bury.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
