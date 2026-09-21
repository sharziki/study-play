#!/usr/bin/env python3
"""What is coming, and whether the app can actually teach and test it.

One command that answers the question every session so far has had to
reconstruct from ad-hoc SQL: for each upcoming assessment, does it have a
published scope, are there questions inside that scope, and does every node in
it have a teach step.

The three failure modes this makes visible, each of which has happened:

- **No scope.** The exam row exists and names nothing, so the app serves an
  empty session. Unknown scope deliberately serves nothing rather than
  widening to the whole course, so this is silent from the learner's side.
- **Scope with no questions.** A section is named and the bank has nothing
  tagged to it.
- **Questions with no teach step.** The node can be tested but not taught,
  which for an unmet concept makes retrieval a guess.

    python3 tools/exam_readiness.py
    python3 tools/exam_readiness.py --campaign "STAT 350" --weeks 4
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", help="only this class")
    parser.add_argument("--weeks", type=int, default=6, help="horizon (default %(default)s)")
    args = parser.parse_args()

    horizon = args.weeks * 7
    with study.connect() as db:
        rows = []
        for items in study.upcoming_assessments(db).values():
            for item in items:
                if item["days_left"] > horizon:
                    continue
                if args.campaign and item["course_code"] != args.campaign:
                    continue
                scope = item["scope"]
                questions = nodes = untaught = 0
                if scope:
                    marks = ",".join("?" * len(scope))
                    stats = db.execute(
                        f"""SELECT COUNT(*) AS questions,
                                   COUNT(DISTINCT q.topic) AS nodes,
                                   COUNT(DISTINCT CASE WHEN l.id IS NULL THEN q.topic END) AS untaught
                            FROM questions q
                            JOIN materials m ON m.id = q.material_id
                            LEFT JOIN lessons l ON l.material_id = m.id AND l.topic = q.topic
                            WHERE q.status='ready' AND m.course_id = ?
                              AND q.section IN ({marks})""",
                        [item["course_id"], *scope],
                    ).fetchone()
                    questions, nodes, untaught = stats["questions"], stats["nodes"], stats["untaught"]
                rows.append((item, scope, questions, nodes, untaught))

    if not rows:
        print(f"Nothing scheduled in the next {args.weeks} week(s).")
        return 0

    rows.sort(key=lambda row: row[0]["days_left"])
    print(f"{'WHEN':>9}  {'COURSE':9} {'ASSESSMENT':30} {'SCOPE':>6} {'Qs':>5} {'NODES':>6} {'UNTAUGHT':>9}")
    problems = 0
    for item, scope, questions, nodes, untaught in rows:
        when = "today" if item["days_left"] == 0 else (
            "tomorrow" if item["days_left"] == 1 else f"{item['days_left']}d"
        )
        flag = ""
        if not scope:
            flag = "  ← NO SCOPE: serves nothing"
            problems += 1
        elif not questions:
            flag = "  ← scope has no questions"
            problems += 1
        elif untaught:
            flag = f"  ← {untaught} node(s) cannot be taught"
        print(
            f"{when:>9}  {item['course_code']:9} {item['exam_title'][:30]:30} "
            f"{len(scope):>6} {questions:>5} {nodes:>6} {untaught:>9}{flag}"
        )

    print()
    print(f"{len(rows)} assessment(s), {problems} that would serve an empty session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
