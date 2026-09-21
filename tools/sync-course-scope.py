#!/usr/bin/env python3
"""Give CS 180 and STAT 350 exams the scope their syllabi already state.

MA 261 publishes a calendar PDF, so `sync-ma261-calendar.py` reads the scope
straight from the department. The other two courses do not, and their exam rows
carried an empty scope: Up Next greyed them out, and tapping one served
nothing, because unknown scope deliberately serves nothing rather than widening
to the whole course.

Both syllabi do state their coverage, and it is recorded in Nova:

- **STAT 350** teaches chapters 1-13 in order. Exam 1 (Oct 7) covers chapters
  1-8, Exam 2 (Nov 17) covers 9-11, and the final is comprehensive with
  roughly 60-70% drawn from after Exam 2.
- **CS 18000** runs 14 weeks over 8 units. Exam 1 (Sep 30) covers units 1-3,
  and each later evening exam adds the units taught since the last one.

That mapping is declared here rather than inferred, because a wrong scope is
worse than none: it would tell the learner a chapter is not on the exam.

    python3 tools/sync-course-scope.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402

# Exam title prefix -> the chapters or units it covers.
#
# STAT 350 sections are `chapter.section`, so a chapter here means every
# section inside it. CS 180 units have no decimal, so a unit is itself.
SCOPE: dict[str, list[tuple[str, str, list[str]]]] = {
    "STAT 350": [
        ("Evening exam 2026-10-07", "Exam 1 (Chapters 1-8)", [str(n) for n in range(1, 9)]),
        ("Evening exam 2026-11-17", "Exam 2 (Chapters 9-11)", ["9", "10", "11"]),
        ("Final exam 2026-12-17", "Final exam (comprehensive)", [str(n) for n in range(1, 14)]),
    ],
    "CS 18000": [
        ("Evening exam 2026-09-30", "Exam 1 (Units 1-3)", ["1", "2", "3"]),
        ("Evening exam 2026-10-21", "Exam 2 (Units 1-5)", ["1", "2", "3", "4", "5"]),
        ("Evening exam 2026-11-11", "Exam 3 (Units 1-6)", ["1", "2", "3", "4", "5", "6"]),
        ("Evening exam 2026-12-02", "Exam 4 (Units 1-8)", [str(n) for n in range(1, 9)]),
        ("Final exam 2026-12-16", "Final exam (comprehensive)", [str(n) for n in range(1, 9)]),
    ],
}


def expand(course_id: int, chapters: list[str], db) -> list[str]:
    """Every section of this course that sits inside the named chapters.

    A chapter is named, not a section, because a syllabus says "chapters 1-8"
    and the bank stores `4.4`. Listing the sections that actually exist keeps
    the scope honest: it can only name material the learner can be served.
    """
    have = [
        row["section"]
        for row in db.execute(
            """SELECT DISTINCT q.section FROM questions q
               JOIN materials m ON m.id = q.material_id
               WHERE m.course_id = ? AND q.section != ''""",
            (course_id,),
        )
    ]
    wanted = set(chapters)
    return sorted(
        (section for section in have if section.split(".")[0] in wanted),
        key=lambda s: tuple(int(part) for part in s.split(".")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    updated = 0
    with study.connect() as db:
        for code, exams in SCOPE.items():
            course = db.execute("SELECT id FROM courses WHERE code=?", (code,)).fetchone()
            if course is None:
                print(f"  {code}: not a course in this database")
                continue
            print(f"\n{code}")
            for old_title, new_title, chapters in exams:
                row = db.execute(
                    "SELECT id, exam_date FROM exams WHERE course_id=? AND title=?",
                    (course["id"], old_title),
                ).fetchone()
                if row is None:
                    print(f"  {old_title}: no such exam row, skipped")
                    continue
                scope = expand(course["id"], chapters, db)
                if not scope:
                    print(f"  {new_title}: no sections tagged yet, skipped")
                    continue
                print(f"  {row['exam_date']}  {new_title:32} {len(scope):3} section(s)")
                updated += 1
                if not args.dry_run:
                    db.execute(
                        "UPDATE exams SET title=?, scope_json=? WHERE id=?",
                        (new_title, json.dumps(scope), row["id"]),
                    )
        if not args.dry_run:
            db.commit()

    verb = "would be scoped" if args.dry_run else "scoped"
    print(f"\n{updated} exam(s) {verb}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
