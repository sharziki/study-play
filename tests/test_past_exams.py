"""The past-exam importer, checked against a real Purdue paper.

The fixture is the genuine MA 26100 Exam 1 from Spring 2025, downloaded from
the department's public archive, together with its official answer key. Every
expected value here was read off the printed paper by eye.

This matters more than a usual parser test. A question imported wrong is not a
crash: it is a plausible-looking question with a subtly different expression,
carrying the authority of a real exam, which the learner will believe. These
tests exist to make that failure loud.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "importers"))

import mathpdf  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "import_past_exams", ROOT / "importers" / "import-past-exams.py"
)
past_exams = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(past_exams)

PAPER = (ROOT / "tests/fixtures/ma26100-e1-s2025.pdf").read_bytes()
KEY = (ROOT / "tests/fixtures/ma26100-e1-s2025-key.pdf").read_bytes()


class MathReconstructionTest(unittest.TestCase):
    """Typeset mathematics must survive extraction as the same mathematics."""

    @classmethod
    def setUpClass(cls):
        cls.lines = mathpdf.read_math_lines(PAPER)
        cls.text = "\n".join(cls.lines)

    def test_exponents_are_restored_rather_than_flattened(self):
        """`x²y²` must not read as `x2 y2`, which is a different expression."""
        self.assertIn(
            "f (x, y) = x^{2} y^{2} + 6x^{2} y − 2xy^{2} − 12xy",
            self.text,
        )

    def test_a_displayed_fraction_keeps_its_bar(self):
        """Question 1's limit is a quotient. Flattened, it is a sum."""
        self.assertIn(
            "\\frac{y^{4} + x^{2} y^{4} − 16 − 16x^{2}}{y^{2} − 4}",
            self.text,
        )

    def test_a_limit_operator_precedes_its_expression(self):
        """`lim` is set left of the fraction but reads after it by position."""
        line = next(line for line in self.lines if "\\lim_" in line)
        self.assertTrue(line.startswith("\\lim_{(x,y)→(1,−2)}"), line)
        self.assertIn("\\frac{", line)

    def test_an_inline_fraction_rejoins_the_line_it_belongs_to(self):
        """`x ln|y| + 1/z` is typeset across three lines and must come back."""
        self.assertIn("f (x, y, z) = x ln |y| + \\frac{1}{z}.", self.text)

    def test_a_radical_keeps_its_radicand(self):
        """√2 must not read as 2. That is a different number."""
        self.assertIn("\\sqrt{2}", self.text)
        self.assertIn("\\sqrt{5}", self.text)

    def test_the_cover_page_is_not_read_as_mathematics(self):
        """Centred title lines are stacked and centred but are not a fraction."""
        self.assertIn("MA 26100", self.lines)
        self.assertIn("EXAM 1", self.lines)
        self.assertNotIn("\\frac{MA 26100}{EXAM 1}", self.text)

    def test_answer_options_are_never_merged_into_each_other(self):
        """Consecutive options are narrow, close and centred, like a fraction."""
        for line in self.lines:
            if line.startswith("\\frac{"):
                self.assertNotRegex(line, r"^\\frac\{[A-F]\. ")


class FaithfulnessTest(unittest.TestCase):
    """What cannot be reconstructed must be refused, not guessed."""

    def test_a_bare_radical_sign_is_refused(self):
        self.assertFalse(mathpdf.is_faithful("A. 2 √"))
        self.assertTrue(mathpdf.is_faithful("A. \\sqrt{2}"))

    def test_a_fraction_over_a_relation_is_refused(self):
        """An equation ruled over the line below it is not a fraction."""
        self.assertFalse(mathpdf.is_faithful("\\frac{x 2 − y^{2} = 3}{16}"))

    def test_an_exponent_straight_after_a_relation_is_refused(self):
        """`κ(t) =^{1} 5` is a fraction that lost its bar, not a power."""
        self.assertFalse(mathpdf.is_faithful("κ(t) =^{1} 5"))

    def test_an_unpaired_partial_derivative_is_refused(self):
        self.assertFalse(mathpdf.is_faithful("∂f −4 ∂f ∂y = 6y − 2"))

    def test_ordinary_text_and_clean_mathematics_pass(self):
        self.assertTrue(mathpdf.is_faithful("Identify the surface x^{2} + 2x = −4."))
        self.assertTrue(mathpdf.is_faithful("The limit does not exist."))


