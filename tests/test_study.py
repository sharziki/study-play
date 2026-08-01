import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import study


class StudyTest(unittest.TestCase):
    def test_companion_evolves_with_xp(self):
        self.assertEqual(study.companion_state(0)[0], "Shadow Sprite")
        self.assertEqual(study.companion_state(300)[0], "Nightling")
        self.assertEqual(study.companion_state(300)[2], 700)

    def test_rank_progression(self):
        self.assertEqual(study.rank_state(0), ("E", 200))
        self.assertEqual(study.rank_state(500), ("C", 1000))
        self.assertEqual(study.rank_state(4000), ("S", None))

    def test_recall_threshold_is_configurable_and_bounded(self):
        with patch.dict("os.environ", {"STUDY_RECALL_THRESHOLD": "0.55"}):
            self.assertEqual(study.recall_threshold(), 0.55)
        with patch.dict("os.environ", {"STUDY_RECALL_THRESHOLD": "2"}):
            self.assertEqual(study.recall_threshold(), 0.95)

    def test_typed_recall_surfaces_only_missing_key_terms(self):
        missing = study.missing_key_terms(
            "Net work changes kinetic energy.",
            "Final kinetic energy is 70 J because net work equals its change.",
        )
        self.assertIn("70", missing)
        self.assertNotIn("kinetic", [word.lower() for word in missing])

    def test_auto_scoring_only_handles_clear_cases(self):
        exact = study.recall_score("Net work changes kinetic energy", "Net work changes kinetic energy")
        vague = study.recall_score("energy changes", "Net work changes kinetic energy")
        self.assertEqual(study.automatic_rating(exact, 5), "good")
        self.assertIsNone(study.automatic_rating(vague, 5))
        self.assertEqual(study.automatic_rating(0.0, 2), "again")

    def test_generation_gate_rejects_short_quotes_and_near_copies(self):
        material = "Net work equals the change in kinetic energy for an object."
        self.assertFalse(study.generation_quality_ok(material, "Net work equals", "Net work"))
        self.assertFalse(study.generation_quality_ok(material, material, material))
        self.assertTrue(study.generation_quality_ok(material, material, "Its kinetic energy changes."))

    def test_cards_have_consistent_width(self):
        rendered = study.card("Question", "A long sentence that wraps cleanly.", 52)
        self.assertTrue(all(len(line) == 52 for line in rendered.splitlines()))

    def test_reward_prefers_calibrated_recall(self):
        honest_miss, miss_combo = study.award_xp("again", 1, 4)
        overconfident_miss, _ = study.award_xp("again", 5, 4)
        recalled, combo = study.award_xp("good", 4, 4)
        self.assertGreater(honest_miss, overconfident_miss)
        self.assertGreater(recalled, honest_miss)
        self.assertEqual(miss_combo, 0)
        self.assertEqual(combo, 5)

    def test_schedule_expands_and_resets(self):
        self.assertEqual(study.next_interval(4, "again"), timedelta(minutes=10))
        self.assertEqual(study.next_interval(4, "good"), timedelta(days=10))
        self.assertEqual(study.next_interval(4, "easy"), timedelta(days=16))

    def test_rejects_ungrounded_question(self):
        with tempfile.TemporaryDirectory() as directory:
            db = study.connect(Path(directory) / "test.db")
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Physics", "x", "Force equals mass times acceleration.", "hash", study.now().isoformat()),
            ).lastrowid
            material = db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
            question = {
                "prompt": "What is momentum?", "answer": "mv", "explanation": "Definition",
                "topic": "momentum", "difficulty": 1, "source_quote": "Momentum equals mass times velocity.",
            }
            self.assertEqual(study.save_questions(db, material, [question]), 0)

    def test_typed_answer_is_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            db = study.connect(Path(directory) / "test.db")
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Physics", "x", "F = ma", "hash", study.now().isoformat()),
            ).lastrowid
            question_id = db.execute(
                """INSERT INTO questions
                   (material_id,prompt,answer,explanation,topic,difficulty,source_quote,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (material_id, "Force law?", "F = ma", "Newton", "forces", 1, "F = ma", study.now().isoformat()),
            ).lastrowid
            db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (question_id, study.now().isoformat()))
            q = db.execute(
                """SELECT q.*, p.interval_days, p.mastery FROM questions q
                   JOIN progress p ON p.question_id=q.id WHERE q.id=?""",
                (question_id,),
            ).fetchone()
            study.record_review(db, q, "good", 5, 3.0, False, "Force equals mass times acceleration")
            saved = db.execute("SELECT response_text FROM reviews").fetchone()[0]
            self.assertEqual(saved, "Force equals mass times acceleration")
            profile = db.execute("SELECT daily_streak FROM profile WHERE id=1").fetchone()[0]
            self.assertEqual(profile, 1)

    def test_mastery_unlocks_true_recall(self):
        with tempfile.TemporaryDirectory() as directory:
            db = study.connect(Path(directory) / "test.db")
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Physics", "x", "F = ma", "hash", study.now().isoformat()),
            ).lastrowid
            question_id = db.execute(
                """INSERT INTO questions
                   (material_id,prompt,answer,explanation,topic,difficulty,source_quote,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (material_id, "Force law?", "F = ma", "Newton", "forces", 1, "F = ma", study.now().isoformat()),
            ).lastrowid
            db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (question_id, study.now().isoformat()))
            for _ in range(5):
                q = db.execute(
                    """SELECT q.*, p.interval_days, p.mastery FROM questions q
                       JOIN progress p ON p.question_id=q.id WHERE q.id=?""",
                    (question_id,),
                ).fetchone()
                study.record_review(db, q, "good", 5, 3.0, False, "F = ma")
            mastery = db.execute("SELECT mastery FROM progress WHERE question_id=?", (question_id,)).fetchone()[0]
            self.assertGreaterEqual(mastery, 0.65)
            self.assertGreaterEqual(study.concept_mastery(db, "forces"), 0.65)

    def test_free_run_uses_not_due_questions(self):
        with tempfile.TemporaryDirectory() as directory:
            db = study.connect(Path(directory) / "test.db")
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at) VALUES (?,?,?,?,?)",
                ("Physics", "x", "F = ma", "hash", study.now().isoformat()),
            ).lastrowid
            question_id = db.execute(
                """INSERT INTO questions
                   (material_id,prompt,answer,explanation,topic,difficulty,source_quote,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (material_id, "Force law?", "F = ma", "Newton", "forces", 1, "F = ma", study.now().isoformat()),
            ).lastrowid
            future = (study.now() + timedelta(days=5)).isoformat()
            db.execute("INSERT INTO progress(question_id,due_at) VALUES (?,?)", (question_id, future))
            self.assertEqual(study.due_questions(db), [])
            self.assertEqual(len(study.practice_questions(db)), 1)


if __name__ == "__main__":
    unittest.main()
