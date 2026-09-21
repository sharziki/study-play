#!/usr/bin/env python3
"""Import the MA 261 guide as real teaching material, section by section.

Why this exists. The MA 26100 bank was generated from the official catalog
description — one paragraph per chapter — so the whole of "Vector functions and
curves in space" was 1,823 characters of summary. Two of Quiz 4's four sections
had five questions between them, and no amount of re-running generation fixes
that: a model asked for more questions about a paragraph writes more questions
about a paragraph.

`https://ultimate-calc3.vercel.app/guide.html` is Sharvil's own MA 261 guide,
built for this exact course and already tagged with the quiz that tests each
section. It carries the thing the catalog description does not: the intuition,
the algorithm, the traps. That is what a question can be grounded in.

Two things this has to get right.

KaTeX renders every expression three times in the DOM — the typeset glyphs, the
LaTeX source, and a screen-reader string — so naive text extraction triples
every formula into noise. The `<annotation>` element holds the LaTeX source, so
each expression is replaced by that one form and the other two are dropped.

And a section is only imported when it carries enough prose to ground a
question. A short stub would import cleanly, generate confidently, and teach
from nothing.
"""

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study  # noqa: E402

GUIDE = "https://ultimate-calc3.vercel.app/guide.html"
CAMPAIGN = "MA 26100"

# Each section opens with an anchor whose id encodes the number: `id="s144"`
# is 14.4, `id="s133b"` is 13.3b. The printed label lives in a `sec-n` span and
# may name a range ("14.4-14.5"), which matters: a section teaching two of the
# course's numbered sections has to be tagged with both, or half a quiz's scope
# silently has no material behind it.
ANCHOR = re.compile(r'id="s(1[2-7])(\d)([ab]?)"', re.I)
SECTION_LABEL = re.compile(r'class="sec-n"[^>]*>([^<]+)<', re.I)
TITLE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S | re.I)
# A label may name a range of sections rather than one.
LABEL_PART = re.compile(r"1[2-7]\.\d[ab]?")

# Material shorter than this is a stub, not a lesson.
MIN_CHARS = 700

# The page footer follows the last section, so without this the final section
# imports the site's nav and colophon as though it were mathematics.
FOOTER = re.compile(
    r"Lesson numbering and quiz badges|Not affiliated with or endorsed|"
    r"©\s*\d{4}\s+Sharvil|Semester map\s*·\s*Study by quiz",
    re.I,
)

# A course-wide index also trails the last section. It lists every section in
# the course, so questions generated from it would be about the syllabus.
INDEX_RUN = re.compile(r"(?:^1[2-7]\.\d\b.*\n){4,}", re.M)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"user-agent": "intellect-importer"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_katex(markup: str) -> str:
    """Replace each rendered expression with its LaTeX source, once.

    KaTeX emits the same expression three ways. Left alone, `\\int_a^b` arrives
    as the typeset glyphs, then the source, then a spoken form, and a question
    generated from that is grounded in triplicated noise.
    """

    def one(match: re.Match[str]) -> str:
        block = match.group(0)
        source = re.search(r"<annotation[^>]*>(.*?)</annotation>", block, re.S)
        if not source:
            return " "
        latex = html.unescape(re.sub(r"<[^>]+>", "", source.group(1))).strip()
        return f" \\({latex}\\) " if latex else " "

    # Innermost-first so a display wrapper does not swallow its own annotation.
    return re.sub(r'<span class="katex(?:-display)?"[^>]*>.*?</span>\s*</span>', one, markup, flags=re.S)


def to_text(markup: str) -> str:
    markup = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    markup = strip_katex(markup)
    markup = re.sub(r"<(li|p|div|h[1-6]|br|tr)\b[^>]*>", "\n", markup, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def split_sections(markup: str) -> list[tuple[list[str], str, str]]:
    """The guide as (sections, title, body), in document order.

    `sections` is a list because one part of the guide can teach two of the
    course's numbered sections — arc length and curvature are written together
    — and a quiz naming both must find material for both.
    """
    marks = [(m.start(), f"{m.group(1)}.{m.group(2)}{m.group(3)}") for m in ANCHOR.finditer(markup)]
    out = []
    for index, (start, anchor) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(markup)
        block = markup[start:end]

        label = SECTION_LABEL.search(block)
        numbers = LABEL_PART.findall(html.unescape(label.group(1))) if label else []
        sections = numbers or [anchor]

        heading = TITLE.search(block)
        title = to_text(heading.group(1)).strip() if heading else anchor

        body = to_text(block)
        for pattern in (FOOTER, INDEX_RUN):
            cut = pattern.search(body)
            if cut:
                body = body[: cut.start()].rstrip()
        # The anchor id itself leads the extracted text; drop that line.
        body = re.sub(r"^id=\"s\d+[ab]?\">\s*", "", body).strip()
        out.append((sections, title, body))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", nargs="*", help="only these sections, e.g. 14.4 14.5")
    args = parser.parse_args()

    sections = split_sections(fetch(GUIDE))
    if not sections:
        print("No sections found; the guide's markup may have changed.")
        return 1

    imported = skipped = 0
    with study.connect() as db:
        course = db.execute("SELECT id FROM courses WHERE code=?", (CAMPAIGN,)).fetchone()
        for numbers, title, body in sections:
            if args.only and not set(numbers) & set(args.only):
                continue
            section = " ".join(numbers)
            if len(body) < MIN_CHARS:
                print(f"  skip {section:11} {title[:32]:34} {len(body):5} chars — too thin to teach from")
                skipped += 1
                continue

            name = f"{CAMPAIGN} · {section} {title}"
            content = f"# {name}\n\nSource: {GUIDE}\n\n{body}\n"
            print(f"  {section:11} {title[:32]:34} {len(body):5} chars")
            if args.dry_run:
                continue

            digest = study.hashlib.sha256(content.encode()).hexdigest()
            existing = db.execute("SELECT id FROM materials WHERE content_hash=?", (digest,)).fetchone()
            if existing:
                continue
            db.execute(
                """INSERT INTO materials(title,path,content,content_hash,created_at,campaign,course_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (name, GUIDE, content, digest, study.now().isoformat(), CAMPAIGN,
                 course["id"] if course else None),
            )
            imported += 1
        if not args.dry_run:
            db.commit()

    print(f"\n{imported} imported, {skipped} too thin, of {len(sections)} section(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
