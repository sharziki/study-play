#!/usr/bin/env python3
"""Read a mathematics PDF as mathematics, not as flattened text.

`pdftotext` throws away the one thing that makes typeset mathematics readable:
vertical position and glyph size. An exponent is not a separate token sitting
beside its base, and a fraction is not two lines that happen to be stacked.
Running a Purdue exam paper through plain extraction turns

    y^4 + x^2 y^4 - 16 - 16x^2
    ---------------------------
             y^2 - 4

into `y 4 + x2 y 4 − 16 − 16x2 y2 − 4`, which is not merely ugly. It is a
*different expression*, and a learner drilled on it is being taught something
false. That is worse than having no question at all.

So this module reads `pdftotext -bbox-layout`, which keeps every word's box,
and recovers the structure the layout encodes:

- **Superscripts** — a run whose glyphs are meaningfully shorter than the
  surrounding body text and whose box sits higher becomes `^{...}`.
- **Fractions** — a horizontal rule in the PDF is drawn, not written, so it
  does not appear as a word at all. What does appear is two groups of words
  centred on a common x-range with a gap between them; that pairing becomes
  `\\frac{...}{...}`.
- **Reading order** — words are grouped into lines by vertical overlap rather
  than by exact y, because a line containing both body text and a superscript
  has no single y value.

The output is LaTeX-ish text the app already knows how to render, since the
bank is typeset with KaTeX.

Only what can be recovered with confidence is reconstructed. Anything
ambiguous is left as the plain reading, because a wrong repair is invisible
and a missing one is merely plain.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

# A glyph run this much shorter than the line's body height is a superscript.
# Measured on Purdue exam papers: body 10.62pt, exponents 7.08pt, a ratio of
# 0.67. The threshold sits above that and below any plausible body variation.
SUPERSCRIPT_HEIGHT_RATIO = 0.85

# How far above the body baseline a superscript sits, as a fraction of body
# height. A true exponent is raised; a smaller font on the same baseline is
# not an exponent, it is just smaller text.
SUPERSCRIPT_RISE_RATIO = 0.12

# Two words belong to the same line when their boxes overlap vertically by at
# least this fraction of the shorter box.
LINE_OVERLAP_RATIO = 0.35

# Numerator and denominator of one fraction are centred on nearly the same x.
FRACTION_CENTRE_TOLERANCE = 24.0

# ... and sit within this many points of each other vertically.
FRACTION_MAX_GAP = 26.0

# Two lines sharing a left margin this closely are a list, not a fraction. This
# is what separates a genuine stacked fraction from two consecutive multiple
# choice options, which are also centred-ish, close, and narrow, and which the
# first version of this happily welded into `\frac{A. ...}{B. ...}`.
SHARED_MARGIN_TOLERANCE = 2.0

# An option line opens with its letter. Such a line is never part of a fraction.
OPTION_START = re.compile(r"^\s*[A-F]\.\s")

# An inline fraction's numerator and denominator are single short runs sitting
# directly above and below the body line, as in `x ln|y| + 1/z`.
INLINE_PART_MAX_WIDTH = 30.0

# A stacked fraction's parts are narrower than a paragraph line.
STACKED_PART_MAX_WIDTH = 260.0

# How many lines past a numerator its denominator may sit. A displayed limit
# interposes its operator and subscript, so the pair is not always adjacent.
STACK_SEARCH_AHEAD = 3

# A radical sign is typeset on its own line above its radicand, because the
# overbar is a drawn rule. The sign alone on a line is the giveaway.
RADICAL_SIGN = "\u221a"

# Words further apart than this are not in the same run. Prose word spacing on
# these papers is around 4pt, so a gap this wide only happens where display
# mathematics places two separate pieces side by side - the subscript under a
# limit operator and, well to its right, the denominator of the fraction being
# limited. Grouped as one line those read as a single flat expression.
DISPLAY_GAP = 20.0


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def centre(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Line:
    words: list[Word]

    @property
    def y0(self) -> float:
        return min(word.y0 for word in self.words)

    @property
    def y1(self) -> float:
        return max(word.y1 for word in self.words)

    @property
    def x0(self) -> float:
        return min(word.x0 for word in self.words)

    @property
    def x1(self) -> float:
        return max(word.x1 for word in self.words)

    @property
    def centre(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def body_height(self) -> float:
        """The tallest glyph run, taken as this line's body text size."""
        return max(word.height for word in self.words)


WORD_RE = re.compile(
    r'<word xMin="([\d.eE+-]+)" yMin="([\d.eE+-]+)" '
    r'xMax="([\d.eE+-]+)" yMax="([\d.eE+-]+)">([^<]*)</word>'
)
PAGE_RE = re.compile(r"<page[^>]*>(.*?)</page>", re.S)


