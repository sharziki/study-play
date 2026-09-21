#!/usr/bin/env python3
"""Sync MA 261's quiz and midterm scope from the department's own calendar.

Why this exists. The app knew MA 261 had "an exam" and showed one countdown.
The course actually runs a recitation quiz almost every Tuesday over three
named lessons, plus two midterms over sixteen lessons each, plus a final. Those
are different pieces of work: the quiz is narrow and imminent, the midterm is
broad and still worth starting. Collapsing them to whichever is nearest hides
the midterm until the quiz has passed, which is exactly when it is too late to
have been revising for it.

Source, first-party and public:

    https://www.math.purdue.edu/academic/courses/semester/202710/ma26100/Schedule261.pages.pdf

The relative PDF links only resolve against the redirected semester path;
fetching them against `/ma261/` silently returns HTML rather than a PDF.

The calendar is a week grid, five day-columns wide, and `pdftotext -layout`
interleaves the columns so a quiz in the Tuesday column reads as though it
belonged to Monday's lesson. Column x-position is stable across every page, so
this reads words by geometry and rebuilds each column separately. That is the
same reason `importers/mathpdf.py` exists, and it reuses its reader.

What it writes: each quiz's date, its lesson numbers, and the textbook sections
those lessons cover, as the exam row's `scope_json`. The scheduler then serves
a quiz's own sections when the quiz is what is imminent.
"""

import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "importers"))

import mathpdf  # noqa: E402
import study  # noqa: E402

CALENDAR = (
    "https://www.math.purdue.edu/academic/courses/semester/202710/ma26100/"
    "Schedule261.pages.pdf"
)
COURSE = "MA 26100"

# Day columns, by the x where each begins. Stable on every page of the grid.
COLUMNS = [(100, 190), (190, 275), (275, 362), (362, 448), (448, 540)]

# Words within this many points vertically belong to the same grid row.
ROW_HEIGHT = 12

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

QUIZ = re.compile(r"Quiz\s+(\d+)[^\n]*\n?\(Lessons?\s+([0-9,\s]+(?:and\s*\d+)?)\)")
LESSON = re.compile(r"Lesson\s+(\d+)\s*\n([^\n]*)")
SECTION = re.compile(r"\d{2}\.\d(?:-\d{2}\.\d)?")
DATE = re.compile(r"([A-Z][a-z]{2,3})\.?\s+(\d{1,2})\s*$")


def column_of(x: float) -> int | None:
    for index, (start, end) in enumerate(COLUMNS):
        if start <= x < end:
            return index
    return None


def read_columns(data: bytes) -> list[dict[int, str]]:
    """Each page's five day-columns, read top to bottom, as text.

    Reading the page as flowed text interleaves the columns, so a Tuesday quiz
    lands beside a Monday lesson and every "(Lessons ...)" attaches to the
    wrong thing.
    """
    pages = []
    for words in mathpdf.pdf_pages(data):
        cells: dict[tuple[int, int], list[tuple[float, str]]] = {}
        for word in words:
            column = column_of(word.x0)
            if column is None:
                continue
            cells.setdefault((column, round(word.y0 / ROW_HEIGHT)), []).append((word.x0, word.text))
        rows: dict[int, list[str]] = {}
        for (column, _), items in sorted(cells.items()):
            rows.setdefault(column, []).append(" ".join(text for _, text in sorted(items)))
        pages.append({column: "\n".join(lines) for column, lines in rows.items()})
    return pages


def parse(data: bytes) -> tuple[dict[int, list[int]], dict[int, list[str]], dict[int, date]]:
    """Quiz to lessons, lesson to textbook sections, and quiz to its date."""
    quizzes: dict[int, list[int]] = {}
    lessons: dict[int, list[str]] = {}
    quiz_dates: dict[int, date] = {}
    year = date.today().year

    for page in read_columns(data):
        for column, blob in page.items():
            for match in QUIZ.finditer(blob):
                number = int(match.group(1))
                quizzes[number] = [int(n) for n in re.findall(r"\d+", match.group(2))]
                # The date heading sits above the quiz in the same column.
                heading = blob[: match.start()].strip().splitlines()
                for line in reversed(heading[-4:]):
                    found = DATE.search(line.strip())
                    if found and found.group(1)[:3].lower() in MONTHS:
                        quiz_dates[number] = date(
                            year, MONTHS[found.group(1)[:3].lower()], int(found.group(2))
                        )
                        break
            for match in LESSON.finditer(blob):
                sections = SECTION.findall(match.group(2))
                if sections:
                    lessons.setdefault(int(match.group(1)), []).extend(sections)
    return quizzes, lessons, quiz_dates


