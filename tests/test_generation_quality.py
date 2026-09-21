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


class MathNotationTest(unittest.TestCase):
    """Maths must be LaTeX inside \\( \\) or the learner sees the markup.

    The generator prompt asks for this, but a prompt is a request. These cover
    the repair pass that runs on save, which is the part that is enforceable.
    Every case here was taken from a question that actually shipped.
    """

    def test_unicode_superscripts_are_wrapped(self):
        self.assertEqual(study.repair_math("g(n) = n² works"), "g(n) = \\(n^{2}\\) works")

    def test_a_greek_base_becomes_a_latex_command(self):
        """σ² inside \\( \\) renders as nothing unless σ becomes \\sigma."""
        self.assertEqual(study.repair_math("σ² is the variance"), "\\(\\sigma^{2}\\) is the variance")

    def test_ascii_roots_are_wrapped(self):
        self.assertEqual(study.repair_math("compute sqrt(x) now"), "compute \\(\\sqrt{x}\\) now")

    def test_bare_latex_subscripts_are_wrapped(self):
        self.assertEqual(study.repair_math("uses p_{X,Y}(x,y)"), "uses \\(p_{X,Y}\\)(x,y)")

    def test_operator_names_typeset_upright(self):
        repaired = study.repair_math("For lim_{(x,y)→(π,0)} the limit")
        self.assertIn("\\lim_{", repaired)
        self.assertIn("\\to", repaired)
        self.assertIn("\\pi", repaired)

    def test_passes_never_nest_inside_each_other(self):
        """\\(\\(\\lim\\)_{...}\\) renders as nothing at all. This was live."""
        repaired = study.repair_math("For lim_{(x,y)→(π,0)} the limit")
        self.assertNotIn("\\(\\(", repaired)
        self.assertNotIn("\\)\\)", repaired)

    def test_existing_math_is_left_alone(self):
        for original in ("Already \\(n^2\\) fine", "Display \\[x^2\\] here"):
            self.assertEqual(study.repair_math(original), original)

    def test_prose_is_not_mistaken_for_mathematics(self):
        """An earlier version wrapped whole 'mathematical runs' and produced
        \\(two-path\\) and \\(n^{2} for\\)."""
        for prose in (
            "Why does the two-path test show the limit fails?",
            "The variance is 4 and the mean is 2.",
            "Under what condition is momentum conserved?",
        ):
            self.assertEqual(study.repair_math(prose), prose)

    def test_repair_is_idempotent(self):
        once = study.repair_math("g(n) = n² and p_{X,Y} and sqrt(x)")
        self.assertEqual(study.repair_math(once), once)

    def test_unrepaired_plaintext_is_still_reportable(self):
        self.assertTrue(study.has_plaintext_math("n² outside"))
        self.assertFalse(study.has_plaintext_math("\\(n^{2}\\) inside"))

    def test_the_generator_is_told_to_write_latex(self):
        import inspect

        prompt_source = inspect.getsource(study.claude_questions)
        self.assertIn("MATHEMATICS IS WRITTEN AS MATHEMATICS", prompt_source)
        self.assertIn("NEVER use a single $", prompt_source)


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


