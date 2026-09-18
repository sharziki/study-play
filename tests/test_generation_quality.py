"""Gates on what a generated question is allowed to be.

Three failures make a question worthless regardless of how well it is written:
it cannot be answered without the source document, it examines the document
rather than the subject, or it leaves part of the material unexamined.
"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import study


MATERIAL = """# Quiz prep — 15.2

## Type 1 — Factor-and-cancel limit (0/0)
Factor the difference of squares and cancel.

## Type 2 — Direct substitution with trig
Continuous, so substitute.

## Type 3 — Two-path test
Different paths give different values.
"""


class SelfContainedTest(unittest.TestCase):
    def test_exercise_references_are_rejected(self):
        for prompt in (
            "In 15.2.29, why does the two-path test show the limit fails?",
            "Using problem 4.2, compute the limit.",
            "Recall example 7.1 and explain the result.",
            "The problem above asks for continuity. Why?",
        ):
            self.assertFalse(study.is_self_contained(prompt), prompt)

    def test_standalone_questions_are_kept(self):
        for prompt in (
            "Why must the sign of y be split into cases?",
            "Evaluate lim_{(x,y)->(0,0)} x^2y/(x^4+y^2) along y=x^2.",
            "A function is defined as 0 at the origin. When is it continuous there?",
        ):
            self.assertTrue(study.is_self_contained(prompt), prompt)


class SubjectNotDocumentTest(unittest.TestCase):
    def test_questions_about_the_document_are_rejected(self):
        for prompt in (
            "According to the quiz-prep notes, what formatting mistake cost a point?",
            "The notes say every problem takes 5-20 seconds. What is the real risk?",
            "The Tuesday 15.2 quiz-prep notes organize problems into five types. Why?",
            "What does the material say about parentheses?",
            "Based on these lecture notes, which technique applies?",
        ):
            self.assertFalse(study.tests_the_subject(prompt), prompt)

    def test_subject_questions_survive_incidental_vocabulary(self):
        """'material', 'text', and 'notes' are ordinary words in real problems."""
        for prompt in (
            "Why is it valid to cancel the common factor before substituting?",
            "A material point moves along a curve. Compute its velocity.",
            "Which text is continuous at the origin?",
            "The function notes a discontinuity at the origin. Why?",
            "Per the chain rule, what is the derivative?",
        ):
            self.assertTrue(study.tests_the_subject(prompt), prompt)


class TopicCoverageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "study.db"

    def tearDown(self):
        self.temp.cleanup()

    def test_sections_are_read_from_headings_without_enumerating_prefixes(self):
        topics = study.material_topics(MATERIAL)
        self.assertIn("Factor-and-cancel limit (0/0)", topics)
        self.assertIn("Direct substitution with trig", topics)
        self.assertIn("Two-path test", topics)
        for topic in topics:
            self.assertFalse(topic.lower().startswith("type "), topic)

    def _material_with_questions(self, topics):
        with study.connect(self.db_path) as db:
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Quiz prep", "memory", MATERIAL, "hash", study.now().isoformat()),
            ).lastrowid
            for index, topic in enumerate(topics):
                db.execute(
                    """INSERT INTO questions
                       (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,
                        choices_json,correct_choice,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (material_id, f"Question about {topic}?", "A", "E", topic, "recall", 3,
                     "Factor the difference of squares and cancel.",
                     json.dumps(["A", "B", "C", "D"]), 0, study.now().isoformat()),
                )
            db.commit()
            return db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()

    def test_unexamined_sections_are_reported(self):
        with study.connect(self.db_path) as db:
            material = self._material_with_questions(["Factor-and-cancel limit (0/0)"])
            missing = study.uncovered_topics(db, material)
            self.assertIn("Direct substitution with trig", missing)
            self.assertIn("Two-path test", missing)
            self.assertNotIn("Factor-and-cancel limit (0/0)", missing)

    def test_full_coverage_reports_nothing_missing(self):
        with study.connect(self.db_path) as db:
            material = self._material_with_questions(study.material_topics(MATERIAL))
            self.assertEqual(study.uncovered_topics(db, material), [])

    def test_coverage_matches_on_wording_not_exact_titles(self):
        """The model names a topic in its own words; matching must tolerate that."""
        with study.connect(self.db_path) as db:
            material = self._material_with_questions(
                ["factor and cancel limits", "substitution with trig functions", "two path test"]
            )
            self.assertEqual(study.uncovered_topics(db, material), [])


class SaveGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "study.db"

    def tearDown(self):
        self.temp.cleanup()

    def _candidate(self, prompt):
        return {
            "prompt": prompt,
            "answer": "Because the expressions agree except at the point itself.",
            "explanation": "Cancellation is valid off the removed point.",
            "topic": "Factor-and-cancel",
            "kind": "explanation",
            "difficulty": 3,
            "source_quote": "Factor the difference of squares and cancel.",
            "choices": [
                "Because the expressions agree except at the point itself.",
                "Because limits ignore denominators.",
                "Because 0/0 equals 1.",
                "Because substitution always works.",
            ],
            "correct_choice": 0,
        }

    def test_the_save_gate_drops_unusable_questions_and_keeps_good_ones(self):
        with study.connect(self.db_path) as db:
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Quiz prep", "memory", MATERIAL, "hash", study.now().isoformat()),
            ).lastrowid
            db.commit()
            material = db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
            saved = study.save_questions(db, material, [
                self._candidate("Why is cancelling the common factor valid here?"),
                self._candidate("In 15.2.11, why is cancelling valid?"),
                self._candidate("According to the notes, why is cancelling valid?"),
            ])
            self.assertEqual(saved, 1)


if __name__ == "__main__":
    unittest.main()


class DocumentTitleTest(unittest.TestCase):
    def test_the_document_title_is_not_treated_as_a_section(self):
        """A '# Title' line names the handout, not a topic to be quizzed on."""
        topics = study.material_topics(MATERIAL)
        self.assertNotIn("Quiz prep — 15.2", topics)
        self.assertTrue(topics)
