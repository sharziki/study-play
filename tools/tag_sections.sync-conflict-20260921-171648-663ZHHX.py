#!/usr/bin/env python3
"""Tag MA 261 questions with the textbook section they examine.

A quiz is scoped by section, not by concept. Quiz 4 covers 14.4, 15.1 and 15.2
and nothing else, so without a section on each question the app can say "Quiz 4
is tomorrow" and still serve Green's theorem. Being told the right deadline and
then drilled on the wrong material is worse than no deadline at all.

The section list is the department's own, read off the course guide Sharvil
already maintains at ultimate-calc3.vercel.app, which tags every section with
the quiz or midterm that tests it. Each section carries the vocabulary that
identifies it, written here rather than inferred, because a wrong tag silently
sends quiz revision to the wrong chapter.

Matching prefers the material's unit when it is unambiguous, then falls back to
the question's own words. A question that matches nothing keeps an empty
section and simply never appears in a scoped quiz session; it is still served
by ordinary topic review, so nothing is lost, only unscoped.

    python3 tools/tag_sections.py            # tag what is untagged
    python3 tools/tag_sections.py --dry-run
    python3 tools/tag_sections.py --retag    # recompute every question
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402

CAMPAIGN = "MA 26100"

# section -> (display name, identifying terms). Terms are lowercase and matched
# as whole words against the question's topic and prompt. Order matters only in
# that a section with more matched terms wins.
SECTIONS: list[tuple[str, str, tuple[str, ...]]] = [
    ("12.1", "Parametric equations", ("parametric", "parameterize", "parametrize")),
    ("13.1", "Vectors", ("vector", "magnitude", "unit vector", "component")),
    ("13.2", "Space, distance, spheres", ("sphere", "distance", "midpoint", "octant")),
    ("13.3", "Dot product", ("dot product", "projection", "orthogonal", "angle between", "scalar projection")),
    ("13.4", "Cross product", ("cross product", "determinant", "parallelogram", "triple product")),
    ("13.5", "Lines and planes", ("line", "plane", "normal vector", "intersection", "skew")),
    ("13.6", "Quadric surfaces", ("quadric", "surface", "ellipsoid", "hyperboloid", "paraboloid", "trace", "cone")),
    ("14.1", "Vector-valued functions", ("vector-valued", "vector function", "curve in space", "space curve")),
    ("14.2", "Derivatives and integrals of vector functions", ("derivative of", "tangent vector", "integral of")),
    ("14.3", "Motion, T, N, B", ("velocity", "acceleration", "speed", "motion", "tangential", "normal component", "binormal")),
    ("14.4", "Arc length and curvature", ("arc length", "curvature", "kappa", "osculating", "unit tangent")),
    ("15.1", "Surfaces and level curves", ("level curve", "level surface", "contour", "domain", "graph of")),
    ("15.2", "Limits and continuity", ("limit", "continuity", "continuous", "two-path", "path test", "does not exist")),
    ("15.3", "Partial derivatives", ("partial derivative", "partial", "clairaut", "mixed partial")),
    ("15.4", "Chain rule", ("chain rule", "implicit differentiation", "tree diagram")),
    ("15.5", "Gradient and directional derivatives", ("gradient", "directional derivative", "steepest", "rate of increase")),
    ("15.6", "Tangent planes and differentials", ("tangent plane", "linearization", "differential", "linear approximation")),
    ("15.7", "Maximum and minimum", ("critical point", "saddle", "local maximum", "local minimum", "second derivative test", "absolute maximum")),
    ("15.8", "Lagrange multipliers", ("lagrange", "constraint", "constrained")),
    ("16.1", "Double integrals", ("double integral", "iterated integral", "rectangle")),
    ("16.2", "Double integrals over general regions", ("general region", "order of integration", "type i", "type ii")),
    ("16.3", "Polar coordinates", ("polar", "r dr")),
    ("16.4", "Triple integrals", ("triple integral", "solid", "volume of the region")),
    ("16.5", "Cylindrical and spherical", ("cylindrical", "spherical", "rho", "phi")),
    ("16.6", "Mass, centroid, moments", ("mass", "centroid", "center of mass", "moment of inertia", "density")),
    ("16.7", "Change of variables", ("jacobian", "change of variables", "transformation")),
    ("17.1", "Vector fields", ("vector field", "field f")),
    ("17.2", "Line integrals", ("line integral", "along the curve", "work done")),
    ("17.3", "Conservative fields", ("conservative", "potential function", "path independent", "fundamental theorem for line")),
    ("17.4", "Green's theorem", ("green's theorem", "green theorem")),
    ("17.5", "Curl and divergence", ("curl", "divergence")),
    ("17.6", "Parametric surfaces and area", ("parametric surface", "surface area")),
    ("17.7", "Surface integrals", ("surface integral", "flux")),
    ("17.8", "Stokes and divergence theorems", ("stokes", "divergence theorem")),
]

# Unit titles map to the chapters they teach, which narrows an ambiguous match.
UNIT_CHAPTERS = {
    "1. Vectors and the Geometry of Space": {"12", "13"},
    "2. Vector Functions and Curves in Space": {"14"},
    "3. Partial Derivatives, Limits, and Continuity": {"15"},
    "4. Multiple Integrals": {"16"},
    "5. Vector Calculus": {"17"},
}


def unit_chapters(material_title: str) -> set[str] | None:
    for suffix, chapters in UNIT_CHAPTERS.items():
        if material_title.endswith(suffix):
            return chapters
    if "15.2" in material_title:
        return {"15"}
    return None


def score(text: str, terms: tuple[str, ...]) -> int:
    """How many of a section's identifying terms this text uses."""
    hits = 0
    for term in terms:
        pattern = r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"s?\b"
        if re.search(pattern, text):
            hits += 1
    return hits