class SectionTaggingTest(unittest.TestCase):
    """A question must know which textbook section it examines.

    A quiz is defined by its sections, so an untagged question is invisible to
    quiz scope no matter how good it is - it sits in the bank and never
    appears the night before the quiz that tests it.
    """

    class Row(dict):
        def keys(self):
            return list(dict.keys(self))

    def test_a_single_section_material_tags_its_questions(self):
        self.assertEqual(
            study.section_of(self.Row(title="MA 26100 · 15.2 Limits & continuity"), {}),
            "15.2",
        )

    def test_a_two_section_material_defers_rather_than_guesses(self):
        """Arc length and curvature are taught together, so the title cannot
        say which half a given question tests. Guessing would file curvature
        questions under arc length and quietly distort both nodes."""
        self.assertEqual(
            study.section_of(self.Row(title="MA 26100 · 14.4 14.5 Arc length & curvature"), {}),
            "",
        )

    def test_a_chapter_material_has_no_section(self):
        for title in (
            "MA 26100 · 1. Vectors and the Geometry of Space",
            "MA 261 - 15.2 Limits and Continuity",
            "",
        ):
            self.assertEqual(study.section_of(self.Row(title=title), {}), "")


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

    def test_a_question_about_the_documents_own_definition_is_rejected(self):
        """The gate carried `defines? first` and `first defines?` but not the
        bare verb, so a prompt quizzing the document's definition rather than
        the definition itself shipped twice in one generation run."""
        for prompt in (
            "The material defines the radius of curvature as 1/kappa. What does it mean?",
            "The material motivates arc length by chopping a curve into tiny sticks.",
            "The unit shows that curvature is 1/a for a circle of radius a.",
            "This section derives the formula for the unit tangent vector.",
            "The material explains why acceleration lies in the osculating plane.",
        ):
            self.assertFalse(study.tests_the_subject(prompt), prompt)

    def test_a_question_that_merely_contains_the_word_material_survives(self):
        """`material` is a noun in its own right. A density problem about a
        material scientist is a real question about the subject."""
        for prompt in (
            "A materials scientist proposes g(x) = kx^4 as a density. Find k.",
            "The material of the beam has Young's modulus E. Compute the deflection.",
            "Why does a straight line have curvature exactly 0 everywhere?",
        ):
            self.assertTrue(study.tests_the_subject(prompt), prompt)

    def test_questions_about_how_the_source_is_arranged_are_rejected(self):
        """Nine of these shipped. The gate caught "the notes say" but not
        presentation verbs, so questions about the ORDER of a document got
        through. The learner sees one question at a time and never sees the
        arrangement, which makes them unanswerable as well as useless."""
        for prompt in (
            "The material introduces the IQR as an alternative to the range.",
            "The unit begins by distinguishing a vector from a point. Why?",
            "The course catalog places 'the object-oriented approach' after decomposition.",
            "Why does the material introduce a bar chart at this point?",
            "In this unit, what is defined first?",
            # Inverted form. The subject-first patterns missed this entirely.
            "Why does the material caution against treating all as outliers?",
            "Why do these notes recommend the median instead?",
        ):
            self.assertFalse(study.tests_the_subject(prompt), prompt)

    def test_attributing_a_method_to_the_source_is_rejected(self):
        """Two shapes survived the earlier patterns and reached the live bank.

        "The material uses a 'next value' test" attributes a method to the
        document rather than to the subject, so a learner who understands the
        test still cannot answer it. "The material's stated real risks" quizzes
        the document's own study advice, which is context for how to ask a
        question, not a thing to be examined on.
        """
        for prompt in (
            "The material uses a 'next value' test to distinguish discrete from continuous.",
            "Given that the sign of y is the material's stated real risk, what is the best use of time?",
            "The notes call this the interquartile range. Why?",
            "The unit refers to these as resistant measures.",
            "What does this section label a lurking variable?",
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
            # The verbs added for the cases above are ordinary English. A real
            # question may use any of them about a person or an object.
            "A material scientist uses a next-value test on heart rate. Why is it continuous?",
            "An engineer labels the axis in volts. What changes?",
            "Which distribution applies when trials are independent?",
            "The sensor refers to a fixed origin. Why does that matter?",
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


class GroundingTest(unittest.TestCase):
    """A quote must be real, and a line break must not make a real one look fake."""

    WRAPPED = (
        "An exception is an object representing a problem that occurred while the\n"
        "program was running. Throwing one unwinds the call stack until some\n"
        "enclosing try block catches it."
    )

    def test_a_quote_spanning_a_line_break_is_still_verbatim(self):
        """This silently cost whole units their questions.

        The material is hard-wrapped, so a quote the model copied correctly
        differs from the source only by where the lines break. Comparing raw
        text dropped it, and generation reported 'Saved 1/8' with no reason.
        """
        quote = "An exception is an object representing a problem that occurred while the program was running."
        self.assertTrue(study.generation_quality_ok(self.WRAPPED, quote, "an object"))

    def test_a_fabricated_quote_is_still_rejected(self):
        """The whole point of the check: an unsupported question cannot be stored."""
        self.assertFalse(
            study.generation_quality_ok(
                self.WRAPPED,
                "Exceptions are stored in a special heap region called the trap table.",
                "the trap table",
            )
        )

    def test_a_trivially_short_quote_is_rejected(self):
        self.assertFalse(study.generation_quality_ok(self.WRAPPED, "an exception", "x"))

    def test_an_answer_that_merely_copies_the_quote_is_rejected(self):
        """Recall must be recall, not recognition of a copied sentence."""
        quote = "An exception is an object representing a problem that occurred while the program was running."
        self.assertFalse(study.generation_quality_ok(self.WRAPPED, quote, quote))


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


    def _save(self, choices, correct_choice):
        with study.connect(self.db_path) as db:
            digest = f"hash-{len(choices)}-{correct_choice}-{choices[1][:8]}"
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Quiz prep", "memory", MATERIAL, digest, study.now().isoformat()),
            ).lastrowid
            db.commit()
            material = db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
            candidate = self._candidate("Why is cancelling the common factor valid here?")
            candidate["choices"] = choices
            candidate["correct_choice"] = correct_choice
            return study.save_questions(db, material, [candidate])

    def test_a_six_option_question_is_kept(self):
        """Purdue mathematics exams offer A through F. A real past paper has to
        import with its own option count, or it is not that paper any more."""
        answer = "Because the expressions agree except at the point itself."
        self.assertEqual(self._save([
            answer,
            "Because limits ignore denominators.",
            "Because 0/0 equals 1.",
            "Because substitution always works.",
            "Because the denominator is never zero.",
            "The limit does not exist.",
        ], 0), 1)

    def test_too_few_and_too_many_options_are_both_rejected(self):
        answer = "Because the expressions agree except at the point itself."
        extras = [
            "Because limits ignore denominators.",
            "Because 0/0 equals 1.",
            "Because substitution always works.",
            "Because the denominator is never zero.",
            "The limit does not exist.",
            "Because the function is continuous.",
        ]
        self.assertEqual(self._save([answer, *extras[:2]], 0), 0)
        self.assertEqual(self._save([answer, *extras], 0), 0)

    def test_a_duplicated_option_is_still_rejected_at_six(self):
        answer = "Because the expressions agree except at the point itself."
        self.assertEqual(self._save([
            answer,
            "Because limits ignore denominators.",
            "Because limits ignore denominators.",
            "Because substitution always works.",
            "Because the denominator is never zero.",
            "The limit does not exist.",
        ], 0), 0)


