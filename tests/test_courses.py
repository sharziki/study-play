"""Coverage for courses, exams, and exam-pressure scheduling.

The behavior under test is the one that matters during midterm season: when
several courses compete for the same study hour, the queue must reallocate
toward whichever exam is soonest instead of splitting attention evenly.
"""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import study
import web


def _iso(days_from_today: int) -> str:
    return (date.today() + timedelta(days=days_from_today)).isoformat()


class ExamPressureTest(unittest.TestCase):
    def test_pressure_rises_as_the_exam_approaches(self):
        imminent = study.exam_pressure(1)
        near = study.exam_pressure(7)
        far = study.exam_pressure(20)
        self.assertGreater(imminent, near)
        self.assertGreater(near, far)

    def test_distant_and_past_exams_do_not_distort_the_queue(self):
        self.assertEqual(study.exam_pressure(90), 1.0)
        self.assertEqual(study.exam_pressure(study.EXAM_HORIZON_DAYS + 1), 1.0)
        self.assertEqual(study.exam_pressure(-3), 0.0)

    def test_weight_amplifies_pressure_at_equal_distance(self):
        self.assertGreater(study.exam_pressure(5, weight=2.0), study.exam_pressure(5, weight=1.0))

    def test_days_until_counts_whole_days(self):
        self.assertEqual(study.days_until(_iso(4)), 4)
        self.assertEqual(study.days_until(_iso(0)), 0)
        self.assertEqual(study.days_until(_iso(-2)), -2)


class CourseApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "study.db"
        self.api = web.StudyAPI(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def _material(self, campaign: str, topic: str, count: int = 6) -> int:
        result = self.api.import_text(
            {"title": f"{campaign} notes", "campaign": campaign, "content": f"{topic} content. " * 20}
        )
        material_id = result["material_id"]
        with study.connect(self.db_path) as db:
            for index in range(count):
                qid = db.execute(
                    """INSERT INTO questions
                       (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,
                        choices_json,correct_choice,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        material_id,
                        f"{topic} question {index}?",
                        "Answer",
                        "Explanation",
                        topic,
                        "recall",
                        3,
                        f"{topic} content.",
                        json.dumps(["Answer", "Wrong A", "Wrong B", "Wrong C"]),
                        0,
                        study.now().isoformat(),
                    ),
                ).lastrowid
                db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (qid, study.now().isoformat()))
            db.commit()
        return material_id

    def test_course_and_exam_round_trip(self):
        self.api.create_course({"code": "MA 26100", "title": "Multivariable Calculus", "term": "Fall"})
        exam = self.api.create_exam({"course": "MA 26100", "title": "Quiz 1", "date": _iso(4)})
        self.assertEqual(exam["exam"]["days_left"], 4)

        courses = self.api.courses()["courses"]
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["next_exam"], "Quiz 1")
        self.assertEqual(courses[0]["days_left"], 4)

    def test_creating_a_course_twice_updates_rather_than_duplicates(self):
        self.api.create_course({"code": "CS 18000", "title": "Old title"})
        self.api.create_course({"code": "CS 18000", "title": "Problem Solving"})
        courses = self.api.courses()["courses"]
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["title"], "Problem Solving")

    def test_rescheduling_an_exam_updates_the_countdown(self):
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        self.api.create_exam({"course": "MA 26100", "title": "Midterm", "date": _iso(20)})
        moved = self.api.create_exam({"course": "MA 26100", "title": "Midterm", "date": _iso(3)})
        self.assertEqual(moved["exam"]["days_left"], 3)
        self.assertEqual(self.api.courses()["courses"][0]["days_left"], 3)

    def test_exam_requires_a_known_course_and_valid_date(self):
        with self.assertRaises(ValueError):
            self.api.create_exam({"course": "NOPE 101", "title": "Quiz", "date": _iso(2)})
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        with self.assertRaises(ValueError):
            self.api.create_exam({"course": "MA 26100", "title": "Quiz", "date": "next tuesday"})

    def test_import_links_material_to_a_matching_course(self):
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        result = self.api.import_text({"title": "Notes", "campaign": "MA 26100", "content": "Limits. " * 20})
        self.assertEqual(result["course"], "MA 26100")
        self.assertEqual(self.api.courses()["courses"][0]["materials"], 1)

    def test_import_without_a_matching_course_stays_unassigned(self):
        result = self.api.import_text({"title": "Notes", "campaign": "Putnam", "content": "Parity. " * 20})
        self.assertIsNone(result["course"])

    def test_assign_material_attaches_an_existing_import(self):
        material_id = self._material("Unfiled", "Gradients")
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        self.api.assign_material({"material_id": material_id, "course": "MA 26100"})
        self.assertEqual(self.api.courses()["courses"][0]["materials"], 1)

    def test_assign_material_rejects_unknown_targets(self):
        material_id = self._material("Unfiled", "Gradients")
        with self.assertRaises(ValueError):
            self.api.assign_material({"material_id": material_id, "course": "GHOST 101"})
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        with self.assertRaises(ValueError):
            self.api.assign_material({"material_id": 9999, "course": "MA 26100"})

    def test_imminent_exam_dominates_the_queue(self):
        """The core midterm-season guarantee."""
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        self.api.create_course({"code": "CS 18000", "title": "Programming"})
        self._material("MA 26100", "Limits", count=8)
        self._material("CS 18000", "Recursion", count=8)

        # The distant exam is worth more of the grade, yet must still yield.
        self.api.create_exam({"course": "MA 26100", "title": "Quiz", "date": _iso(2), "weight": 1.0})
        self.api.create_exam({"course": "CS 18000", "title": "Midterm", "date": _iso(20), "weight": 2.0})

        questions = self.api.session(limit=10)["questions"]
        calc = sum(1 for q in questions if q["course"] == "MA 26100")
        self.assertGreater(calc, len(questions) / 2)

    def test_lapsed_unexamined_material_cannot_crowd_out_an_imminent_exam(self):
        """The bug this reproduces was live, not hypothetical.

        Bundled example questions had accumulated 8 lapses. The session SQL
        prefiltered candidates with ORDER BY lapses DESC and only then applied
        exam pressure in Python, so the pressure sort never saw a single
        question from the course whose quiz was two days away. Two days before
        a real calculus quiz the app served demo physics.
        """
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        self._material("MA 26100", "Limits", count=8)
        self.api.create_exam({"course": "MA 26100", "title": "Quiz", "date": _iso(2)})

        # Unfiled material with a heavy lapse history and no exam at all. The
        # pool must exceed the SQL prefilter window (limit * 4) or the Python
        # sort still sees calculus rows and the bug hides; measured, not
        # assumed: 20 examples passes even when broken, 60 fails outright.
        self._material("EXAMPLES", "Newtonian mechanics", count=60)
        with study.connect(self.db_path) as db:
            db.execute(
                """UPDATE progress SET lapses=8 WHERE question_id IN
                   (SELECT q.id FROM questions q JOIN materials m ON m.id=q.material_id
                    WHERE m.campaign='EXAMPLES')"""
            )
            db.commit()

        questions = self.api.session(limit=8)["questions"]
        calc = sum(1 for q in questions if q["campaign"] == "MA 26100")
        self.assertGreater(calc, len(questions) / 2, "imminent quiz lost to unexamined material")

    def test_session_reports_upcoming_exams_soonest_first(self):
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        self.api.create_course({"code": "CS 18000", "title": "Programming"})
        self._material("MA 26100", "Limits")
        self._material("CS 18000", "Recursion")
        self.api.create_exam({"course": "CS 18000", "title": "Midterm", "date": _iso(18)})
        self.api.create_exam({"course": "MA 26100", "title": "Quiz", "date": _iso(3)})

        exams = self.api.session(limit=5)["exams"]
        self.assertEqual([exam["course_code"] for exam in exams], ["MA 26100", "CS 18000"])

    def test_past_exams_stop_steering_the_queue(self):
        self.api.create_course({"code": "MA 26100", "title": "Calc"})
        self.api.create_course({"code": "CS 18000", "title": "Programming"})
        self._material("MA 26100", "Limits", count=8)
        self._material("CS 18000", "Recursion", count=8)
        self.api.create_exam({"course": "MA 26100", "title": "Quiz", "date": _iso(-1)})
        self.api.create_exam({"course": "CS 18000", "title": "Midterm", "date": _iso(5)})

        session = self.api.session(limit=10)
        self.assertEqual([exam["course_code"] for exam in session["exams"]], ["CS 18000"])
        programming = sum(1 for q in session["questions"] if q["course"] == "CS 18000")
        self.assertGreater(programming, 0)

    def test_weakness_still_ranks_within_one_course(self):
        """Pressure reallocates across courses; need still orders within one."""
        pressures = {1: {"pressure": 2.0}}
        weak = {"mastery": 0.0, "lapses": 3, "reviews": 5, "course_id": 1}
        strong = {"mastery": 0.9, "lapses": 0, "reviews": 5, "course_id": 1}
        self.assertGreater(
            study.attempt_priority(weak, pressures),
            study.attempt_priority(strong, pressures),
        )

    def test_unscheduled_material_yields_to_an_examined_course(self):
        """Found by using it: two days before a calculus quiz the queue served
        bundled physics examples, because a course with no exam and a course
        with a distant exam were both weighted 1.0."""
        pressures = {1: {"pressure": 1.0}}
        scheduled = {"mastery": 0.5, "lapses": 0, "reviews": 3, "course_id": 1}
        unscheduled = {"mastery": 0.5, "lapses": 0, "reviews": 3, "course_id": 99}
        self.assertGreater(
            study.attempt_priority(scheduled, pressures),
            study.attempt_priority(unscheduled, pressures),
        )

    def test_unscheduled_material_is_still_reachable(self):
        unscheduled = {"mastery": 0.0, "lapses": 0, "reviews": 0, "course_id": 99}
        self.assertGreater(study.attempt_priority(unscheduled, {}), 0)

    def test_priority_tolerates_rows_without_course_context(self):
        unassigned = {"mastery": 0.2, "lapses": 0, "reviews": 1, "course_id": None}
        self.assertGreater(study.attempt_priority(unassigned, {}), 0)


if __name__ == "__main__":
    unittest.main()


class ExamSyncParsingTest(unittest.TestCase):
    """The shape purdue-mcp returns must keep parsing into exam rows."""

    PATTERN = __import__("re").compile(
        r"([A-Z]{2,5})\s+(\d{5})[A-Z]*[^—\n]*—\s*\w{3}\s+(\d{4}-\d{2}-\d{2})[^\n]*?\[(evening|final)\]"
    )

    SAMPLE = (
        "Exams in the next 120 days — West Lafayette\n\n"
        "  CS 18000BLK — Wed 2026-09-30 06:30p-07:30p (in 12d) · HAAS G050, DSAI B031  [evening]\n"
        "  MA 26100 — Mon 2026-10-05 08:00p-09:00p (in 17d) · Loeb Plyhs, WTHR 200  [evening]\n"
        "  MA 26100 — Tue 2026-12-15 01:00p-03:00p (in 88d) · WTHR 200  [final]\n"
    )

    def test_section_suffixes_and_kinds_are_recovered(self):
        found = self.PATTERN.findall(self.SAMPLE)
        self.assertEqual(
            found,
            [
                ("CS", "18000", "2026-09-30", "evening"),
                ("MA", "26100", "2026-10-05", "evening"),
                ("MA", "26100", "2026-12-15", "final"),
            ],
        )

    def test_the_header_line_is_not_mistaken_for_an_exam(self):
        header = "Exams in the next 120 days — West Lafayette\n"
        self.assertEqual(self.PATTERN.findall(header), [])
