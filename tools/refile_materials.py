#!/usr/bin/env python3
"""Move material that was filed under the wrong course.

Two misfilings made the app actively misleading, and both were invisible from
inside the app because the label looked plausible:

  - `newton` is Newtonian mechanics from `examples/`, filed under CS 18000. A
    physics question therefore appeared under a real CS exam countdown.
  - `Putnam 2025` is a competition paper, filed under MA 26100. It inherited
    the Quiz 15.2 countdown, so 19 competition questions sat at the top of the
    queue two days before an actual calculus quiz.

Neither belongs to a graded course, so each moves to a course with no exams.
Exam pressure then ranks them below anything being examined, while leaving them
reachable. Safe to re-run.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402


REASSIGNMENTS = [
    ("newton", "EXAMPLES", "Bundled examples"),
    ("Putnam 2025 — Problems & Solutions", "PUTNAM", "Putnam competition"),
]


def ensure_course(db: sqlite3.Connection, code: str, title: str) -> int:
    db.execute(
        "INSERT OR IGNORE INTO courses(code,title,created_at) VALUES (?,?,?)",
        (code, title, study.now().isoformat()),
    )
    return db.execute("SELECT id FROM courses WHERE code=?", (code,)).fetchone()[0]


def main() -> int:
    db = sqlite3.connect(study.DB_PATH)
    db.row_factory = sqlite3.Row
    moved = 0
    for title, code, course_title in REASSIGNMENTS:
        material = db.execute("SELECT id, campaign FROM materials WHERE title=?", (title,)).fetchone()
        if material is None:
            continue
        if material["campaign"] == code:
            continue
        course_id = ensure_course(db, code, course_title)
        db.execute(
            "UPDATE materials SET campaign=?, course_id=? WHERE id=?",
            (code, course_id, material["id"]),
        )
        print(f"{title!r}: {material['campaign']} -> {code}")
        moved += 1
    db.commit()
    db.close()
    print(f"{moved} material(s) reassigned." if moved else "Nothing to reassign.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
