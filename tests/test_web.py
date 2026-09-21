import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import study
import web


class WebAppTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "study.db"
        self.api = web.StudyAPI(self.db_path)
        with study.connect(self.db_path) as db:
            self.material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at,campaign) VALUES (?,?,?,?,?,?)",
                ("Putnam notes", "memory", "A parity invariant is unchanged by each legal move. " * 3,
                 "putnam-hash", study.now().isoformat(), "Putnam"),
            ).lastrowid
            for index, topic in enumerate(("Parity", "Invariants", "Parity"), 1):
                qid = db.execute(
                    """INSERT INTO questions
                       (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,
                        choices_json,correct_choice,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (self.material_id, f"Question {index}?", f"Answer {index}", f"Why {index}", topic,
                     "transfer" if index == 3 else "recall", min(5, index + 2),
                     "A parity invariant is unchanged by each legal move.",
                     json.dumps([f"Answer {index}", "Wrong A", "Wrong B", "Wrong C"]), 0,
                     study.now().isoformat()),
                ).lastrowid
                db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (qid, study.now().isoformat()))
            db.commit()

    def tearDown(self):
        self.temp.cleanup()

    def _seed_lesson(self):
        with study.connect(self.db_path) as db:
            lesson_id = db.execute(
                """INSERT INTO lessons
                   (material_id,topic,title,objective,motivation,prerequisites_json,primitives_json,
                    derivation_steps_json,worked_example_json,misconception,checks_json,source_quote,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    self.material_id, "Invariants", "Invariants from zero",
                    "Recognize a quantity that legal moves cannot change.",
                    "Instead of tracking every move, track what survives every move.",
                    json.dumps(["Basic arithmetic", "Even and odd numbers"]),
                    json.dumps([{"term": "state", "meaning": "The full configuration at one moment."},
                                {"term": "invariant", "meaning": "A property unchanged by every legal move."}]),
                    json.dumps(["Describe the state.", "List what one move changes.", "Find what remains fixed."]),
                    json.dumps({"problem": "Can parity change after adding 2?", "steps": ["Write n+2.", "It has the same parity as n."], "answer": "No."}),
                    "An invariant need not mean the entire state stays fixed.",
                    json.dumps([
                        {"prompt": "What must be true of an invariant?", "choices": ["It never changes under a legal move", "It always increases", "It is the whole state", "It is hard to compute"], "correct_choice": 0, "explanation": "Only preservation under every legal move is required."},
                        {"prompt": "Why are invariants useful?", "choices": ["They replace move-by-move simulation", "They enumerate every path", "They make every state equal", "They remove proof"], "correct_choice": 0, "explanation": "One preserved obstruction can rule out every possible move sequence."},
                    ]),
                    "A parity invariant is unchanged by each legal move.", study.now().isoformat(),
                ),
            ).lastrowid
            db.commit()
            return int(lesson_id)

    def test_lesson_session_teaches_before_checks_and_hides_answers(self):
        lesson_id = self._seed_lesson()
        lesson = self.api.lesson_session(campaign="Putnam")
        self.assertEqual(lesson["id"], lesson_id)
        self.assertEqual(lesson["stage"], "teach")
        self.assertEqual(lesson["primitives"][0]["term"], "state")
        self.assertEqual(len(lesson["derivation_steps"]), 3)
        self.assertNotIn("correct_choice", lesson["checks"][0])
        self.assertNotIn("explanation", lesson["checks"][0])

    def test_lesson_check_awards_mastery_xp_once_and_unlocks_challenge(self):
        lesson_id = self._seed_lesson()
        first = self.api.lesson_check({"lesson_id": lesson_id, "check_index": 0, "selected_choice": 0})
        self.assertTrue(first["correct"])
        self.assertEqual(first["xp_gained"], 5)
        self.assertEqual(first["stage"], "check")
        repeated = self.api.lesson_check({"lesson_id": lesson_id, "check_index": 0, "selected_choice": 0})
        self.assertEqual(repeated["xp_gained"], 0)
        second = self.api.lesson_check({"lesson_id": lesson_id, "check_index": 1, "selected_choice": 0})
        self.assertTrue(second["ready_for_challenge"])
        self.assertEqual(second["stage"], "challenge")
        self.assertEqual(second["xp_gained"], 15)
        with study.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT xp FROM profile WHERE id=1").fetchone()[0], 20)

    def test_successful_challenge_completes_lesson_and_awards_bonus(self):
        lesson_id = self._seed_lesson()
        self.api.lesson_check({"lesson_id": lesson_id, "check_index": 0, "selected_choice": 0})
        self.api.lesson_check({"lesson_id": lesson_id, "check_index": 1, "selected_choice": 0})
        with study.connect(self.db_path) as db:
            question_id = db.execute("SELECT id FROM questions WHERE topic='Invariants'").fetchone()[0]
        result = self.api.commit_review({
            "question_id": question_id, "lesson_id": lesson_id, "response": "Answer 2",
            "confidence": 4, "response_seconds": 15, "boss": True, "rating": "good",
        })
        self.assertTrue(result["lesson_completed"])
        self.assertEqual(result["lesson_bonus_xp"], 20)
        with study.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT stage FROM lesson_progress WHERE lesson_id=?", (lesson_id,)).fetchone()[0], "complete")

    def test_topic_session_prioritizes_transfer_for_the_lesson_challenge(self):
        session = self.api.session(limit=2, campaign="Putnam", topic="Parity")
        self.assertEqual([q["topic"] for q in session["questions"]], ["Parity", "Parity"])
        self.assertEqual(session["questions"][0]["kind"], "transfer")
        self.assertEqual(session["questions"][0]["mode"], "true_recall")

    def test_connect_migrates_material_campaign_without_losing_rows(self):
        with study.connect(self.db_path) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(materials)")}
            self.assertIn("campaign", columns)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM materials").fetchone()[0], 1)

    def test_dashboard_reports_profile_queue_tracks_and_mastery(self):
        dashboard = self.api.dashboard()
        self.assertEqual(dashboard["due_count"], 3)
        self.assertEqual(dashboard["profile"]["xp"], 0)
        self.assertEqual(dashboard["tracks"][0]["name"], "Putnam")
        self.assertTrue(any(topic["name"] == "Parity" for topic in dashboard["topics"]))

    def test_session_never_exposes_answers_and_keeps_choices_for_recognition(self):
        session = self.api.session(limit=3, campaign="Putnam")
        self.assertEqual(len(session["questions"]), 3)
        question = session["questions"][0]
        self.assertNotIn("answer", question)
        self.assertNotIn("explanation", question)
        self.assertEqual(len(question["choices"]), 4)
        self.assertIn(question["kind"], {"recall", "transfer"})

    def test_recognition_preview_grades_choice_deterministically(self):
        question = self.api.session(limit=1)["questions"][0]
        preview = self.api.review_preview({
            "question_id": question["id"], "response": "definitely wrong", "confidence": 5,
            "response_seconds": 4, "boss": False, "mode": "recognition",
        })
        self.assertFalse(preview["needs_rating"])
        self.assertEqual(preview["suggested_rating"], "again")

    def test_typed_preview_does_not_commit_ambiguous_answer(self):
        question = self.api.session(limit=1)["questions"][0]
        preview = self.api.review_preview({
            "question_id": question["id"], "response": "maybe", "confidence": 4,
            "response_seconds": 12, "boss": False,
        })
        self.assertTrue(preview["needs_rating"])
        self.assertIn("answer", preview)
        with study.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 0)

    def test_committed_review_updates_progress_and_returns_feedback(self):
        question = self.api.session(limit=1)["questions"][0]
        result = self.api.commit_review({
            "question_id": question["id"], "response": "Answer 1", "confidence": 5,
            "response_seconds": 8, "boss": False, "rating": "good",
        })
        self.assertGreater(result["xp_gained"], 0)
        self.assertGreater(result["mastery"], 0)
        self.assertIn("next_due_at", result)
        with study.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 1)

    def test_import_file_decodes_text_and_assigns_track(self):
        result = self.api.import_file({
            "filename": "algorithms.md", "title": "Algorithms", "campaign": "Purdue CS",
            "data": base64.b64encode(b"A loop invariant holds before and after every iteration.").decode(),
        })
        with study.connect(self.db_path) as db:
            row = db.execute("SELECT title,campaign,content FROM materials WHERE id=?", (result["material_id"],)).fetchone()
            self.assertEqual(tuple(row), ("Algorithms", "Purdue CS", "A loop invariant holds before and after every iteration."))

    def test_import_text_assigns_track_and_deduplicates_content(self):
        payload = {"title": "Graph theory", "content": "A tree with n vertices has n-1 edges.", "campaign": "Putnam"}
        first = self.api.import_text(payload)
        second = self.api.import_text(payload)
        self.assertEqual(first["material_id"], second["material_id"])
        self.assertFalse(second["created"])
        with study.connect(self.db_path) as db:
            row = db.execute("SELECT campaign FROM materials WHERE id=?", (first["material_id"],)).fetchone()
            self.assertEqual(row[0], "Putnam")