def unescape(text: str) -> str:
    return (
        text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        .replace("&quot;", '"').replace("&apos;", "'")
    )


def pdf_pages(data: bytes) -> list[list[Word]]:
    """Every page's words, with boxes, in document order."""
    result = subprocess.run(
        ["pdftotext", "-bbox-layout", "-", "-"], input=data, capture_output=True, timeout=180
    )
    if result.returncode != 0:
        raise RuntimeError("pdftotext -bbox-layout failed")
    xml = result.stdout.decode(errors="replace")
    pages = []
    for page in PAGE_RE.findall(xml):
        words = [
            Word(float(x0), float(y0), float(x1), float(y1), unescape(text))
            for x0, y0, x1, y1, text in WORD_RE.findall(page)
            if text.strip()
        ]
        pages.append(words)
    return pages


def group_lines(words: list[Word]) -> list[Line]:
    """Group words into visual lines by vertical overlap.

    Grouping by exact y fails on any line containing an exponent, because the
    exponent's box starts higher than the body text's. Overlap tolerates that
    while still separating genuinely different lines.
    """
    lines: list[Line] = []
    for word in sorted(words, key=lambda w: (round(w.y0, 1), w.x0)):
        placed = False
        for line in lines:
            overlap = min(line.y1, word.y1) - max(line.y0, word.y0)
            if overlap >= LINE_OVERLAP_RATIO * min(line.y1 - line.y0, word.height):
                line.words.append(word)
                placed = True
                break
        if not placed:
            lines.append(Line([word]))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    lines.sort(key=lambda line: line.y0)
    return lines


def split_display_runs(lines: list[Line]) -> list[Line]:
    """Break a line wherever a display gap shows two separate runs.

    Vertical grouping alone puts `lim`, its subscript, and the denominator of
    the limited fraction on one line, because they do overlap vertically. They
    are not one run: the subscript belongs under the operator and the
    denominator belongs under the numerator, several centimetres to the right.
    Splitting on the gap lets each find its real partner.
    """
    out: list[Line] = []
    for line in lines:
        run = [line.words[0]]
        for word in line.words[1:]:
            if word.x0 - run[-1].x1 > DISPLAY_GAP:
                out.append(Line(run))
                run = [word]
            else:
                run.append(word)
        out.append(Line(run))
    out.sort(key=lambda item: (item.y0, item.x0))
    return out


def render_line(line: Line) -> str:
    """One visual line as text, with superscripts restored."""
    body = line.body_height
    out: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            out.append("^{" + "".join(pending) + "}")
            pending.clear()

    for word in line.words:
        raised = (line.y0 + body) - (word.y0 + word.height)
        is_superscript = (
            word.height < SUPERSCRIPT_HEIGHT_RATIO * body
            and raised > SUPERSCRIPT_RISE_RATIO * body
            and out  # nothing can be an exponent of nothing
        )
        if is_superscript:
            pending.append(word.text)
            continue
        flush()
        out.append(word.text)
    flush()

    text = ""
    for index, piece in enumerate(out):
        if index and not piece.startswith("^{"):
            text += " "
        text += piece
    return text.strip()


def merge_fractions(lines: list[Line]) -> list[str]:
    """Rebuild the fractions whose bars the text layer threw away.

    A fraction's horizontal rule is a drawn rule, so it never appears as a
    word. What survives is geometry, and two shapes matter:

    **Stacked** — numerator and denominator on their own lines, centred on a
    common x, as in a displayed limit.

    **Inline** — a one-token numerator and denominator straddling the body
    line, as in `f(x,y,z) = x ln|y| + 1/z`. Read in document order those come
    out as three lines reading `1`, `f (x, y, z) = x ln |y| + .`, and `z`, so
    the fraction has fallen out of the expression altogether.

    Two things disqualify a pair no matter how well it scores geometrically.
    A line opening with an option letter belongs to the answer list, and two
    lines sharing a left margin are a list rather than a stack. Without those
    rules a run of multiple-choice options welds into nonsense fractions,
    which is exactly what the first version of this did.
    """
    rendered = [render_line(line) for line in lines]
    out: list[str] = []
    consumed: set[int] = set()
    index = 0

    while index < len(lines):
        if index in consumed:
            index += 1
            continue
        radicand = _radical(lines, rendered, index)
        if radicand is not None:
            out.append(radicand)
            index += 2
            continue
        if _inline_fraction(lines, index):
            top, body, bottom = rendered[index], rendered[index + 1], rendered[index + 2]
            fraction = f"\\frac{{{top}}}{{{bottom}}}"
            # The body line keeps the punctuation that followed the fraction in
            # print, so the fraction belongs just before it rather than after.
            merged = f"{body[:-1].rstrip()} {fraction}." if body.endswith(".") else f"{body} {fraction}"
            out.append(merged)
            index += 3
            continue
        partner = _stacked_partner(lines, rendered, index, consumed)
        if partner is not None:
            out.append(f"\\frac{{{rendered[index]}}}{{{rendered[partner]}}}")
            consumed.add(partner)
            index += 1
            continue
        out.append(rendered[index])
        index += 1
    return out


