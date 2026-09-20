"""Human titles for imported units.

A unit heading is the only label a learner ever sees for a body of material, and
the importers were deriving it from the source filename. That produced headings
like "STAT 350 · 10.3 Ht For Mean Sigma Unknown" and "STAT 350 · 7.4 Discret Rvs
And Clt": a `.title()` call over a URL slug, complete with the upstream typo.

The rules here are deliberately narrow.

  - Expand only abbreviations that are genuinely ambiguous to a reader ("Ht",
    "Cb", "Lr"). An acronym a statistics student reads fluently stays an
    acronym, but in its conventional casing: "CLT", "ANOVA", "IQR", "PMF".
  - Lowercase the small words a `.title()` call wrongly capitalised.
  - Fix source typos only where the intended word is unambiguous.

Everything is a pure string transform, so it can be applied to the database by
`tools/retitle_materials.py` and to new imports by the importers, and the two
cannot drift apart.
"""

import re


# Expansions, applied word by word. Keys are lowercase; values are final casing.
#
# Two kinds live here. An abbreviation that no one reads aloud as letters is
# expanded ("Ci" -> "Confidence Interval"). An acronym that is spoken as letters
# keeps its form but gains its conventional casing ("Clt" -> "CLT"), because
# spelling it out makes a heading longer without making it clearer.
WORDS = {
    # Spoken as letters: fix the casing only.
    "clt": "CLT",
    "anova": "ANOVA",
    "iqr": "IQR",
    "sd": "SD",
    "pmf": "PMF",
    "pmfs": "PMFs",
    "pdf": "PDF",
    "pdfs": "PDFs",
    "cdf": "CDF",
    "cdfs": "CDFs",
    "rv": "Random Variable",
    "rvs": "Random Variables",
    # Expanded: unreadable as an abbreviation.
    "ht": "Hypothesis Testing",
    "ci": "Confidence Interval",
    "cb": "Confidence Bound",
    "lr": "Linear Regression",
    "cts": "Continuous",
    "pvalue": "P-value",
    "sigma": "Sigma",
    "sigmas": "Sigmas",
    # Source typos with one obvious intended word.
    "discret": "Discrete",
}

# `.title()` capitalises every word. English does not capitalise these unless
# they open the heading.
SMALL = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "of",
    "on", "or", "the", "to", "with",
}

# Paired abbreviations that read as one idea. Applied before the word pass so
# "Ci Ht Two Samples" does not become "Confidence Interval Hypothesis Testing".
PHRASES = [
    (r"\bci\s+ht\b", "Confidence Intervals and Hypothesis Testing"),
    (r"\bci\s+cb\b", "Confidence Intervals and Bounds"),
    (r"\bht\s+errors\b", "Hypothesis Testing Errors"),
]


def humanize(text: str) -> str:
    """A readable heading for one section, from its filename-derived title.

    Idempotent: running it on its own output changes nothing, which is what
    makes the retitling tool safe to re-run against a live database.
    """
    if not text:
        return text
    working = text
    for pattern, replacement in PHRASES:
        working = re.sub(pattern, replacement, working, flags=re.IGNORECASE)

    out: list[str] = []
    for index, word in enumerate(working.split()):
        lowered = word.lower()
        if lowered in WORDS:
            out.append(WORDS[lowered])
        elif lowered in SMALL and index > 0 and not _opens_clause(out):
            out.append(lowered)
        else:
            out.append(word)
    return " ".join(out)


def _opens_clause(out: list[str]) -> bool:
    """Whether the previous token ended a clause, so the next word starts one.

    A numbered heading is the case that matters: in "CS 18000 · 5. The
    Object-Oriented Approach", "The" opens the description and must keep its
    capital, even though it is neither the first word nor a proper noun. An
    earlier version checked only separators and shipped "5. the Object-Oriented
    Approach" to the live database.
    """
    return bool(out) and out[-1].endswith(("·", ":", "—", "-", ".", "!", "?"))


def section_title(course: str, section: str, slug: str) -> str:
    """The full unit heading an importer should store.

    `course` is the course code ("STAT 350"), `section` the syllabus number
    ("10.3"), and `slug` the filename-derived description. Keeping the
    composition here means a re-import produces exactly the title the retitling
    tool would produce for an existing row.
    """
    described = humanize(slug.replace("-", " ").title())
    return f"{course} · {section} {described}".rstrip()
