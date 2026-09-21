#!/usr/bin/env python3
"""Tag every MA 261 question with the textbook section it examines.

Why this exists. A Purdue recitation quiz is defined by sections: Quiz 4 is
14.4, 14.5, 15.1 and 15.2, and nothing else. The app stored a concept name per
question ("Arc length and curvature") and nothing linked that to a section, so
it could order work by exam pressure but could not answer the only question
that matters the night before a quiz: *what is actually on it.*

The section list is the course's own, taken from the department calendar
(`sync-ma261-calendar.py`) and the section titles Purdue's MA 261 guide
publishes. Classification is by the section's own vocabulary plus a short list
of terms that identify a section unambiguously — "curvature" is 14.4 wherever
it appears, "Lagrange" is 15.8.

A question that cannot be placed is left blank rather than guessed at. Quiz
scope then serves only what it can prove is in scope, which is the honest
behaviour: showing a learner an out-of-scope question the night before a quiz
wastes the one evening they have.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402

# One definition, in study.
MATERIAL_SECTIONS = study.MATERIAL_SECTIONS


class _Titled(dict):
    """A row shaped the way `study.section_of` expects."""

    def keys(self):
        return list(dict.keys(self))

# Purdue MA 261 sections in teaching order, with the terms that identify each.
# The name comes from the course's published section list; the markers are the
# words that make a section recognisable on its own.
SECTIONS: list[tuple[str, str, tuple[str, ...]]] = [
    ("13.1", "Vectors", ("vector addition", "scalar multiple", "unit vector", "magnitude")),
    ("13.2", "Space, distance, spheres", ("sphere", "distance formula", "octant", "midpoint")),
    ("13.3", "Dot product", ("dot product", "scalar projection", "vector projection", "orthogonal", "angle between")),
    ("13.4", "Cross product", ("cross product", "torque", "parallelepiped", "area of the triangle", "right-hand")),
    ("12.1", "Parametric equations", ("parametric equation", "parameterize the curve", "eliminate the parameter")),
    ("13.5", "Lines and planes", ("line of intersection", "equation of the plane", "parallel to the plane",
                                  "perpendicular to the plane", "symmetric equation", "normal vector", "skew")),
    ("13.6", "Quadric surfaces", ("quadric", "hyperboloid", "paraboloid", "ellipsoid", "trace", "elliptic cone")),
    ("14.1", "Vector-valued functions", ("vector-valued", "vector function", "domain of the curve")),
    ("14.2", "Derivatives and integrals of vector functions", ("derivative of the vector", "tangent to the graph",
                                                               "integrate the vector")),
    ("14.3", "Motion in space", ("velocity", "acceleration", "speed", "projectile", "trajectory")),
    # Purdue teaches these as two sections and Quiz 4 names both, so they stay
    # apart even though many references print them under one heading.
    ("14.4", "Arc length", ("arc length", "reparameter", "length of the curve")),
    ("14.5", "Curvature and normal vectors", ("curvature", "unit tangent", "principal normal", "binormal",
                                              "osculating", "tangential component", "normal component", "torsion")),
    ("15.1", "Functions of several variables", ("level curve", "level set", "domain of f", "surface defined by",
                                                "contour", "graph of the function")),
    ("15.2", "Limits and continuity", ("limit", "continuous", "two-path", "does not exist", "squeeze")),
    ("15.3", "Partial derivatives", ("partial derivative", "clairaut", "mixed partial", "f_x", "f xx", "f yx")),
    ("15.4", "The chain rule", ("chain rule", "implicit differentiation", "tree diagram", "dz/dt")),
    ("15.5", "Directional derivatives and the gradient", ("gradient", "directional derivative",
                                                          "steepest", "maximum rate of increase")),
    ("15.6", "Tangent planes and linear approximation", ("tangent plane", "linear approximation", "differential",
                                                         "normal line to the surface")),
    ("15.7", "Maximum and minimum values", ("critical point", "saddle", "local maximum", "local minimum",
                                            "second derivative test", "absolute maximum")),
    ("15.8", "Lagrange multipliers", ("lagrange", "constraint", "subject to the constraint")),
    ("16.1", "Double integrals over rectangles", ("double integral", "rectangle", "iterated integral", "fubini")),
    ("16.2", "Double integrals over general regions", ("general region", "order of integration", "type i", "type ii")),
    ("16.3", "Double integrals in polar coordinates", ("polar", "r dr", "annulus")),
    ("16.4", "Triple integrals", ("triple integral", "solid region", "volume of the solid")),
    ("16.5", "Cylindrical and spherical coordinates", ("cylindrical", "spherical", "rho", "phi")),
    ("16.6", "Applications of multiple integrals", ("center of mass", "centroid", "moment of inertia", "mass of the")),
    ("16.7", "Change of variables", ("jacobian", "change of variables", "transformation")),
    ("17.1", "Vector fields", ("vector field", "flow line", "sketch the field")),
    ("17.2", "Line integrals", ("line integral", "work done", "circulation", "ds along")),
    ("17.3", "Conservative vector fields", ("conservative", "potential function", "path independen",
                                            "fundamental theorem for line")),
    ("17.4", "Green's theorem", ("green's theorem", "greens theorem")),
    ("17.5", "Curl and divergence", ("curl", "divergence")),
    ("17.6", "Surface integrals", ("surface integral", "parametric surface", "surface area", "flux across the surface")),
    ("17.7", "Stokes' theorem", ("stokes",)),
    ("17.8", "Divergence theorem", ("divergence theorem", "closed surface")),
]

# Concept names the bank already uses, mapped to the section that owns them.
# A question filed under one of these is in that section by definition, which
# is stronger evidence than a phrase match on the prompt.
TOPIC_SECTIONS = {
    "vectors": "13.1",
    "the dot product": "13.3",
    "the cross product": "13.4",
    "lines and planes": "13.5",
    "vector-valued functions": "14.1",
    "tangents and motion": "14.3",
    # These nodes cover both halves; the prompt decides which.
    "arc length and curvature": None,
    "curvature formulas": "14.5",
    "curvature intuition": "14.5",
    "radius of curvature": "14.5",
    "arc length computation": "14.4",
    "arc length concept": "14.4",
    "reparametrization by arc length": "14.4",
    "reparameterization by arc length": "14.4",
    "functions of several variables": "15.1",
    "limits": "15.2",
    "continuity": "15.2",
    "continuity of a piecewise function": "15.2",
    "direct substitution with trig": "15.2",
    "factor-and-cancel limit (0/0)": "15.2",
    "two-path test, axis paths (3-part multiple choice)": "15.2",
    "two-path test, line path with sign split": "15.2",
    "partial derivatives": "15.3",
    "the chain rule and the gradient": "15.5",
    "optimization": "15.7",
    "double integrals": "16.1",
    "polar coordinates": "16.3",
    "triple integrals": "16.4",
    "applications and change of variables": "16.7",
    "vector fields": "17.1",
    "line integrals": "17.2",
    "the fundamental theorem for line integrals": "17.3",
    "green's theorem": "17.4",
    "curl and divergence": "17.5",
    "surface integrals and the big theorems": "17.6",
}

MARKERS = {section: markers for section, _, markers in SECTIONS}
NAMES = {section: name for section, name, _ in SECTIONS}


def classify(prompt: str, topic: str) -> str | None:
    """The section a question examines, or None when it cannot be placed."""
    key = (topic or "").strip().lower()
    if key in TOPIC_SECTIONS:
        known = TOPIC_SECTIONS[key]
        if known:
            return known
        # An explicit None means the node spans sections and the prompt has to
        # decide, which is the case for "Arc length and curvature" — Purdue
        # splits that into 14.4 and 14.5 and Quiz 4 names both.

    text = re.sub(r"\\[a-zA-Z]+|[{}\\\\]", " ", f"{topic} {prompt}").lower()
    best: tuple[int, str] | None = None
    for section, markers in MARKERS.items():
        hits = sum(1 for marker in markers if marker in text)
        if hits and (best is None or hits > best[0]):
            best = (hits, section)
    return best[1] if best else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default="MA 26100")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tagged = 0
    unplaced: list[str] = []
    counts: dict[str, int] = {}

    with study.connect() as db:
        rows = list(db.execute(
            """SELECT q.id, q.prompt, q.topic, q.section, m.title AS material_title
               FROM questions q
               JOIN materials m ON m.id = q.material_id
               WHERE m.campaign = ?""",
            (args.campaign,),
        ))
        for row in rows:
            # A question generated from a material that teaches exactly one
            # section already carries the truth, and content matching is a
            # weaker signal than the source itself. Re-classifying those
            # scattered eleven questions written from the 14.2 material across
            # eight different sections, because a derivative example mentions
            # vectors and a vector example mentions dot products.
            owned = study.section_of(_Titled(title=row["material_title"]), {})
            if owned:
                section = owned
            else:
                section = classify(row["prompt"], row["topic"])
            if section is None:
                # A material teaching two sections cannot say which half a
                # question tests, but it can say the question is in one of
                # them. Falling back to the first is better than leaving the
                # question untagged and therefore invisible to quiz scope:
                # seven arc-length and curvature questions sat outside Quiz 4
                # entirely because their topic names were not in the map.
                owned_pair = MATERIAL_SECTIONS.search(row["material_title"] or "")
                if owned_pair:
                    section = owned_pair.group(1).split()[0]
            if section is None:
                unplaced.append(f"{row['topic']} :: {row['prompt'][:70]}")
                continue
            counts[section] = counts.get(section, 0) + 1
            if not args.dry_run:
                db.execute("UPDATE questions SET section=? WHERE id=?", (section, row["id"]))
            tagged += 1
        if not args.dry_run:
            db.commit()

    # SECTIONS names MA 261's sections. Another campaign's numbers are its
    # own, so printing them through this table labelled STAT 350's 12.1 as
    # "Parametric equations", which is MA 261's.
    def order(section: str) -> tuple:
        parts = section.split(".")
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

    for section in sorted(counts, key=order):
        name = NAMES.get(section, "") if args.campaign == "MA 26100" else ""
        print(f"  {section:6} {name[:40]:42} {counts[section]:4}")
    print(f"\n{tagged} tagged, {len(unplaced)} unplaced, of {len(rows)} total.")
    for line in unplaced[:12]:
        print(f"    unplaced: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