MATH_TOKEN = re.compile(
    r"[=+\u2212<>]|\\frac|\\sqrt|\^\{|_\{|\blim\b|\bint\b|[\u222b\u2211\u2192\u27e8\u27e9]"
)


def _is_mathematical(text: str) -> bool:
    """Whether a run carries a sign that it is an expression, not a caption.

    Centred title lines on an exam's cover page are narrow, stacked, and
    centred on each other, so pure geometry happily rules `MA 26100` over
    `EXAM 1`. A fraction is made of expressions; requiring at least one side to
    show an operator, an exponent, or a radical keeps the cover page intact.
    """
    return bool(MATH_TOKEN.search(text))


def _stacked_partner(
    lines: list[Line], rendered: list[str], index: int, consumed: set[int]
) -> int | None:
    """The denominator belonging to the numerator at `index`, if there is one.

    Not necessarily the next line. A displayed limit puts `lim` and its
    subscript *between* the numerator and the denominator, because the operator
    is tall and the fraction is set to its right. Pairing strictly with the next
    line therefore rules the operator over the numerator and leaves the real
    denominator stranded, which is how `lim` ended up inside a fraction bar.
    So the search looks a short way ahead and takes the first line that is
    genuinely centred beneath this one.
    """
    for candidate in range(index + 1, min(index + 1 + STACK_SEARCH_AHEAD, len(lines))):
        if candidate not in consumed and _stacked_fraction(lines, rendered, index, candidate):
            return candidate
    return None


def _stacked_fraction(lines: list[Line], rendered: list[str], index: int, below: int) -> bool:
    line, other = lines[index], lines[below]
    if not rendered[index] or not rendered[below]:
        return False
    if OPTION_START.match(rendered[index]) or OPTION_START.match(rendered[below]):
        return False
    if abs(line.x0 - other.x0) <= SHARED_MARGIN_TOLERANCE:
        return False
    if not (_is_mathematical(rendered[index]) or _is_mathematical(rendered[below])):
        return False
    return (
        abs(line.centre - other.centre) <= FRACTION_CENTRE_TOLERANCE
        and 0 <= _centre_y(other) - _centre_y(line) <= FRACTION_MAX_GAP
        # A fraction's parts are narrow. Two full-width paragraph lines are
        # also centred and close; width is what separates them.
        and (line.x1 - line.x0) < STACKED_PART_MAX_WIDTH
        and (other.x1 - other.x0) < STACKED_PART_MAX_WIDTH
    )


def _radical(lines: list[Line], rendered: list[str], index: int) -> str | None:
    """A lone radical sign plus the line beneath it, folded into \\sqrt{}.

    The sign and its overbar are drawn separately from the radicand, so the
    sign lands on its own line directly above. Read in order that gives
    `√` then `A. 2`, which reads as the option being 2 when it is √2 — a
    different number, and the wrong answer to memorise.
    """
    if index + 1 >= len(lines) or rendered[index].strip() != RADICAL_SIGN:
        return None
    below = lines[index + 1]
    sign = lines[index]
    # The radicand begins under the sign: the sign's left edge sits at or after
    # the line's start, and the two are vertically adjacent.
    if not 0 <= _centre_y(below) - _centre_y(sign) <= FRACTION_MAX_GAP:
        return None
    text = rendered[index + 1]
    option = OPTION_START.match(text)
    prefix, body = (text[: option.end()], text[option.end():]) if option else ("", text)
    if not body.strip():
        return None
    # Only the part of the line actually under the radical is inside it. On an
    # option line that is the value; the option letter stays outside.
    return f"{prefix}\\sqrt{{{body.strip()}}}"


def _centre_y(line: Line) -> float:
    return (line.y0 + line.y1) / 2


