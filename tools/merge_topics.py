#!/usr/bin/env python3
"""Merge near-duplicate topic names inside one section into a single node.

The path advances when a node's average mastery clears the recall threshold,
and a node is one `questions.topic`. Section 14.5 held thirteen nodes:
"Curvature intuition", "Curvature formulas", "Curvature of a circle",
"Curvature of a plane curve \\(y=f(x)\\)", "Curvature of a plane curve y=f(x)",
and so on — sixteen questions spread so thin that every one of them was a node
completed by a single lucky recall. That is the defect `deepen.py` exists to
undo, and plain generation recreates it: each call invents its own topic names,
and nothing tells the next call what the last one chose.

`deepen.py` can only deepen a node that exists. When the same idea is already
split across a dozen names, deepening them all buys twelve shallow nodes rather
than one real one. So they are merged first, and only then topped up.

Merging is by section: two topics in the same textbook section whose names
share their distinctive words are the same node. Nothing merges across
sections, because 14.4 and 14.5 are separately examinable and a quiz can name
one without the other.

The largest node's name wins, since that is the one the learner has already
seen and whose review history is deepest.

    python3 tools/merge_topics.py "MA 26100" --dry-run
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402

# Words that do not distinguish one topic from another.
NOISE = {
    "the", "a", "an", "of", "for", "and", "or", "to", "in", "on", "with", "by",
    "as", "at", "from", "its", "it", "is", "are", "be", "using", "use", "via",
    "given", "when", "what", "why", "how", "vs", "versus", "into",
}

# A node this large is established; it is not folded into anything else.
ESTABLISHED = 6

# Words that name a specific object rather than describe one. If two topics
# disagree on any of these, they are different ideas however much else they
# share: "Dot product derivative rule" and "Cross product derivative order"
# overlap on `product` and `derivative` and are opposites.
DISCRIMINATING = {
    "dot", "cross", "curl", "divergence", "gradient",
    "arc", "curvature", "torsion", "tangent", "normal", "binormal",
    "double", "triple", "line", "surface", "polar", "cylindrical", "spherical",
    "limit", "continuity", "partial", "chain", "directional",
    "sphere", "cylinder", "plane", "cone", "paraboloid", "hyperboloid",
    "green", "stokes", "conservative", "potential", "flux", "work",
    "maximum", "minimum", "saddle", "lagrange", "jacobian",
}


def terms(topic: str) -> set[str]:
    """The distinctive words of a topic name, with LaTeX stripped out."""
    plain = re.sub(r"\\\(.*?\\\)|\\[a-zA-Z]+|[{}\\\\$]", " ", topic or "")
    return {
        word
        for word in re.findall(r"[a-z]+", plain.lower())
        if word not in NOISE and len(word) > 2
    }


def same_idea(left: str, right: str) -> bool:
    """Whether two topic names in one section name the same idea.

    One name's distinctive words being a subset of the other's is the signal:
    "Curvature of a circle" inside "Curvature of a circle of radius a", and
    "Curvature intuition" against "Curvature formulas" — both are curvature,
    which is the node. Requiring a shared word beyond that keeps two genuinely
    different ideas apart even when one name is short.
    """
    a, b = terms(left), terms(right)
    if not a or not b:
        return False
    # A disagreement on a naming word settles it. `arc length` and `curvature`
    # are taught in the same breath and are still separately examinable, so a
    # topic naming one and a topic naming the other stay apart.
    if (a & DISCRIMINATING) != (b & DISCRIMINATING):
        return False
    shared = a & b
    if not shared:
        return False
    # Either name is contained in the other, or they overlap substantially.
    return a <= b or b <= a or len(shared) / min(len(a), len(b)) >= 0.5


# A paper's own mixed-review node names the paper. Two different papers share
# almost every word of their names and are not the same node: they are the
# leftovers of two different exams, and merging them buries which is which.
PAPER_NODE = re.compile(r"—\s*mixed review\s*$")


def plan(db, campaign: str) -> list[tuple[str, list[tuple[str, int]]]]:
    """Groups of topics that should become one node, per section."""
    by_section: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for row in db.execute(
        """SELECT q.section, q.topic, COUNT(*) AS n
           FROM questions q JOIN materials m ON m.id = q.material_id
           WHERE m.campaign = ? AND q.status='ready' AND q.section != ''
           GROUP BY q.section, q.topic ORDER BY q.section, COUNT(*) DESC""",
        (campaign,),
    ):
        if PAPER_NODE.search(row["topic"]):
            continue
        by_section[row["section"]].append((row["topic"], row["n"]))

    merges: list[tuple[str, list[tuple[str, int]]]] = []
    for section, topics in by_section.items():
        taken: set[str] = set()
        # Largest first, so the established node is the one others fold into.
        for name, count in topics:
            if name in taken:
                continue
            group = [(name, count)]
            for other, other_count in topics:
                if other in taken or other == name:
                    continue
                # An established node is a destination, never a source.
                if other_count >= ESTABLISHED:
                    continue
                if same_idea(name, other):
                    group.append((other, other_count))
                    taken.add(other)
            taken.add(name)
            if len(group) > 1:
                merges.append((section, group))
    return merges


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", nargs="?", default="MA 26100")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    moved = 0
    with study.connect() as db:
        merges = plan(db, args.campaign)
        for section, group in merges:
            keep, keep_n = group[0]
            folded = group[1:]
            print(f"  {section}  {keep!r} ({keep_n})")
            for name, count in folded:
                print(f"         + {name!r} ({count})")
                moved += count
                if not args.dry_run:
                    db.execute(
                        """UPDATE questions SET topic=?
                           WHERE topic=? AND section=? AND id IN (
                             SELECT q.id FROM questions q
                             JOIN materials m ON m.id = q.material_id
                             WHERE m.campaign=?)""",
                        (keep, name, section, args.campaign),
                    )
        if not args.dry_run:
            db.commit()

    verb = "would move" if args.dry_run else "moved"
    print(f"\n{len(merges)} merge(s), {verb} {moved} question(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