class ExamParsingTest(unittest.TestCase):
    """Questions, options and the official key must line up exactly."""

    @classmethod
    def setUpClass(cls):
        lines = mathpdf.read_math_lines(PAPER)
        cls.questions = past_exams.parse_questions(lines)
        cls.key = past_exams.parse_key(mathpdf.read_math_lines(KEY))
        cls.candidates = past_exams.to_candidates(cls.questions, cls.key, "MA 26100 E1 Spring 2025")

    def test_the_official_key_is_read_in_full(self):
        """The paper has twelve questions, so the key has twelve answers."""
        self.assertEqual(len(self.key), 12)
        self.assertEqual(self.key[1], "E")
        self.assertEqual(self.key[2], "C")

    def test_every_imported_question_offers_the_six_options_A_to_F(self):
        """Purdue mathematics exams run A through F.

        Fewer than six means an option was swallowed by its neighbour, which
        is not a cosmetic loss: the key still names a letter, and that letter
        may be the one that vanished. Spring 2025 Q8 does exactly this - two
        stacked radicals merge B into C - so it must not be imported at all.
        """
        for candidate in self.candidates:
            self.assertEqual(len(candidate["choices"]), 6, candidate["number"])
        imported = {candidate["number"] for candidate in self.candidates}
        self.assertNotIn(8, imported)
        self.assertIn(1, imported)

    def test_the_key_letter_selects_the_option_the_paper_printed(self):
        """Question 1's answer is E, and E on the paper is 16."""
        first = next(c for c in self.candidates if c["number"] == 1)
        self.assertEqual(first["answer"], "16")
        self.assertEqual(first["choices"][first["correct_choice"]], "16")

    def test_a_candidate_is_grounded_in_its_own_wording(self):
        """The source quote is the question, so grounding is exact."""
        for candidate in self.candidates:
            self.assertEqual(candidate["source_quote"], candidate["prompt"])

    def test_every_prompt_marks_its_mathematics_for_rendering(self):
        """Undelimited LaTeX reaches the learner as literal braces."""
        marked = [c for c in self.candidates if "^{" in c["prompt"] or "\\frac" in c["prompt"]]
        self.assertTrue(marked)
        for candidate in marked:
            self.assertIn("\\(", candidate["prompt"])

    def test_no_candidate_carries_unreconstructed_mathematics(self):
        for candidate in self.candidates:
            self.assertTrue(mathpdf.is_faithful(candidate["prompt"]), candidate["prompt"])
            for choice in candidate["choices"]:
                self.assertTrue(mathpdf.is_faithful(choice), choice)

    def test_a_question_missing_its_expression_is_dropped(self):
        """A stem promising a limit with nothing to limit is unanswerable."""
        self.assertTrue(past_exams.is_missing_its_expression("The limit lim (x,y)→(0,0) is equal to"))
        self.assertFalse(past_exams.is_missing_its_expression(
            "Compute the limit \\lim_{(x,y)→(1,−2)} \\frac{a}{b}"
        ))

    def test_page_furniture_never_lands_inside_an_option(self):
        for candidate in self.candidates:
            for choice in candidate["choices"]:
                self.assertNotIn("intentionally blank", choice.lower())

    def test_nothing_is_imported_without_a_key(self):
        """A paper whose key cannot be read yields no questions at all."""
        self.assertEqual(past_exams.to_candidates(self.questions, {}, "no key"), [])


class VersionGridKeyTest(unittest.TestCase):
    """Some years print the key as a version-by-question grid."""

    GRID = [
        "EXAM 1 2 3 4 5 6 7 8 9 10 11 12",
        "11 E B A E B E E A A E A C",
        "12 B C D E E B A B E C D A",
    ]

    def test_an_ambiguous_grid_is_refused(self):
        """With several versions, the paper's own version decides. Guessing
        would be a coin toss repeated on every question."""
        self.assertEqual(past_exams.parse_version_grid(self.GRID), {})

    def test_a_single_version_grid_is_read(self):
        key = past_exams.parse_version_grid(self.GRID[:2])
        self.assertEqual(key[1], "E")
        self.assertEqual(key[12], "C")

    def test_a_plain_key_still_wins_over_the_grid_path(self):
        self.assertEqual(past_exams.parse_key(["1. E", "2. C"]), {1: "E", 2: "C"})
        self.assertEqual(past_exams.parse_key(["1 B", "2 A"]), {1: "B", 2: "A"})


if __name__ == "__main__":
    unittest.main()
