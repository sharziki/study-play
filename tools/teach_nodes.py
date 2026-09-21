#!/usr/bin/env python3
"""Generate the teach step for nodes that do not have one.

    python3 tools/teach_nodes.py "STAT 350" --limit 40

Lessons are the expensive artifact — two model calls each when the notation
needs a second pass — so this runs newest-exam-first and is safe to stop. It
recomputes the untaught nodes from the database on every run, so an interrupted
pass resumes exactly where it left off.

--per-material caps how many nodes are taught in one unit, which matters when a
class has more nodes than a session can pay for: taking two from each unit gives
the learner a teach step everywhere rather than a complete first chapter and
nothing after it.
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deepen  # noqa: E402  (shared busy-timeout helper)
import lessons  # noqa: E402
import study  # noqa: E402

# One definition, in study, so a course whose chapters are single digits is not
# silently skipped by three tools with their own copy of the pattern.
sections_of = study.material_sections


def ordered_materials(db, campaign: str, exam: str | None = None) -> list:
    """Materials for a class, soonest assessment first.

    Ordering by the COURSE's next exam puts every material in a class on the
    same footing, because they all share that one date. With a quiz tomorrow
    over four sections and forty-eight materials in the class, that ordering
    is no ordering at all: it taught whatever came first by id while fourteen
    nodes on tomorrow's quiz stayed untaught.

    Each material is now ranked by the soonest assessment that actually covers
    a section it teaches, so the quiz's own units come first.
    """
    upcoming = [
        item
        for items in study.upcoming_assessments(db).values()
        for item in items
    ]
    rows = db.execute("SELECT * FROM materials WHERE campaign=? ORDER BY id", (campaign,)).fetchall()

    if exam:
        wanted = next((i for i in upcoming if i["exam_title"].lower().startswith(exam.lower())), None)
        if wanted is None:
            raise SystemExit(f"No upcoming assessment matching {exam!r}.")
        scope = set(wanted["scope"])
        rows = [row for row in rows if scope & set(sections_of(row["title"]))]

    def key(row):
        sections = set(sections_of(row["title"]))
        covering = [
            item["days_left"]
            for item in upcoming
            if item["course_id"] == row["course_id"] and sections & set(item["scope"] or [])
        ]
        if covering:
            return (0, min(covering), row["id"])
        # No assessment names this material's sections, or it has none. It
        # still belongs to the class, just behind everything being examined.
        pressure = study.course_pressures(db).get(row["course_id"]) or {}
        days = pressure.get("days_left")
        return (1, days if days is not None else 10**6, row["id"])

    return sorted(rows, key=key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", help='class name, e.g. "STAT 350"')
    parser.add_argument("--limit", type=int, help="stop after this many lessons")
    parser.add_argument("--per-material", type=int, default=2,
                        help="lessons to generate per unit in one pass (default %(default)s)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--shard", type=int, default=0, help="this worker's index")
    parser.add_argument("--shards", type=int, default=1, help="how many workers are running")
    parser.add_argument("--exam", help='only units an assessment covers, e.g. "Quiz 4"')
    args = parser.parse_args()

    db = deepen.share(study.connect())
    materials = ordered_materials(db, args.campaign, args.exam)
    if not materials:
        print(f"No material for {args.campaign!r}.")
        return 1

    # Split by material so two workers never teach the same node. A lesson is
    # two model calls when the notation needs a second pass, so a whole class is
    # hours; the exam-pressure ordering is preserved inside each shard.
    if args.shards > 1:
        materials = [m for index, m in enumerate(materials) if index % args.shards == args.shard]
        print(f"shard {args.shard}/{args.shards}: {len(materials)} unit(s)")

    if args.dry_run:
        untaught = sum(len(lessons.untaught_topics(db, m["id"])) for m in materials)
        print(f"{untaught} node(s) without a teach step across {len(materials)} unit(s).")
        return 0

    started = time.time()
    made = failed = 0
    for material in materials:
        topics = lessons.untaught_topics(db, material["id"])[: args.per_material]
        for topic in topics:
            if args.limit and made >= args.limit:
                print(f"\nReached limit: {made} lesson(s).")
                return 0
            try:
                ok = lessons.teach_topic(db, material, topic)
            except Exception as error:  # noqa: BLE001 - one bad node must not end the run
                print(f"   FAILED {topic}: {error}", flush=True)
                failed += 1
                continue
            made += ok
            failed += not ok
            print(f"{'taught' if ok else 'REJECTED'}  {material['title'][:44]} · {topic[:40]}"
                  f"   ({made} made, {(time.time() - started) / 60:.1f} min)", flush=True)

    print(f"\n{made} lesson(s) generated, {failed} rejected or failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
