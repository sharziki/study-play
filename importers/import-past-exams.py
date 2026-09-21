#!/usr/bin/env python3
"""Import Purdue's public past-exam archive as questions.

Why this exists. The MA 26100 and CS 18000 banks were generated from the
official *catalog description* — one paragraph naming the syllabus topics —
because neither course publishes lecture notes outside Brightspace. That is
honest scaffolding, and it is also the weakest possible grounding: the learner
drills a course blurb while the exam asks something else entirely.

The Mathematics department publishes something far better and entirely public:

    https://www.math.purdue.edu/academic/courses/oldexams.php?course=MA26100

Two decades of real exam papers with official answer keys. These are the exact
instrument the learner will sit. A question taken from one is not a model's
guess at what MA 261 might ask; it is what MA 261 did ask, with the department's
own key deciding what is correct.

Design constraints this respects:

- **No model is involved.** The prompt is the exam's own wording, the options
  are the exam's own options, and the correct option is the department's
  published key. The app's grounding rule — every question carries a verbatim
  source quote — is satisfied trivially, because the source *is* the question.
- **A paper is skipped, not guessed at, when the key is missing or short.** An
  exam whose key cannot be matched question-for-question is not imported. A
  wrong key is worse than no question: it teaches the wrong answer.
- **Six options stay six.** Purdue maths exams run A through F.

Usage:

    python3 importers/import-past-exams.py MA26100 --exam e1 --years 4
    python3 importers/import-past-exams.py MA26100 --list

Requires `pdftotext` (poppler-utils), which is already how this repo reads PDFs.
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mathpdf  # noqa: E402
import study  # noqa: E402

ARCHIVE = "https://www.math.purdue.edu/academic/courses/oldexams.php?course={course}"
BASE = "https://www.math.purdue.edu/academic/courses/"
API = "http://127.0.0.1:4173/api/materials"

# Which Purdue course code each archive belongs to inside the app.
COURSE_CODES = {"MA26100": "MA 26100", "MA26500": "MA 26500", "MA16500": "MA 16500"}

# An exam paper's filename encodes paper, exam, and term: `26100e1-s2025.pdf`.
PAPER = re.compile(r"past-exams/(?P<prefix>(?:sol-|ans-)?)(?P<number>\d{5})(?P<exam>e\d|fe)-(?P<term>[sf]\d{4})\.pdf")

# A numbered question begins at the left margin: "7. Find the ...".
QUESTION_START = re.compile(r"^\s{0,3}(\d{1,2})\.\s+(.*)$")

# An option line: "   A. 12" or "   B. The limit does not exist."
OPTION = re.compile(r"^\s*([A-F])\.\s+(.*)$")

# A key line in an answer PDF: "1. E" or "1.E".
KEY_LINE = re.compile(r"^\s*(\d{1,2})\.\s*([A-F])\s*$")

# Some years drop the point: "1 B".
KEY_LOOSE = re.compile(r"^\s*(\d{1,2})\s+([A-F])\s*$")

# Page furniture that is not part of any question.
NOISE = re.compile(
    r"^\s*(\d{1,2}|MA\s*\d{5}|EXAM\s*\d|FINAL EXAM|Page \d+|"
    r"(Spring|Fall|Summer)\s+\d{4}|TEST/QUIZ NUMBER.*)\s*$",
    re.IGNORECASE,
)

# Page furniture that appears mid-line rather than on a line of its own, and so
# survives the NOISE filter by riding along with a wrapped option.
FURNITURE = re.compile(
    r"\(?\s*This page (?:is )?(?:left )?intentionally blank[^)]*\)?|"
    r"\(?\s*(?:You may use this|Use the back of).{0,60}(?:scratch|scrap)[^)]*\)?",
    re.IGNORECASE,
)


def fetch(url: str, binary: bool = False) -> bytes | str:
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read()
    return raw if binary else raw.decode(errors="replace")


def list_papers(course: str) -> list[dict]:
    """Every paper in the archive, newest first, with its key paired in."""
    html = fetch(ARCHIVE.format(course=course))
    papers: dict[tuple[str, str], dict] = {}
    for match in PAPER.finditer(html):
        term = match.group("term")
        exam = match.group("exam")
        entry = papers.setdefault((term, exam), {"term": term, "exam": exam, "paper": None, "key": None})
        path = match.group(0)
        if match.group("prefix"):
            # Prefer a worked solution over a bare answer list when both exist.
            if entry["key"] is None or path.startswith("past-exams/sol-"):
                entry["key"] = path
        else:
            entry["paper"] = path
    ordered = sorted(
        papers.values(),
        key=lambda item: (item["term"][1:], 0 if item["term"][0] == "f" else 1),
        reverse=True,
    )
    return ordered


def pdf_lines(url: str) -> list[str]:
    """An exam paper's lines, with its mathematics reconstructed.

    Plain `pdftotext` flattens typeset mathematics into a different expression
    than the one printed, so this reads geometry instead. See `mathpdf`.
    """
    return mathpdf.read_math_lines(fetch(url, binary=True))


def parse_key(lines: list[str]) -> dict[int, str]:
    """Question number to correct letter, from an answer or solution PDF.

    Purdue publishes keys in three shapes across the years, and all three are
    handled because a paper with an unreadable key is a paper thrown away:

    - one per line, `1. E`
    - one per line without the point, `1 B`
    - a **version grid**, where each row is one exam version and each column a
      question. The grid is the awkward one: several versions of the same exam
      are scrambled differently, so only the row matching the paper's own
      version number is its key. Reading the wrong row yields twelve confident
      wrong answers, which is why an ambiguous grid is refused entirely.
    """
    key: dict[int, str] = {}
    for line in lines:
        match = KEY_LINE.match(line) or KEY_LOOSE.match(line)
        if match:
            # A solution PDF may restate a number; the first statement wins.
            key.setdefault(int(match.group(1)), match.group(2))
    if key:
        return key
    return parse_version_grid(lines)


def parse_version_grid(lines: list[str]) -> dict[int, str]:
    """A key printed as a version-by-question grid.

    Returned only when exactly one version row is present. With several rows
    the paper's own version number decides which applies, and that number is
    not in the key document, so guessing would be a coin toss on every answer.
    """
    header = None
    rows = []
    for line in lines:
        cells = line.split()
        if not cells:
            continue
        if header is None:
            numbers = [cell for cell in cells if cell.isdigit()]
            if len(numbers) >= 8 and numbers == [str(n) for n in range(1, len(numbers) + 1)]:
                header = numbers
            continue
        letters = [cell for cell in cells if len(cell) == 1 and cell in "ABCDEF"]
        if len(letters) == len(header):
            rows.append(letters)
    if header is None or len(rows) != 1:
        return {}
    return {index: letter for index, letter in enumerate(rows[0], 1)}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", FURNITURE.sub(" ", text)).strip()


def parse_questions(lines: list[str]) -> list[dict]:
    """Split an exam paper into numbered questions with their lettered options.

    The layout is two-dimensional — displayed mathematics sits centred, options
    are indented — so this reads structurally rather than by regex over the
    whole document: a numbered line opens a question, lettered lines collect
    options, and the next numbered line closes it.
    """
    questions: list[dict] = []
    current: dict | None = None
    collecting_stem = False

    # The cover page carries its own numbered list - the exam policies, "1.
    # Students may not open the exam until instructed to do so." Read from the
    # top, that list claims numbers 1 through 6 before a single question
    # appears, and the real question 1 is then rejected as out of sequence.
    # Spring 2025's Exam 2 lost ten of its twelve questions that way.
    lines = lines[_first_question_line(lines):]

    for line in lines:
        option = OPTION.match(line)
        start = QUESTION_START.match(line)

        # An option letter only counts once a question is open, otherwise the
        # instruction pages' lettered lists would open phantom questions.
        if option and current is not None:
            current["options"].append([option.group(1), option.group(2)])
            collecting_stem = False
            continue

        if start and not (current and current["options"] and not collecting_stem and False):
            number = int(start.group(1))
            # Numbers restart per page in the exam-policy preamble; only accept
            # a number that continues the sequence, or opens it at 1.
            expected = (questions[-1]["number"] + 1) if questions else 1
            if current is not None and current["options"]:
                questions.append(current)
                expected = current["number"] + 1
                current = None
            if number == expected:
                current = {"number": number, "stem": [start.group(2)], "options": []}
                collecting_stem = True
                continue
            if current is not None and collecting_stem:
                current["stem"].append(line)
            continue

        if current is None:
            continue
        if NOISE.match(line):
            continue
        if collecting_stem:
            current["stem"].append(line)
        elif current["options"] and line.strip():
            # A wrapped option continues the last one - but only if it reads
            # like a continuation. Purdue sets the display mathematics for the
            # NEXT question above that question's number, so a centred formula
            # frequently lands after the previous question's final option. Glued
            # on, it becomes part of an answer that never contained it: Fall
            # 2024 option E read "lines" and ended up "lines \frac{2x^4 ...}",
            # while the question that owned the expression lost it and asked
            # about a limit with no expression at all. Both are wrong, and both
            # look like ordinary text.
            if _continues_option(current["options"][-1][1], line):
                current["options"][-1][1] += " " + line.strip()
            else:
                # It belongs to a question not yet open. Nothing here can say
                # which, so it is dropped rather than misattributed.
                continue

    if current is not None and current["options"]:
        questions.append(current)
    return [q for q in questions if len(q["options"]) >= study.MIN_CHOICES]


# A display line is mathematics standing alone: it carries structure and no
# sentence. An option that wraps continues a sentence instead.
DISPLAY_LINE = re.compile(r"\\frac|\\sqrt|\\lim|\^\{|_\{|[\u222b\u2211\u2192]")


def _continues_option(existing: str, line: str) -> bool:
    """Whether `line` is the rest of an option rather than a stray display.

    A wrapped option is prose that ran out of width, so the text before it does
    not look finished. A displayed formula is self-contained mathematics that
    the typesetter centred between two questions.
    """
    if DISPLAY_LINE.search(line) and not DISPLAY_LINE.search(existing):
        return False
    # An option that already ends in a full stop is complete.
    return not existing.rstrip().endswith(".")


# The policy list is prose instructions; a question is a task. The policy list
# also always precedes the questions, so the last numbered "1." wins.
POLICY_WORDS = re.compile(
    r"\b(?:students?|proctors?|TAs?|lecturers?|exam room|writing instruments|"
    r"academic dishonesty|Dean of Students)\b",
    re.IGNORECASE,
)


def _first_question_line(lines: list[str]) -> int:
    """Where the real questions begin, past any numbered policy list."""
    best = 0
    for index, line in enumerate(lines):
        match = QUESTION_START.match(line)
        if match and match.group(1) == "1" and not POLICY_WORDS.search(line):
            best = index
    return best


def to_candidates(questions: list[dict], key: dict[int, str], label: str) -> list[dict]:
    """Turn parsed questions plus the official key into savable candidates."""
    candidates = []
    for question in questions:
        letter = key.get(question["number"])
        if letter is None:
            continue
        options = [(letter_, clean(body)) for letter_, body in question["options"]]
        options = [(letter_, body) for letter_, body in options if body]
        letters = [letter_ for letter_, _ in options]
        bodies = [body for _, body in options]
        if letter not in letters or len(bodies) != len(set(bodies)):
            continue
        # A missing letter means an option was swallowed by its neighbour, so
        # the options no longer are what the paper offered. On Spring 2025 Q8 a
        # stacked radical merged B and C, leaving five options whose letters ran
        # A, B, D, E, F - and the key still pointed at a letter that may have
        # been the one that vanished.
        if letters != list("ABCDEF"[: len(letters)]):
            continue
        stem_text = clean(" ".join(question["stem"]))
        # One unreadable option condemns the whole question. Dropping just the
        # bad option would silently change which answers are available, and the
        # key still points at a letter that may no longer be there.
        if not all(mathpdf.is_faithful(part) for part in (stem_text, *bodies)):
            continue
        # A question whose displayed expression was set between two questions
        # and therefore dropped still reads as a sentence: "The limit ... is
        # equal to", with nothing to take the limit of. It is unanswerable, and
        # unlike a mangled formula it carries no visible damage, so it has to be
        # recognised by what it is missing.
        if is_missing_its_expression(stem_text):
            continue
        if not study.MIN_CHOICES <= len(bodies) <= study.MAX_CHOICES:
            continue
        stem = stem_text
        if len(stem) < 24:
            continue
        index = letters.index(letter)
        # Mark the mathematics before storing. The reader emits LaTeX
        # fragments, and the app renders only what sits inside \( ... \), so
        # an unmarked question shows the learner literal braces.
        stem = mathpdf.wrap_math(stem)
        bodies = [mathpdf.wrap_math(body) for body in bodies]
        candidates.append({
            "number": question["number"],
            "prompt": stem,
            "answer": bodies[index],
            # No reasoning is invented here. The department published which
            # option is correct, not why, and asserting a derivation the source
            # does not contain is exactly the failure this repo forbids.
            "explanation": f"Official Purdue answer key for {label}: {letter}.",
            "topic": f"{label} Q{question['number']}",
            "kind": "recall",
            "difficulty": 3,
            # The quote is the question. Both carry the delimiters, because the
            # material stores exactly what the learner is shown; a quote in a
            # different notation from the material fails the grounding check
            # that every stored question must pass.
            "source_quote": stem,
            "choices": bodies,
            "correct_choice": index,
        })
    return candidates


# A stem promising an expression it never shows. Each of these reads as a
# complete sentence, which is exactly why they need naming explicitly.
TRUNCATED_STEM = re.compile(
    "|".join([
        r"\blim\b(?!.*(?:\\frac|\\sqrt|[-+=/^]))",
        r"\b(?:compute|find|evaluate)\b[^.]{0,40}\b(?:d[a-z]\s+d[a-z]|\u2202)\b",
        r"\bis equal to\s*$",
        r"\bthe (?:limit|integral|derivative)\b[^.]{0,30}$",
    ]),
    re.IGNORECASE,
)


def is_missing_its_expression(stem: str) -> bool:
    """Whether a stem refers to mathematics that is not present in it."""
    return bool(TRUNCATED_STEM.search(stem))


MATH_SPAN = re.compile(r"\\\\\((.+?)\\\\\)", re.S)
KATEX = Path(__file__).resolve().parents[1] / "tools" / "katex_validate.js"


def katex_failures(candidates: list[dict]) -> set[str]:
    """Every delimited expression the app's own KaTeX build cannot render.

    "The reader produced LaTeX" and "the learner sees mathematics" are
    different claims, and only the second one matters. This checks the second
    with the exact KaTeX the app ships, so a question that would render as a
    red error string never reaches the bank.
    """
    expressions = sorted({
        expression
        for candidate in candidates
        for field in (candidate["prompt"], *candidate["choices"])
        for expression in MATH_SPAN.findall(field)
    })
    if not expressions:
        return set()
    result = subprocess.run(
        ["node", str(KATEX)], input=json.dumps(expressions), capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        return set()
    try:
        return {failure["expression"] for failure in json.loads(result.stdout or "[]")}
    except json.JSONDecodeError:
        # The validator itself failed. Refusing everything is the safe reading.
        return set(expressions)


def drop_unrenderable(candidates: list[dict]) -> list[dict]:
    broken = katex_failures(candidates)
    if not broken:
        return candidates
    kept = []
    for candidate in candidates:
        fields = (candidate["prompt"], *candidate["choices"])
        if any(expression in broken for field in fields for expression in MATH_SPAN.findall(field)):
            continue
        kept.append(candidate)
    return kept


def build_material(label: str, candidates: list[dict], url: str) -> str:
    """The material text an imported paper is grounded in: the paper itself."""
    lines = [
        f"# {label}",
        "",
        f"Source: {url}",
        "",
        "Verbatim transcription of a publicly archived Purdue exam paper. The",
        "correct option on each question is the department's own published key.",
        "",
    ]
    for candidate in candidates:
        lines.append(f"## Question {candidate['number']}")
        lines.append("")
        lines.append(candidate["prompt"])
        lines.append("")
        for letter, body in zip("ABCDEF", candidate["choices"]):
            lines.append(f"- {letter}. {body}")
        lines.append("")
    return "\n".join(lines)


def post_material(title: str, content: str, campaign: str) -> int:
    body = json.dumps({"title": title, "content": content, "campaign": campaign}).encode()
    request = urllib.request.Request(API, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode())["material_id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("course", help="archive code, e.g. MA26100")
    parser.add_argument("--exam", default="e1", help="e1, e2, or fe (default %(default)s)")
    parser.add_argument("--years", type=int, default=4, help="how many recent papers (default %(default)s)")
    parser.add_argument("--list", action="store_true", help="show the archive and stop")
    parser.add_argument("--dry-run", action="store_true", help="parse and report without importing")
    args = parser.parse_args()

    campaign = COURSE_CODES.get(args.course)
    if campaign is None and not args.list:
        print(f"Unknown course {args.course!r}. Known: {', '.join(COURSE_CODES)}")
        return 1

    papers = list_papers(args.course)
    if args.list:
        for paper in papers:
            print(f"{paper['term']} {paper['exam']}  paper={bool(paper['paper'])} key={bool(paper['key'])}")
        return 0

    usable = [p for p in papers if p["exam"] == args.exam and p["paper"] and p["key"]][: args.years]
    if not usable:
        print(f"No {args.exam} paper with a key found for {args.course}.")
        return 1

    total = 0
    for paper in usable:
        term = paper["term"]
        season = "Fall" if term[0] == "f" else "Spring"
        label = f"{campaign} {args.exam.upper()} {season} {term[1:]}"
        url = BASE + paper["paper"]
        try:
            questions = parse_questions(pdf_lines(url))
            key = parse_key(pdf_lines(BASE + paper["key"]))
        except Exception as error:  # noqa: BLE001
            print(f"  SKIP {label}: {error}")
            continue

        candidates = drop_unrenderable(to_candidates(questions, key, label))
        if not candidates:
            print(f"  SKIP {label}: parsed {len(questions)} question(s), {len(key)} key entr(ies), 0 usable")
            continue
        if args.dry_run:
            print(f"  {label}: {len(candidates)} question(s) ready")
            print(f"      e.g. {candidates[0]['prompt'][:90]}")
            print(f"      key {candidates[0]['answer'][:60]}")
            total += len(candidates)
            continue

        material_id = post_material(label, build_material(label, candidates, url), campaign)
        with study.connect() as db:
            material = db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
            saved = study.save_questions(db, material, candidates)
            db.commit()
        print(f"  {label}: saved {saved}/{len(candidates)} into material #{material_id}")
        total += saved

    print(f"\n{total} question(s) from {len(usable)} paper(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
