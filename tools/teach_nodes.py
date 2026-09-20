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
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deepen  # noqa: E402  (shared busy-timeout helper)
import lessons  # noqa: E402
import study  # noqa: E402


def ordered_materials(db, campaign: str) -> list:
    """Materials for a class, soonest exam first.

    The same ordering the learning path uses, so the units being taught are the
    units at the top of the learner's screen.
    """
    pressures = study.course_pressures(db)
    rows = db.execute("SELECT * FROM materials WHERE campaign=? ORDER BY id", (campaign,)).fetchall()

    def key(row):
        pressure = pressures.get(row["course_id"]) or {}
        days = pressure.get("days_left")
        return (days is None, days if days is not None else 0, row["id"])

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
    args = parser.parse_args()

    db = deepen.share(study.connect())
    materials = ordered_materials(db, args.campaign)
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
