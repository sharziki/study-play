#!/usr/bin/env python3
"""Top up the sections an assessment covers, thinnest first.

`deepen.py` works by topic and `study.py generate` works by material, and
neither answers the question that matters before a midterm: *which sections of
this exam do I have almost nothing for.* Midterm 1 covers nineteen sections;
four of them held zero questions and three more held fewer than six, while one
section held seventy. Studying that bank is studying limits.

This reads an assessment's own scope, counts what exists per section, and
generates against the material that teaches the thinnest ones. Sections are
filled in ascending order of coverage, so an interrupted run has still spent
its time where the gap was largest.

    python3 tools/fill_exam_scope.py "Midterm 1" --target 8
    python3 tools/fill_exam_scope.py "Quiz 4" --target 10 --dry-run
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import study  # noqa: E402

# One definition, in study, so a course whose chapters are single digits is not
# silently skipped by three tools with their own copy of the pattern.
sections_of = study.material_sections


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exam", help='assessment title or prefix, e.g. "Midterm 1"')
    parser.add_argument("--target", type=int, default=8, help="questions a section should hold")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, help="stop after this many sections")
    args = parser.parse_args()

    with study.connect() as db:
        row = db.execute(
            "SELECT id, title, scope_json, course_id FROM exams WHERE title LIKE ? ORDER BY exam_date LIMIT 1",
            (f"{args.exam}%",),
        ).fetchone()
        if row is None:
            print(f"No assessment matching {args.exam!r}.")
            return 1
        scope = json.loads(row["scope_json"] or "[]")
        if not scope:
            print(f"{row['title']} publishes no scope, so there is nothing to fill against.")
            return 1

        counts = {
            item["section"]: item["n"]
            for item in db.execute(
                """SELECT q.section, COUNT(*) AS n FROM questions q
                   JOIN materials m ON m.id = q.material_id
                   WHERE q.status='ready' AND m.course_id = ? GROUP BY q.section""",
                (row["course_id"],),
            )
        }

        # Which material teaches each section. A material covering two sections
        # serves both, which is how arc length and curvature are taught.
        teaches: dict[str, list[int]] = {}
        titles: dict[int, str] = {}
        for material in db.execute(
            "SELECT id, title FROM materials WHERE course_id = ?", (row["course_id"],)
        ):
            titles[material["id"]] = material["title"]
            for section in sections_of(material["title"]):
                teaches.setdefault(section, []).append(material["id"])

    gaps = sorted(
        ((section, counts.get(section, 0)) for section in scope if counts.get(section, 0) < args.target),
        key=lambda item: item[1],
    )
    if not gaps:
        print(f"{row['title']}: every section already holds {args.target}+.")
        return 0

    print(f"{row['title']} — {len(gaps)} section(s) under {args.target}:")
    planned: list[tuple[int, str, int]] = []
    for section, have in gaps:
        materials = teaches.get(section)
        if not materials:
            print(f"  {section:6} {have:3} → no material teaches it; import one first")
            continue
        need = args.target - have
        print(f"  {section:6} {have:3} → need {need:2}  via {titles[materials[0]][:46]}")
        # A material teaching two sections needs one call PER section, aimed
        # at the section that is short. Asking once for the pair follows the
        # material's own emphasis and tops up whichever half was already
        # fuller: six calls produced curvature questions while arc length
        # stayed two short of what its quiz needs.
        planned.append((materials[0], section, need))

    if args.dry_run or not planned:
        return 0

    items = planned[: args.limit] if args.limit else planned
    for material_id, section, need in items:
        print(f"\n→ {section}  {titles[material_id][:52]} (+{need})")
        result = subprocess.run(
            [sys.executable, str(ROOT / "study.py"), "generate",
             "--material", str(material_id), "--count", str(need + 4),
             "--focus", section],
            capture_output=True, text=True, timeout=1800,
        )
        print("  " + (result.stdout.strip().splitlines() or ["no output"])[-1])

    # Newly generated questions carry their section from the material title,
    # but a two-section material cannot say which half, so the classifier runs
    # afterwards to place those by content.
    subprocess.run([sys.executable, str(ROOT / "tools" / "tag_sections.py")], capture_output=True)
    print("\nRe-tagged sections.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
