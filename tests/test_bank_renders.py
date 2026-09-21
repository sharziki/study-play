"""Every expression in the live question bank must render.

`repair_math` producing LaTeX and KaTeX being able to typeset it are different
claims, and only the second is what the learner sees. This validates the real
database against the exact KaTeX build the app ships, so a question that would
appear as red error text or as blank space fails here first.

Skips cleanly when there is no database or no node, so it never blocks a fresh
checkout.
"""

import json
import re
import shutil
import sqlite3
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / ".study" / "study.db"
VALIDATOR = ROOT / "tools" / "katex_validate.js"

INLINE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
DISPLAY = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)


def expressions_in(text: str) -> set[str]:
    return set(INLINE.findall(text)) | set(DISPLAY.findall(text))


def bank_fields() -> list[tuple[int, str, str]]:
    """Every learner-visible string in the bank, with the question it came from."""
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = []
    # Only questions the learner can actually be shown. A buried question is
    # withdrawn from circulation, and its text is kept for review history
    # rather than for display, so holding it to a rendering standard reports a
    # defect nobody can encounter.
    for row in db.execute(
        "SELECT id, prompt, answer, explanation, choices_json FROM questions "
        "WHERE status='ready'"
    ):
        rows.append((row["id"], "prompt", row["prompt"]))
        rows.append((row["id"], "answer", row["answer"]))
        rows.append((row["id"], "explanation", row["explanation"]))
        for index, choice in enumerate(json.loads(row["choices_json"] or "[]")):
            rows.append((row["id"], f"choice{index}", choice))
    db.close()
    return rows


@unittest.skipUnless(DB.is_file(), "no local question bank")
class BankRendersTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not available")
    def test_every_expression_renders_in_katex(self):
        found: set[str] = set()
        for _, _, text in bank_fields():
            found |= expressions_in(text or "")
        if not found:
            self.skipTest("no math in the bank")

        result = subprocess.run(
            ["node", str(VALIDATOR)],
            input=json.dumps(sorted(found)),
            capture_output=True,
            text=True,
            timeout=60,
        )
        failures = json.loads(result.stdout or "[]")
        self.assertEqual(
            failures,
            [],
            "\n".join(f"{f['expression']!r}: {f['error']}" for f in failures),
        )

    def test_no_question_shows_raw_latex_to_the_learner(self):
        """Markup outside \\( \\) reaches the screen as literal characters.

        This is what "lim_{(x,y)→(π,0)}" looked like in a shipped question.
        """
        import study

        offenders = [
            (qid, field)
            for qid, field, text in bank_fields()
            if text and study.has_plaintext_math(text)
        ]
        self.assertEqual(offenders, [], f"unrepaired math in {offenders[:5]}")

    def test_answers_match_their_own_choice(self):
        """A mismatch makes the question impossible to answer correctly."""
        db = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
        broken = []
        for row in db.execute(
            "SELECT id, answer, choices_json, correct_choice FROM questions WHERE status='ready'"
        ):
            choices = json.loads(row["choices_json"] or "[]")
            if not choices:
                continue
            if row["correct_choice"] >= len(choices) or choices[row["correct_choice"]] != row["answer"]:
                broken.append(row["id"])
        db.close()
        self.assertEqual(broken, [], f"answer is not among its choices: {broken}")


if __name__ == "__main__":
    unittest.main()


class DocumentQuestionSweepTest(unittest.TestCase):
    """The live bank must satisfy the guard that now governs new questions.

    tests_the_subject was tightened twice after the first imports, so questions
    written under the older rule kept being served. tools/bury_document_questions.py
    sweeps them; this is the check that it was run.
    """

    def test_no_served_question_examines_the_document(self):
        import study

        offenders = [
            (qid, text[:70])
            for qid, field, text in bank_fields()
            if field == "prompt" and not study.tests_the_subject(text)
        ]
        self.assertEqual(offenders, [], f"run tools/bury_document_questions.py: {offenders[:3]}")

    def test_no_served_question_needs_the_source_in_hand(self):
        import study

        offenders = [
            (qid, text[:70])
            for qid, field, text in bank_fields()
            if field == "prompt" and not study.is_self_contained(text)
        ]
        self.assertEqual(offenders, [], f"unanswerable without the source: {offenders[:3]}")