def _inline_fraction(lines: list[Line], index: int) -> bool:
    if index + 2 >= len(lines):
        return False
    top, middle, bottom = lines[index], lines[index + 1], lines[index + 2]
    return (
        (top.x1 - top.x0) <= INLINE_PART_MAX_WIDTH
        and (bottom.x1 - bottom.x0) <= INLINE_PART_MAX_WIDTH
        and abs(top.centre - bottom.centre) <= FRACTION_CENTRE_TOLERANCE
        # The stack sits at the right-hand end of the body line, where the
        # expression it belongs to trails off.
        and top.centre >= middle.x1 - FRACTION_CENTRE_TOLERANCE
        # Ordering is by vertical centre, not by gap. A raised numerator's box
        # overlaps the body line's by a few points, so requiring a non-negative
        # gap rejects exactly the fractions this is meant to catch.
        and _centre_y(top) < _centre_y(middle) < _centre_y(bottom)
        and _centre_y(bottom) - _centre_y(top) <= FRACTION_MAX_GAP
        and (middle.x1 - middle.x0) > (top.x1 - top.x0)
    )


# `lim` with its subscript, as rendered once the display runs are split. The
# subscript is set below the operator, so it reads first.
LIMIT_RUN = re.compile(r"^(?P<sub>\(?[^()]*\)?\s*\u2192\s*\([^()]*\))\s+lim$")


def reorder_limits(lines: list[str]) -> list[str]:
    """Put a limit operator in front of the expression it applies to.

    `lim` is typeset with its subscript underneath and the limited expression
    to its right, so reading by position yields the subscript, then `lim`, then
    - on an earlier line, because it is taller - the expression. Written out
    that is `(x,y)→(1,−2) lim` sitting after a fraction it governs, which is
    not the limit at all.
    """
    out = list(lines)
    for index, line in enumerate(out):
        match = LIMIT_RUN.match(line.strip())
        if not match or index == 0:
            continue
        target = index - 1
        if not out[target].strip():
            continue
        out[target] = f"\\lim_{{{match.group('sub')}}} {out[target]}"
        out[index] = ""
    return [line for line in out if line.strip()]


def read_math_lines(data: bytes) -> list[str]:
    """Every line of a PDF, with exponents, fractions and radicals restored."""
    lines: list[str] = []
    for words in pdf_pages(data):
        if not words:
            continue
        lines.extend(merge_fractions(split_display_runs(group_lines(words))))
    return reorder_limits(lines)



# Wreckage left by a construction this module does not reconstruct: a bare
# radical sign with nothing under it, an empty fraction part, a radical trapped
# inside one, or a private-use glyph from a maths font's extensible delimiters.
UNRECONSTRUCTED = re.compile(
    "|".join([
        # A radical sign with nothing under it.
        RADICAL_SIGN + r"(?![A-Za-z0-9({\[])",
        # An empty fraction part, or one holding only an operator. A fraction
        # over `=` is not a fraction; it is a row of separate equations that
        # geometry mistook for a stack, and the reading is nonsense.
        r"\\frac\{\s*\}",
        r"\\frac\{\s*[=+\u2212<>/]\s*\}",
        # A fraction whose numerator contains a relation is not a fraction. An
        # equation was ruled over the line below it, so both halves are wrong.
        r"\\frac\{[^=]*=[^{}]*\}\{",
        # An exponent immediately after a relation, as in `= ^{1} 5`, is a
        # fraction whose bar was lost: the 1 was the numerator, not a power.
        r"[=+\u2212<>]\s*\^\{",
        # ... and the same shape written the other way round, `13^{1}`, where a
        # trailing lone digit exponent follows a complete number.
        r"\d\s*\^\{\d\}\s*$",
        r"\\frac\{[^{}]*" + RADICAL_SIGN + r"[^{}]*\}",
        # A partial-derivative symbol that never became a derivative. These are
        # always set as a fraction, so a bare pair outside one means the stack
        # was not recovered and the operator has lost its variable.
        r"\u2202(?![^{}]*\}\{)",
        # Private-use glyphs from a maths font's extensible delimiters.
        r"[\ue000-\uf8ff\x00-\x08\x0e-\x1f]",
    ])
)


def is_faithful(text: str) -> bool:
    """Whether a reconstructed line can be trusted as the mathematics it came from.

    Some layouts are not recoverable from geometry alone: a coefficient beside a
    stacked radical, a matrix, a deeply nested fraction. Heuristics can always be
    piled higher, but a wrong reconstruction is silent, and a silently wrong
    question teaches a false fact under the authority of a real exam paper. So
    anything still carrying the marks of an unreconstructed construction is
    refused rather than guessed at.

    A question that never imports costs nothing. A question that imports wrong
    costs an exam mark and the learner's trust in every other question.
    """
    return not UNRECONSTRUCTED.search(text)


def radical_count(text: str) -> int:
    """How many radicals a piece of text contains, reconstructed or not."""
    return text.count(RADICAL_SIGN) + text.count("\\sqrt{")
