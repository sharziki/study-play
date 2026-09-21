#!/usr/bin/env python3
"""Rewrite explanations that cite the source document instead of the subject.

The save gate checked the prompt and never the explanation, so 395 questions
shipped with reasoning like:

    "The material states that distance = speed x time applies at every
     instant, and the integral sums these instantaneous products."

The mathematics is right. The framing is wrong, and it is wrong at the moment
the learner is most receptive — immediately after a miss. Nothing in the app
shows them the material, so an explanation that appeals to it is appealing to
something they cannot see, which teaches them to trust an authority instead of
the argument.

Burying these would take the mathematics with the framing. Every instance is a
stock phrase — "the material states", "the material notes", "in the material" —
so the phrase is removed and the sentence re-pointed at the subject. The claim
is untouched: only who is said to be making it changes.

A rewrite is kept only when it passes the same gate a new question must pass
and leaves the sentence readable. Anything else is reported and left alone.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402

# Each pattern strips the attribution and leaves the claim standing. Order
# matters: the longest, most specific forms are tried first, because
# "as the material states" and "the material states" need different repairs.
# Verbs of attribution. Removing "the material" in front of one of these
# leaves the verb dangling — "States the acceleration points..." — so the verb
# goes with it and the claim becomes the sentence.
SAYS = (
    r"(?:states?|notes?|explains?|defines?|shows?|describes?|warns?|lists?|calls?|"
    r"distinguishes?|mentions?|says?|emphasi[sz]es?|highlights?|"
    r"introduces?|presents?|gives?|provides?|points? out|makes? clear|stresses?)"
)

REWRITES: list[tuple[re.Pattern[str], str]] = [
    # "..., as the material states that X" / "..., which the material notes."
    (re.compile(rf"\s*,?\s*\b(?:as|which|and)\s+the\s+material(?:'s)?\s+{SAYS}\b(?:\s+that)?\s*", re.I), " "),
    # "As stated in the material, X" and its variants.
    (re.compile(r"\s*,?\s*\bas\s+\w+\s+(?:in|by)\s+the\s+material\b\s*,?\s*", re.I), " "),
    # Verbs that describe an ACTION on the mathematics rather than an act of
    # telling. "The material derives this directly" has to keep its verb, or
    # the sentence loses what was done; only the speaker is replaced.
    (re.compile(r"\bthe\s+material(?:'s)?\s+(derives?|computes?|evaluates?|proves?|"
                r"applies|uses?|rewrites?|expands?|factors?|solves?)\b", re.I),
     lambda m: f"The standard argument {m.group(1).lower()}"),
    # "The material states that X" -> "X". The verb leaves with the subject.
    (re.compile(rf"\bthe\s+material(?:'s)?\s+(?:own\s+)?{SAYS}\b(?:\s+directly)?(?:\s+that)?\s*,?\s*", re.I), ""),
    (re.compile(rf"\bthe\s+material(?:'s)?\s+(?:own\s+)?{SAYS}\b\s*:\s*", re.I), ""),
    # "in the material", "from the material", "per the material"
    (re.compile(r"\s*,?\s*\b(?:in|from|per|according to|throughout)\s+the\s+material\b\s*,?\s*", re.I), " "),
    # Possessive: "the material's stated risk" -> "the stated risk"
    (re.compile(r"\bthe\s+material's\s+", re.I), "the "),
    # Bare trailing attribution: "..., the material states."
    (re.compile(rf"\s*,?\s*the\s+material\s+{SAYS}\s*\.\s*$", re.I), "."),
    # Whatever remains, e.g. "the material" used as a bare noun phrase.
    (re.compile(r"\bthe\s+material\b\s*", re.I), ""),
]

SENTENCE_START = re.compile(r"(^|[.!?]\s+)([a-z])")


# A sentence must still have a subject after the attribution is removed.
DANGLING = re.compile(rf"(^|[.!?]\s+){SAYS}\b", re.I)


def tidy(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"^[,;:]\s*", "", text)
    # A removed leading clause can leave the sentence starting lower-case.
    return SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def repair(text: str) -> str | None:
    """A version of `text` that no longer cites the document, or None."""
    out = text
    for pattern, replacement in REWRITES:
        if study.tests_the_subject(out):
            break
        out = pattern.sub(replacement, out)  # type: ignore[arg-type]
    out = tidy(out)
    if not study.tests_the_subject(out):
        return None
    # "States the acceleration points in the direction of the net force" reads
    # as a fragment: the verb survived its subject. Better left for a human
    # than shipped as broken English.
    if DANGLING.search(out):
        return None
    # A repair that guts the sentence is not a repair.
    if len(out) < len(text) * 0.55 or len(out) < 40:
        return None
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show", type=int, default=6, help="examples to print")
    args = parser.parse_args()

    repaired = failed = 0
    shown = 0
    with study.connect() as db:
        rows = list(db.execute(
            "SELECT id, explanation FROM questions WHERE status='ready'"
        ))
        for row in rows:
            text = row["explanation"] or ""
            if study.tests_the_subject(text):
                continue
            fixed = repair(text)
            if fixed is None:
                failed += 1
                if shown < args.show:
                    print(f"  UNFIXED [{row['id']}] {text[:100]}")
                    shown += 1
                continue
            if shown < args.show:
                print(f"  [{row['id']}]\n    was: {text[:96]}\n    now: {fixed[:96]}")
                shown += 1
            repaired += 1
            if not args.dry_run:
                db.execute("UPDATE questions SET explanation=? WHERE id=?", (fixed, row["id"]))
        if not args.dry_run:
            db.commit()

    verb = "would be repaired" if args.dry_run else "repaired"
    print(f"\n{repaired} explanation(s) {verb}, {failed} left for burial.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