def expand(sections: list[str]) -> list[str]:
    """`13.1-13.4` as the four sections it names."""
    out: list[str] = []
    for section in sections:
        if "-" not in section:
            out.append(section)
            continue
        start, end = section.split("-")
        chapter, first = start.split(".")
        _, last = end.split(".")
        out.extend(f"{chapter}.{n}" for n in range(int(first), int(last) + 1))
    return out


def scope_for(lesson_numbers: list[int], lessons: dict[int, list[str]]) -> list[str]:
    seen: list[str] = []
    for number in lesson_numbers:
        for section in expand(lessons.get(number, [])):
            if section not in seen:
                seen.append(section)
    return seen


def main() -> int:
    data = urllib.request.urlopen(CALENDAR, timeout=60).read()
    if not data.startswith(b"%PDF"):
        print("The calendar URL did not return a PDF. Check the semester path.")
        return 1

    quizzes, lessons, quiz_dates = parse(data)
    if not quizzes:
        print("No quizzes parsed; the calendar layout may have changed.")
        return 1

    written = 0
    with study.connect() as db:
        course = db.execute("SELECT id FROM courses WHERE code=?", (COURSE,)).fetchone()
        if course is None:
            print(f"{COURSE} is not a course in this database.")
            return 1

        for number, lesson_numbers in sorted(quizzes.items()):
            when = quiz_dates.get(number)
            if when is None:
                print(f"  Quiz {number}: no date found, skipped")
                continue
            scope = scope_for(lesson_numbers, lessons)
            spread = ", ".join(str(n) for n in lesson_numbers)
            title = f"Quiz {number} (Lessons {spread})"
            db.execute(
                """INSERT INTO exams(course_id,title,exam_date,weight,scope_json,kind,created_at)
                   VALUES (?,?,?,?,?,'quiz',?)
                   ON CONFLICT(course_id,title) DO UPDATE SET
                     exam_date=excluded.exam_date, scope_json=excluded.scope_json, kind='quiz'""",
                (course["id"], title, when.isoformat(), 1.0, json.dumps(scope), study.now().isoformat()),
            )
            written += 1
            print(f"  Quiz {number} · {when} · lessons {spread} · {' '.join(scope)}")

        # The midterms cover a lesson range the ground rules state, and the
        # final covers the course. Their scope is every section in range.
        for title, low, high, when, kind in (
            ("Midterm 1 (Lessons 1-16)", 1, 16, "2026-10-05", "exam"),
            ("Midterm 2 (Lessons 17-31)", 17, 31, "2026-11-18", "exam"),
            ("Final exam", 1, 40, "2026-12-15", "final"),
        ):
            scope = scope_for(list(range(low, high + 1)), lessons)
            db.execute(
                """INSERT INTO exams(course_id,title,exam_date,weight,scope_json,kind,created_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(course_id,title) DO UPDATE SET
                     exam_date=excluded.exam_date, scope_json=excluded.scope_json, kind=excluded.kind""",
                (course["id"], title, when, 2.0 if kind == "final" else 2.0,
                 json.dumps(scope), kind, study.now().isoformat()),
            )
            written += 1
            print(f"  {title} · {when} · {len(scope)} section(s)")

        # The generic rows the registrar sync wrote are now superseded by the
        # titled ones, and leaving both double-counts the same sitting.
        db.execute(
            """DELETE FROM exams WHERE course_id=? AND title IN
               ('Evening exam 2026-10-05','Evening exam 2026-11-18','Final exam 2026-12-15')""",
            (course["id"],),
        )
        db.commit()

    print(f"\n{written} assessment(s) synced for {COURSE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