def classify(topic: str, prompt: str, chapters: set[str] | None) -> str | None:
    """The section a question examines, or None when nothing fits well."""
    # The topic is the author's own label and is worth more than the prompt,
    # which is full of incidental words.
    topic_text = (topic or "").lower()
    full_text = f"{topic_text} {(prompt or '').lower()}"

    best: tuple[int, int, str] | None = None
    for section, _, terms in SECTIONS:
        if chapters is not None and section.split(".")[0] not in chapters:
            continue
        weighted = score(topic_text, terms) * 3 + score(full_text, terms)
        if weighted == 0:
            continue
        ranked = (weighted, len(terms), section)
        if best is None or ranked > best:
            best = ranked
    return best[2] if best else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retag", action="store_true", help="recompute already-tagged questions")
    parser.add_argument("--campaign", default=CAMPAIGN)
    args = parser.parse_args()

    tagged = 0
    unmatched = 0
    counts: dict[str, int] = {}
    with study.connect() as db:
        rows = db.execute(
            """SELECT q.id, q.topic, q.prompt, q.section, m.title AS material_title
               FROM questions q JOIN materials m ON m.id = q.material_id
               WHERE m.campaign = ?""",
            (args.campaign,),
        ).fetchall()

        for row in rows:
            if row["section"] and not args.retag:
                continue
            section = classify(row["topic"], row["prompt"], unit_chapters(row["material_title"]))
            if section is None:
                unmatched += 1
                continue
            counts[section] = counts.get(section, 0) + 1
            tagged += 1
            if not args.dry_run:
                db.execute("UPDATE questions SET section=? WHERE id=?", (section, row["id"]))
        if not args.dry_run:
            db.commit()

    for section, _, _ in SECTIONS:
        if counts.get(section):
            print(f"  {section:6} {counts[section]:4} question(s)")
    print(f"\n{tagged} tagged, {unmatched} left unscoped, {len(rows)} seen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