if __name__ == "__main__":
    unittest.main()


class DocumentTitleTest(unittest.TestCase):
    def test_the_document_title_is_not_treated_as_a_section(self):
        """A '# Title' line names the handout, not a topic to be quizzed on."""
        topics = study.material_topics(MATERIAL)
        self.assertNotIn("Quiz prep — 15.2", topics)
        self.assertTrue(topics)


class ExplanationGateTest(unittest.TestCase):
    """The explanation is held to the same standard as the prompt.

    It is read at the moment the learner is most receptive - right after a
    miss - and nothing in the app ever shows them the source, so an
    explanation that appeals to "the material" appeals to something they
    cannot see. The gate only ever checked the prompt, and 395 questions
    shipped that way.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "study.db"

    def tearDown(self):
        self.temp.cleanup()

    def _save(self, explanation):
        with study.connect(self.db_path) as db:
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Quiz prep", "memory", MATERIAL, f"h-{hash(explanation)}", study.now().isoformat()),
            ).lastrowid
            db.commit()
            material = db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
            return study.save_questions(db, material, [{
                "prompt": "Why is cancelling the common factor valid here?",
                "answer": "Because the expressions agree except at the point itself.",
                "explanation": explanation,
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
            }])

    def test_an_explanation_about_the_document_is_rejected(self):
        self.assertEqual(self._save("The material states that cancellation is valid off the point."), 0)
        self.assertEqual(self._save("In the material, this is called a removable discontinuity."), 0)

    def test_an_explanation_with_plaintext_maths_is_rejected(self):
        """Markup outside \\( \\) reaches the screen as literal characters in an
        explanation exactly as it would in a prompt."""
        self.assertEqual(self._save("Because distance = speed × time at every instant of the motion."), 0)

    def test_an_explanation_that_argues_the_mathematics_is_kept(self):
        self.assertEqual(
            self._save("Cancellation is valid off the removed point, so the limits agree."), 1
        )


class TopicReuseTest(unittest.TestCase):
    """Generation must add to the nodes that exist, not invent new ones.

    Batches were told nothing about what earlier batches chose, so each
    invented its own names: section 14.5 ended up with thirteen nodes over
    sixteen questions. The path advances on a node's average mastery, so a
    node that small is completed by one lucky recall.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "study.db"

    def tearDown(self):
        self.temp.cleanup()

    def test_existing_topics_are_reported_largest_node_first(self):
        with study.connect(self.db_path) as db:
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Curvature", "memory", MATERIAL, "reuse-hash", study.now().isoformat()),
            ).lastrowid
            for topic, copies in (("Curvature", 3), ("Arc length", 1)):
                for index in range(copies):
                    db.execute(
                        """INSERT INTO questions
                           (material_id,prompt,answer,explanation,topic,kind,difficulty,
                            source_quote,choices_json,correct_choice,created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (material_id, f"{topic} {index}?", "A", "why", topic, "recall", 3,
                         "quote", "[]", -1, study.now().isoformat()),
                    )
            db.commit()
            self.assertEqual(study.existing_topics(db, material_id), ["Curvature", "Arc length"])

    def test_a_material_with_no_questions_yet_reports_none(self):
        with study.connect(self.db_path) as db:
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Fresh", "memory", MATERIAL, "fresh-hash", study.now().isoformat()),
            ).lastrowid
            db.commit()
            self.assertEqual(study.existing_topics(db, material_id), [])