if __name__ == "__main__":
    unittest.main()


class PathTest(unittest.TestCase):
    """The path is the home screen, so its ordering rules are load-bearing."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "study.db"
        self.api = web.StudyAPI(self.db_path)
        with study.connect(self.db_path) as db:
            self.material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at,campaign) VALUES (?,?,?,?,?,?)",
                ("Chapter 15", "memory", "content", "hash-15", study.now().isoformat(), "MA 26100"),
            ).lastrowid
            for index, topic in enumerate(("Limits", "Continuity", "Partials"), 1):
                qid = db.execute(
                    """INSERT INTO questions
                       (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (self.material_id, f"Q{index}", f"A{index}", "why", topic, "recall", 3,
                     "quote", study.now().isoformat()),
                ).lastrowid
                db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (qid, study.now().isoformat()))
            db.commit()

    def tearDown(self):
        self.temp.cleanup()

    def test_exactly_one_node_is_current_and_later_ones_lock(self):
        units = self.api.path()["units"]
        states = [node["state"] for unit in units for node in unit["nodes"]]
        self.assertEqual(states.count("current"), 1)
        self.assertEqual(states[0], "current")
        self.assertTrue(all(state in {"open", "locked"} for state in states[1:]))

    def test_a_short_lookahead_stays_tappable_but_the_rest_locks(self):
        with study.connect(self.db_path) as db:
            for index in range(4, 9):
                qid = db.execute(
                    """INSERT INTO questions
                       (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (self.material_id, f"Q{index}", f"A{index}", "why", f"Topic {index}", "recall", 3,
                     "quote", study.now().isoformat()),
                ).lastrowid
                db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (qid, study.now().isoformat()))
            db.commit()
        states = [node["state"] for node in self.api.path()["units"][0]["nodes"]]
        self.assertEqual(states[0], "current")
        self.assertEqual(states[1:3], ["open", "open"])
        self.assertTrue(all(state == "locked" for state in states[3:]))

    def test_a_mastered_topic_completes_and_hands_the_torch_onward(self):
        with study.connect(self.db_path) as db:
            db.execute(
                """UPDATE progress SET mastery=0.95 WHERE question_id=
                   (SELECT id FROM questions WHERE topic='Limits')"""
            )
            db.commit()
        nodes = self.api.path()["units"][0]["nodes"]
        self.assertEqual(nodes[0]["state"], "complete")
        self.assertEqual(nodes[1]["state"], "current")
        self.assertAlmostEqual(self.api.path()["units"][0]["progress"], 1 / 3)

    def test_filtering_by_class_hides_the_others(self):
        with study.connect(self.db_path) as db:
            other = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at,campaign) VALUES (?,?,?,?,?,?)",
                ("CS reading", "memory", "content", "hash-cs", study.now().isoformat(), "CS 18000"),
            ).lastrowid
            qid = db.execute(
                """INSERT INTO questions
                   (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (other, "Q", "A", "why", "Recursion", "recall", 3, "quote", study.now().isoformat()),
            ).lastrowid
            db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (qid, study.now().isoformat()))
            db.commit()
        self.assertEqual(len(self.api.path()["units"]), 2)
        filtered = self.api.path(campaign="CS 18000")["units"]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["campaign"], "CS 18000")

    def test_the_sooner_exam_takes_the_top_of_the_path(self):
        from datetime import date, timedelta

        with study.connect(self.db_path) as db:
            far = db.execute(
                "INSERT INTO courses(code,title,created_at) VALUES (?,?,?)",
                ("CS 18000", "Problem Solving", study.now().isoformat()),
            ).lastrowid
            near = db.execute(
                "INSERT INTO courses(code,title,created_at) VALUES (?,?,?)",
                ("MA 26100", "Multivariate", study.now().isoformat()),
            ).lastrowid
            db.execute(
                "INSERT INTO exams(course_id,title,exam_date,created_at) VALUES (?,?,?,?)",
                (far, "Midterm", (date.today() + timedelta(days=30)).isoformat(), study.now().isoformat()),
            )
            db.execute(
                "INSERT INTO exams(course_id,title,exam_date,created_at) VALUES (?,?,?,?)",
                (near, "Quiz", (date.today() + timedelta(days=2)).isoformat(), study.now().isoformat()),
            )
            db.execute("UPDATE materials SET course_id=? WHERE id=?", (near, self.material_id))
            cs_material = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at,campaign,course_id) VALUES (?,?,?,?,?,?,?)",
                ("CS reading", "memory", "content", "hash-cs2", study.now().isoformat(), "CS 18000", far),
            ).lastrowid
            qid = db.execute(
                """INSERT INTO questions
                   (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (cs_material, "Q", "A", "why", "Recursion", "recall", 3, "quote", study.now().isoformat()),
            ).lastrowid
            db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (qid, study.now().isoformat()))
            db.commit()
        units = self.api.path()["units"]
        self.assertEqual(units[0]["course"], "MA 26100")
        self.assertEqual(units[0]["days_left"], 2)


class ClassSwitcherTest(unittest.TestCase):
    """The macro switcher must come from the data, not a maintained list.

    The whole point of the content boundary is that importing material for a
    new subject makes that subject appear with no code or config change.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "study.db"
        self.api = web.StudyAPI(self.db_path)

    def tearDown(self):
        self.temp.cleanup()

    def _seed(self, campaign: str, topics, course_id=None, hash_suffix=""):
        with study.connect(self.db_path) as db:
            material = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at,campaign,course_id) VALUES (?,?,?,?,?,?,?)",
                (f"{campaign} notes", "memory", "content", f"hash-{campaign}{hash_suffix}",
                 study.now().isoformat(), campaign, course_id),
            ).lastrowid
            for index, topic in enumerate(topics, 1):
                qid = db.execute(
                    """INSERT INTO questions
                       (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (material, f"Q{index}", f"A{index}", "why", topic, "recall", 3, "quote",
                     study.now().isoformat()),
                ).lastrowid
                db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (qid, study.now().isoformat()))
            db.commit()
            return material

    def test_a_newly_imported_subject_appears_with_no_configuration(self):
        self.assertEqual(self.api.classes()["classes"], [])
        self._seed("PHYS 172", ["Momentum", "Energy"])
        names = [item["name"] for item in self.api.classes()["classes"]]
        self.assertEqual(names, ["PHYS 172"])

    def test_each_class_reports_its_own_counts(self):
        self._seed("PHYS 172", ["Momentum", "Energy"])
        self._seed("CS 18000", ["Recursion"])
        found = {item["name"]: item for item in self.api.classes()["classes"]}
        self.assertEqual(found["PHYS 172"]["questions"], 2)
        self.assertEqual(found["PHYS 172"]["topics"], 2)
        self.assertEqual(found["CS 18000"]["questions"], 1)
        self.assertEqual(self.api.classes()["totals"]["questions"], 3)

    def test_the_class_with_the_nearest_exam_is_offered_first(self):
        from datetime import date, timedelta

        with study.connect(self.db_path) as db:
            far = db.execute("INSERT INTO courses(code,title,created_at) VALUES (?,?,?)",
                             ("CS 18000", "Problem Solving", study.now().isoformat())).lastrowid
            near = db.execute("INSERT INTO courses(code,title,created_at) VALUES (?,?,?)",
                              ("PHYS 172", "Mechanics", study.now().isoformat())).lastrowid
            db.execute("INSERT INTO exams(course_id,title,exam_date,created_at) VALUES (?,?,?,?)",
                       (far, "Midterm", (date.today() + timedelta(days=28)).isoformat(), study.now().isoformat()))
            db.execute("INSERT INTO exams(course_id,title,exam_date,created_at) VALUES (?,?,?,?)",
                       (near, "Quiz", (date.today() + timedelta(days=2)).isoformat(), study.now().isoformat()))
            db.commit()
        self._seed("CS 18000", ["Recursion"], course_id=far)
        self._seed("PHYS 172", ["Momentum"], course_id=near)
        classes = self.api.classes()["classes"]
        self.assertEqual(classes[0]["name"], "PHYS 172")
        self.assertEqual(classes[0]["days_left"], 2)
        self.assertEqual(classes[0]["next_exam"], "Quiz")

    def test_a_long_course_code_gets_a_badge_that_is_still_the_class(self):
        self.assertEqual(web._short_label("MA 26100"), "MA 261")
        self.assertEqual(web._short_label("STAT 35000"), "STAT 350")
        self.assertEqual(web._short_label("Putnam"), "Putnam")

    def test_a_subject_with_no_questions_is_not_offered(self):
        with study.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at,campaign) VALUES (?,?,?,?,?,?)",
                ("Empty", "memory", "content", "hash-empty", study.now().isoformat(), "EMPTY 101"),
            )
            db.commit()
        self.assertEqual([item["name"] for item in self.api.classes()["classes"]], [])


    def test_topic_session_matches_subject_not_just_exact_phrase(self):
        """Asking for "curvature" the night before a quiz returned ZERO
        questions while matching ones sat in the bank, because the filter was
        `q.topic=?` and real topics are phrases like "Curvature of a plane
        curve". Found 2026-09-21, one day before MA 261 Quiz 4."""
        with study.connect(self.db_path) as db:
            mid = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at,campaign) VALUES (?,?,?,?,?,?)",
                ("MA 261 - 14.5 Curvature", "memory", "Curvature measures bending. " * 3,
                 "curv-hash", study.now().isoformat(), "MA 26100"),
            ).lastrowid
            for topic in ("Curvature of a plane curve", "Unit tangent and normal"):
                qid = db.execute(
                    """INSERT INTO questions
                       (material_id,prompt,answer,explanation,topic,kind,difficulty,source_quote,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (mid, f"{topic}?", "A", "Why", topic, "concept", 3,
                     "Curvature measures bending.", study.now().isoformat()),
                ).lastrowid
                db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)",
                           (qid, study.now().isoformat()))
            db.commit()

        hits = self.api.session(limit=10, campaign="MA 26100", topic="curvature")["questions"]
        self.assertTrue(hits, "a subject search must find its questions")

        # A section number matches via the material title.
        self.assertTrue(self.api.session(limit=10, campaign="MA 26100", topic="14.5")["questions"])

        # An unrelated subject must still return nothing, not everything.
        self.assertFalse(self.api.session(limit=10, campaign="MA 26100", topic="zzz-nope")["questions"])
