#!/usr/bin/env python3
"""Local-first web surface for the Intellect study engine."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import mimetypes
import random
import sqlite3
import subprocess
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import study


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "web_static"
MAX_BODY = 32 * 1024 * 1024
RATINGS = {"again", "hard", "good", "easy"}
# How many nodes past the current one stay tappable. Two keeps the next action
# obvious without making the path feel like a paywall.
LOOKAHEAD = 2


def _short_label(name: str) -> str:
    """A compact badge for a class, e.g. "MA 26100" -> "MA 261".

    Course codes are long enough to blow out a phone header, and truncating
    blindly turns "STAT 350" into "STAT", which is not a class.
    """
    parts = str(name).split()
    if len(parts) >= 2 and parts[1][:1].isdigit():
        return f"{parts[0]} {parts[1][:3]}"
    return parts[0][:6] if parts else "All"


class StudyAPI:
    def __init__(self, db_path: Path = study.DB_PATH):
        self.db_path = Path(db_path)
        with study.connect(self.db_path):
            pass

    def _question(self, db: sqlite3.Connection, question_id: int) -> sqlite3.Row:
        row = db.execute(
            """SELECT q.*, p.interval_days, p.reviews, p.lapses, p.mastery, p.due_at,
                      m.title AS material_title, m.campaign
               FROM questions q JOIN progress p ON p.question_id=q.id
               JOIN materials m ON m.id=q.material_id WHERE q.id=?""",
            (question_id,),
        ).fetchone()
        if row is None:
            raise ValueError("question not found")
        return row

    def dashboard(self) -> dict:
        with study.connect(self.db_path) as db:
            profile = dict(db.execute("SELECT * FROM profile WHERE id=1").fetchone())
            due_count = db.execute(
                "SELECT COUNT(*) FROM progress p JOIN questions q ON q.id=p.question_id WHERE q.status='ready' AND p.due_at<=?",
                (study.now().isoformat(),),
            ).fetchone()[0]
            materials = db.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
            questions = db.execute("SELECT COUNT(*) FROM questions WHERE status='ready'").fetchone()[0]
            reviews = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            accuracy = db.execute("SELECT AVG(rating IN ('good','easy')) FROM reviews").fetchone()[0] or 0
            tracks = [
                {
                    "name": row["campaign"],
                    "materials": row["materials"],
                    "questions": row["questions"],
                    "mastery": float(row["mastery"] or 0),
                    "due": row["due"],
                }
                for row in db.execute(
                    """SELECT m.campaign, COUNT(DISTINCT m.id) AS materials,
                              COUNT(DISTINCT q.id) AS questions, AVG(p.mastery) AS mastery,
                              COUNT(DISTINCT CASE WHEN p.due_at<=? AND q.status='ready' THEN q.id END) AS due
                       FROM materials m LEFT JOIN questions q ON q.material_id=m.id
                       LEFT JOIN progress p ON p.question_id=q.id
                       GROUP BY m.campaign
                       ORDER BY CASE m.campaign WHEN 'Putnam' THEN 0 WHEN 'Purdue CS' THEN 1 ELSE 2 END, m.campaign""",
                    (study.now().isoformat(),),
                )
            ]
            topics = [
                {
                    "name": row["topic"],
                    "campaign": row["campaign"],
                    "mastery": float(row["mastery"] or 0),
                    "questions": row["questions"],
                    "lapses": row["lapses"],
                }
                for row in db.execute(
                    """SELECT q.topic, m.campaign, AVG(p.mastery) AS mastery,
                              COUNT(*) AS questions, SUM(p.lapses) AS lapses
                       FROM questions q JOIN progress p ON p.question_id=q.id
                       JOIN materials m ON m.id=q.material_id WHERE q.status='ready'
                       GROUP BY m.campaign, q.topic
                       ORDER BY mastery ASC, lapses DESC, questions DESC LIMIT 18"""
                )
            ]
            recent = [
                dict(row)
                for row in db.execute(
                    """SELECT m.id, m.title, m.campaign, m.created_at, COUNT(q.id) AS questions
                       FROM materials m LEFT JOIN questions q ON q.material_id=m.id
                       GROUP BY m.id ORDER BY m.id DESC LIMIT 8"""
                )
            ]
            rank, next_rank = study.rank_state(profile["xp"])
            companion, _, next_evolution = study.companion_state(profile["xp"])
            return {
                "profile": {
                    **profile,
                    "rank": rank,
                    "next_rank_xp": next_rank,
                    "companion": companion,
                    "next_evolution_xp": next_evolution,
                },
                "due_count": due_count,
                "materials_count": materials,
                "questions_count": questions,
                "reviews_count": reviews,
                "strong_recall": accuracy,
                "tracks": tracks,
                "topics": topics,
                "materials": recent,
            }

    def lesson_session(self, campaign: str | None = None) -> dict:
        """Return the next first-principles lesson without leaking check answers."""
        with study.connect(self.db_path) as db:
            params: list[object] = []
            campaign_clause = ""
            if campaign and campaign.lower() != "all":
                campaign_clause = "WHERE m.campaign=?"
                params.append(campaign)
            row = db.execute(
                f"""SELECT l.*, m.title AS material_title, m.campaign,
                           COALESCE(lp.stage,'teach') AS stage,
                           COALESCE(lp.current_check,0) AS current_check,
                           COALESCE(lp.correct_checks,0) AS correct_checks,
                           COALESCE(lp.attempted_checks,0) AS attempted_checks,
                           COALESCE(lp.xp_earned,0) AS xp_earned
                    FROM lessons l JOIN materials m ON m.id=l.material_id
                    LEFT JOIN lesson_progress lp ON lp.lesson_id=l.id
                    {campaign_clause}
                    ORDER BY CASE COALESCE(lp.stage,'teach') WHEN 'complete' THEN 1 ELSE 0 END,
                             COALESCE(lp.correct_checks,0) ASC, l.id ASC LIMIT 1""",
                params,
            ).fetchone()
            if row is None:
                return {"available": False}
            db.execute("INSERT OR IGNORE INTO lesson_progress(lesson_id) VALUES (?)", (row["id"],))
            db.commit()
            checks = json.loads(row["checks_json"])
            public_checks = [
                {"prompt": item["prompt"], "choices": list(item["choices"])}
                for item in checks
            ]
            return {
                "available": True,
                "id": row["id"],
                "topic": row["topic"],
                "title": row["title"],
                "objective": row["objective"],
                "motivation": row["motivation"],
                "prerequisites": json.loads(row["prerequisites_json"]),
                "primitives": json.loads(row["primitives_json"]),
                "derivation_steps": json.loads(row["derivation_steps_json"]),
                "worked_example": json.loads(row["worked_example_json"]),
                "misconception": row["misconception"],
                "checks": public_checks,
                "source_quote": row["source_quote"],
                "material": row["material_title"],
                "campaign": row["campaign"],
                "stage": row["stage"],
                "current_check": row["current_check"],
                "correct_checks": row["correct_checks"],
                "attempted_checks": row["attempted_checks"],
                "xp_earned": row["xp_earned"],
            }

    def lesson_check(self, payload: dict) -> dict:
        lesson_id = int(payload.get("lesson_id", 0))
        check_index = int(payload.get("check_index", -1))
        selected_choice = int(payload.get("selected_choice", -1))
        with study.connect(self.db_path) as db:
            lesson = db.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
            if lesson is None:
                raise ValueError("lesson not found")
            checks = json.loads(lesson["checks_json"])
            if check_index < 0 or check_index >= len(checks):
                raise ValueError("check not found")
            check = checks[check_index]
            if selected_choice < 0 or selected_choice >= len(check["choices"]):
                raise ValueError("choice not found")
            db.execute("INSERT OR IGNORE INTO lesson_progress(lesson_id) VALUES (?)", (lesson_id,))
            progress = db.execute("SELECT * FROM lesson_progress WHERE lesson_id=?", (lesson_id,)).fetchone()
            assert progress is not None
            if check_index < progress["current_check"]:
                return {
                    "correct": selected_choice == check["correct_choice"],
                    "correct_choice": check["correct_choice"],
                    "explanation": check["explanation"],
                    "xp_gained": 0,
                    "stage": progress["stage"],
                    "current_check": progress["current_check"],
                    "ready_for_challenge": progress["stage"] in {"challenge", "complete"},
                    "already_completed": True,
                }
            if check_index > progress["current_check"]:
                raise ValueError("complete the current check first")
            correct = selected_choice == check["correct_choice"]
            next_check = check_index + 1 if correct else check_index
            complete = correct and next_check == len(checks)
            xp = (5 + (10 if complete else 0)) if correct else 0
            stage = "challenge" if complete else "check"
            db.execute(
                """INSERT INTO lesson_attempts(lesson_id,check_index,selected_choice,correct,xp,attempted_at)
                   VALUES (?,?,?,?,?,?)""",
                (lesson_id, check_index, selected_choice, int(correct), xp, study.now().isoformat()),
            )
            db.execute(
                """UPDATE lesson_progress
                   SET stage=?, current_check=?,
                       correct_checks=correct_checks+?, attempted_checks=attempted_checks+1,
                       xp_earned=xp_earned+? WHERE lesson_id=?""",
                (stage, next_check, int(correct), xp, lesson_id),
            )
            if xp:
                db.execute("UPDATE profile SET xp=xp+? WHERE id=1", (xp,))
            profile = dict(db.execute("SELECT * FROM profile WHERE id=1").fetchone())
            db.commit()
            rank, next_rank = study.rank_state(profile["xp"])
            return {
                "correct": correct,
                "correct_choice": check["correct_choice"],
                "explanation": check["explanation"],
                "xp_gained": xp,
                "stage": stage,
                "current_check": next_check,
                "ready_for_challenge": complete,
                "already_completed": False,
                "rank": rank,
                "next_rank_xp": next_rank,
            }

    def _topic_session(self, limit: int, campaign: str | None, topic: str) -> dict:
        """Build a concept-linked challenge set, ignoring spaced-review due dates."""
        with study.connect(self.db_path) as db:
            params: list[object] = [topic]
            campaign_clause = ""
            if campaign and campaign.lower() != "all":
                campaign_clause = " AND m.campaign=?"
                params.append(campaign)
            params.append(limit)
            rows = list(db.execute(
                f"""SELECT q.*, p.interval_days, p.reviews, p.lapses, p.mastery, p.due_at,
                           m.title AS material_title, m.campaign
                    FROM questions q JOIN progress p ON p.question_id=q.id
                    JOIN materials m ON m.id=q.material_id
                    WHERE q.status='ready' AND q.topic=? {campaign_clause}
                    ORDER BY CASE WHEN q.kind='transfer' THEN 0 ELSE 1 END,
                             q.difficulty DESC, p.mastery ASC, p.reviews ASC
                    LIMIT ?""",
                params,
            ))
            questions = []
            for index, row in enumerate(rows):
                mastery = study.concept_mastery(db, row["topic"])
                choices_data = study.multiple_choices(db, row)
                recognition = row["kind"] != "transfer" and mastery < study.recall_threshold() and choices_data is not None
                mode = "true_recall" if row["kind"] == "transfer" else ("recognition" if recognition else "recall")
                questions.append({
                    "id": row["id"], "prompt": row["prompt"], "topic": row["topic"],
                    "kind": row["kind"], "difficulty": row["difficulty"],
                    "material": row["material_title"], "campaign": row["campaign"],
                    "mastery": mastery, "mode": mode,
                    "choices": choices_data[0] if recognition and choices_data else [],
                    "boss": index == 0, "target_seconds": 25 + row["difficulty"] * 10,
                })
            return {"questions": questions, "free_run": False, "campaign": campaign or "All", "topic": topic}

    def session(self, limit: int = 12, campaign: str | None = None, topic: str | None = None) -> dict:
        limit = max(1, min(40, int(limit)))
        if topic:
            return self._topic_session(limit, campaign, topic)
        with study.connect(self.db_path) as db:
            params: list[object] = [study.now().isoformat()]
            campaign_clause = ""
            if campaign and campaign.lower() != "all":
                campaign_clause = " AND m.campaign=?"
                params.append(campaign)
            params.append(max(limit * 4, 40))
            rows = list(
                db.execute(
                    f"""SELECT q.*, p.interval_days, p.reviews, p.lapses, p.mastery, p.due_at,
                               m.title AS material_title, m.campaign, m.course_id
                        FROM questions q JOIN progress p ON p.question_id=q.id
                        JOIN materials m ON m.id=q.material_id
                        WHERE q.status='ready' AND p.due_at<=? {campaign_clause}
                        ORDER BY p.lapses DESC, p.mastery ASC, p.reviews ASC, p.due_at ASC LIMIT ?""",
                    params,
                )
            )
            free_run = not rows
            if free_run:
                params = []
                campaign_clause = ""
                if campaign and campaign.lower() != "all":
                    campaign_clause = " AND m.campaign=?"
                    params.append(campaign)
                params.append(max(limit * 4, 40))
                rows = list(
                    db.execute(
                        f"""SELECT q.*, p.interval_days, p.reviews, p.lapses, p.mastery, p.due_at,
                                   m.title AS material_title, m.campaign, m.course_id
                            FROM questions q JOIN progress p ON p.question_id=q.id
                            JOIN materials m ON m.id=q.material_id
                            WHERE q.status='ready' {campaign_clause}
                            ORDER BY p.mastery ASC, p.reviews ASC, p.due_at ASC LIMIT ?""",
                        params,
                    )
                )
            pressures = study.course_pressures(db)
            random.shuffle(rows)
            rows.sort(key=lambda row: study.attempt_priority(row, pressures), reverse=True)
            ordered: list[sqlite3.Row] = []
            while rows and len(ordered) < limit:
                # Interleaving avoids consecutive same-topic questions, but only
                # among comparably urgent candidates. Searching the whole queue
                # for a topic change would hand a distant course equal time with
                # one being examined in two days, silently undoing the
                # exam-pressure ordering above.
                window = rows[: study.INTERLEAVE_WINDOW]
                pick = next(
                    (index for index, row in enumerate(window) if not ordered or row["topic"] != ordered[-1]["topic"]),
                    0,
                )
                ordered.append(rows.pop(pick))
            ordered = study.arrange_boss_transfers(ordered)
            questions = []
            for index, row in enumerate(ordered, 1):
                mastery = study.concept_mastery(db, row["topic"])
                choices_data = study.multiple_choices(db, row)
                recognition = mastery < study.recall_threshold() and choices_data is not None
                choices = choices_data[0] if recognition and choices_data else []
                questions.append(
                    {
                        "id": row["id"],
                        "prompt": row["prompt"],
                        "topic": row["topic"],
                        "kind": row["kind"],
                        "difficulty": row["difficulty"],
                        "material": row["material_title"],
                        "campaign": row["campaign"],
                        "course": (pressures.get(row["course_id"]) or {}).get("course_code", ""),
                        "exam_days_left": (pressures.get(row["course_id"]) or {}).get("days_left"),
                        "mastery": mastery,
                        "mode": "recognition" if recognition else "recall",
                        "choices": choices,
                        "boss": index % 5 == 0,
                        "target_seconds": 25 + row["difficulty"] * 10,
                    }
                )
            return {
                "questions": questions,
                "free_run": free_run,
                "campaign": campaign or "All",
                "exams": sorted(pressures.values(), key=lambda item: item["days_left"]),
            }

    def courses(self) -> dict:
        """Every active course with its next exam, countdown, and readiness."""
        return self._courses()

    def classes(self) -> dict:
        """Every subject the learner can switch between, with its own progress.

        This is the macro switcher. It is deliberately derived from the
        material table rather than a hand-kept list, so importing a new
        subject makes it appear with no configuration step: fill the database
        and the app already knows about it.
        """
        with study.connect(self.db_path) as db:
            pressures = study.course_pressures(db)
            by_course = {
                pressure["course_code"]: pressure
                for pressure in pressures.values()
                if pressure.get("course_code")
            }
            subjects = []
            for row in db.execute(
                """SELECT m.campaign AS name,
                          COALESCE(c.title, '') AS title,
                          COUNT(DISTINCT m.id) AS materials,
                          COUNT(DISTINCT CASE WHEN q.status='ready' THEN q.id END) AS questions,
                          COALESCE(AVG(p.mastery), 0) AS mastery,
                          COUNT(DISTINCT CASE WHEN p.due_at<=? AND q.status='ready' THEN q.id END) AS due,
                          COUNT(DISTINCT q.topic) AS topics
                   FROM materials m
                   LEFT JOIN courses c ON c.id = m.course_id
                   LEFT JOIN questions q ON q.material_id = m.id
                   LEFT JOIN progress p ON p.question_id = q.id
                   GROUP BY m.campaign
                   HAVING questions > 0
                   ORDER BY m.campaign""",
                (study.now().isoformat(),),
            ):
                pressure = by_course.get(row["name"], {})
                subjects.append(
                    {
                        "name": row["name"],
                        "title": row["title"] or row["name"],
                        "short": _short_label(row["name"]),
                        "materials": row["materials"],
                        "questions": row["questions"],
                        "topics": row["topics"],
                        "mastery": float(row["mastery"] or 0),
                        "due": row["due"],
                        "next_exam": pressure.get("exam_title"),
                        "exam_date": pressure.get("exam_date"),
                        "days_left": pressure.get("days_left"),
                    }
                )
            subjects.sort(key=lambda item: (item["days_left"] is None, item["days_left"] or 0, item["name"]))
            totals = {
                "questions": sum(item["questions"] for item in subjects),
                "due": sum(item["due"] for item in subjects),
                "materials": sum(item["materials"] for item in subjects),
            }
            return {"classes": subjects, "totals": totals}

    def path(self, campaign: str | None = None) -> dict:
        """The learning path: units of material, each a row of topic nodes.

        Duolingo's map works because the next action is never a decision. One
        node is current, everything before it is done, everything after is
        visibly waiting. Mastery decides the boundary, so the path reorders
        itself as the learner improves instead of being hand-sequenced.
        """
        with study.connect(self.db_path) as db:
            pressures = study.course_pressures(db)
            params: list[object] = [study.now().isoformat()]
            clause = ""
            if campaign and campaign.lower() != "all":
                clause = " AND m.campaign=?"
                params.append(campaign)
            rows = list(db.execute(
                f"""SELECT m.id AS material_id, m.title AS material_title, m.campaign,
                           m.course_id, q.topic,
                           COUNT(q.id) AS questions,
                           AVG(p.mastery) AS mastery,
                           SUM(CASE WHEN p.due_at<=? THEN 1 ELSE 0 END) AS due,
                           SUM(p.reviews) AS reviews,
                           MIN(q.id) AS first_question,
                           MAX(CASE WHEN q.kind='transfer' THEN 1 ELSE 0 END) AS has_transfer
                    FROM materials m
                    JOIN questions q ON q.material_id=m.id AND q.status='ready'
                    JOIN progress p ON p.question_id=q.id
                    WHERE 1=1 {clause}
                    GROUP BY m.id, q.topic
                    ORDER BY m.id, MIN(q.id)""",
                params,
            ))
            lessons = {
                (row["material_id"], row["topic"]): row["id"]
                for row in db.execute("SELECT id, material_id, topic FROM lessons")
            }

        units: list[dict] = []
        by_material: dict[int, dict] = {}
        for row in rows:
            unit = by_material.get(row["material_id"])
            if unit is None:
                pressure = pressures.get(row["course_id"]) or {}
                unit = {
                    "material_id": row["material_id"],
                    "title": row["material_title"],
                    "campaign": row["campaign"],
                    "course": pressure.get("course_code", row["campaign"]),
                    "days_left": pressure.get("days_left"),
                    "exam_title": pressure.get("exam_title"),
                    "nodes": [],
                }
                by_material[row["material_id"]] = unit
                units.append(unit)
            mastery = float(row["mastery"] or 0)
            unit["nodes"].append({
                "topic": row["topic"],
                "questions": row["questions"],
                "mastery": mastery,
                "due": row["due"] or 0,
                "reviews": row["reviews"] or 0,
                "lesson_id": lessons.get((row["material_id"], row["topic"])),
                "kind": "transfer" if row["has_transfer"] else "practice",
                "state": "complete" if mastery >= study.recall_threshold() else "open",
            })

        # Urgent courses float to the top; within a unit the first unfinished
        # node becomes the entry point. Everything is not hard-locked: a short
        # lookahead stays tappable because a learner who knows what they need
        # to study next should never be told no. Locking exists to remove
        # decisions, not to withhold material.
        units.sort(key=lambda unit: (unit["days_left"] is None, unit["days_left"] or 0, unit["material_id"]))
        current_set = False
        for unit in units:
            ahead = 0
            for node in unit["nodes"]:
                if node["state"] == "complete":
                    continue
                if ahead == 0:
                    node["state"] = "current" if not current_set else "next"
                    current_set = True
                elif ahead <= LOOKAHEAD:
                    node["state"] = "open"
                else:
                    node["state"] = "locked"
                ahead += 1
            total = len(unit["nodes"]) or 1
            done = sum(1 for node in unit["nodes"] if node["state"] == "complete")
            unit["progress"] = done / total
            unit["complete"] = done == total
        return {"units": units, "campaign": campaign or "All"}

    def _courses(self) -> dict:
        """Every active course with its next exam, countdown, and readiness."""
        with study.connect(self.db_path) as db:
            pressures = study.course_pressures(db)
            courses = []
            for row in db.execute(
                """SELECT c.id, c.code, c.title, c.term,
                          COUNT(DISTINCT m.id) AS materials,
                          COUNT(q.id) AS questions,
                          COALESCE(AVG(p.mastery), 0) AS mastery,
                          SUM(CASE WHEN p.due_at <= ? THEN 1 ELSE 0 END) AS due
                   FROM courses c
                   LEFT JOIN materials m ON m.course_id = c.id
                   LEFT JOIN questions q ON q.material_id = m.id AND q.status='ready'
                   LEFT JOIN progress p ON p.question_id = q.id
                   WHERE c.archived = 0
                   GROUP BY c.id ORDER BY c.code""",
                (study.now().isoformat(),),
            ):
                pressure = pressures.get(row["id"], {})
                courses.append(
                    {
                        "id": row["id"],
                        "code": row["code"],
                        "title": row["title"],
                        "term": row["term"],
                        "materials": row["materials"],
                        "questions": row["questions"],
                        "mastery": row["mastery"],
                        "due": row["due"] or 0,
                        "next_exam": pressure.get("exam_title"),
                        "exam_date": pressure.get("exam_date"),
                        "days_left": pressure.get("days_left"),
                        "pressure": pressure.get("pressure", 1.0),
                    }
                )
            courses.sort(key=lambda item: (item["days_left"] is None, item["days_left"] or 0))
            return {"courses": courses}

    def create_course(self, payload: dict) -> dict:
        code = str(payload.get("code", "")).strip()
        if not code:
            raise ValueError("course code is required")
        title = str(payload.get("title", "")).strip() or code
        term = str(payload.get("term", "")).strip()
        with study.connect(self.db_path) as db:
            db.execute(
                """INSERT INTO courses(code, title, term, created_at) VALUES (?,?,?,?)
                   ON CONFLICT(code) DO UPDATE SET title=excluded.title, term=excluded.term""",
                (code, title, term, study.now().isoformat()),
            )
            db.commit()
            row = db.execute("SELECT id, code, title, term FROM courses WHERE code=?", (code,)).fetchone()
            return {"course": dict(row)}

    def create_exam(self, payload: dict) -> dict:
        course_code = str(payload.get("course", "")).strip()
        title = str(payload.get("title", "")).strip()
        exam_date = str(payload.get("date", "")).strip()
        if not (course_code and title and exam_date):
            raise ValueError("course, title, and date are required")
        try:
            study.days_until(exam_date)
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD") from None
        weight = float(payload.get("weight", 1.0))
        with study.connect(self.db_path) as db:
            course = db.execute("SELECT id FROM courses WHERE code=?", (course_code,)).fetchone()
            if course is None:
                raise ValueError(f"unknown course: {course_code}")
            db.execute(
                """INSERT INTO exams(course_id, title, exam_date, weight, created_at) VALUES (?,?,?,?,?)
                   ON CONFLICT(course_id, title)
                   DO UPDATE SET exam_date=excluded.exam_date, weight=excluded.weight""",
                (course["id"], title, exam_date, weight, study.now().isoformat()),
            )
            db.commit()
            return {
                "exam": {
                    "course": course_code,
                    "title": title,
                    "date": exam_date,
                    "weight": weight,
                    "days_left": study.days_until(exam_date),
                }
            }

    def assign_material(self, payload: dict) -> dict:
        """Attach an existing material to a course so its questions inherit exam pressure."""
        material_id = int(payload.get("material_id", 0))
        course_code = str(payload.get("course", "")).strip()
        with study.connect(self.db_path) as db:
            course = db.execute("SELECT id FROM courses WHERE code=?", (course_code,)).fetchone()
            if course is None:
                raise ValueError(f"unknown course: {course_code}")
            updated = db.execute(
                "UPDATE materials SET course_id=?, campaign=? WHERE id=?",
                (course["id"], course_code, material_id),
            ).rowcount
            if not updated:
                raise ValueError(f"unknown material: {material_id}")
            db.commit()
            return {"material_id": material_id, "course": course_code}

    def review_preview(self, payload: dict) -> dict:
        question_id = int(payload.get("question_id", 0))
        response = str(payload.get("response", "")).strip()
        confidence = max(1, min(5, int(payload.get("confidence", 3))))
        with study.connect(self.db_path) as db:
            question = self._question(db, question_id)
            score = study.recall_score(response, question["answer"])
            recognition = payload.get("mode") == "recognition"
            automatic = ("good" if response == question["answer"] else "again") if recognition else study.automatic_rating(score, confidence)
            return {
                "question_id": question_id,
                "answer": question["answer"],
                "explanation": question["explanation"],
                "source_quote": question["source_quote"],
                "score": score,
                "missing_terms": study.missing_key_terms(response, question["answer"]),
                "suggested_rating": automatic or ("again" if score < 0.25 else "hard" if score < 0.55 else "good"),
                "needs_rating": automatic is None,
            }

    def commit_review(self, payload: dict) -> dict:
        rating = str(payload.get("rating", ""))
        if rating not in RATINGS:
            raise ValueError("rating must be again, hard, good, or easy")
        question_id = int(payload.get("question_id", 0))
        confidence = max(1, min(5, int(payload.get("confidence", 3))))
        response_seconds = max(0.0, float(payload.get("response_seconds", 0)))
        response = str(payload.get("response", "")).strip()
        boss = bool(payload.get("boss", False))
        with study.connect(self.db_path) as db:
            question = self._question(db, question_id)
            old_mastery = float(question["mastery"])
            xp, pressure_bonus, shards = study.record_review(
                db, question, rating, confidence, response_seconds, boss, response
            )
            lesson_completed = False
            lesson_bonus_xp = 0
            lesson_id = int(payload.get("lesson_id", 0) or 0)
            if lesson_id and rating in {"good", "easy"}:
                lesson = db.execute(
                    """SELECT l.topic, lp.stage FROM lessons l
                       JOIN lesson_progress lp ON lp.lesson_id=l.id WHERE l.id=?""",
                    (lesson_id,),
                ).fetchone()
                if lesson and lesson["topic"] == question["topic"] and lesson["stage"] == "challenge":
                    lesson_completed = True
                    lesson_bonus_xp = 20
                    db.execute(
                        "UPDATE lesson_progress SET stage='complete', completed_at=?, xp_earned=xp_earned+? WHERE lesson_id=?",
                        (study.now().isoformat(), lesson_bonus_xp, lesson_id),
                    )
                    db.execute("UPDATE profile SET xp=xp+? WHERE id=1", (lesson_bonus_xp,))
            db.commit()
            progress = db.execute(
                "SELECT mastery,due_at,interval_days FROM progress WHERE question_id=?", (question_id,)
            ).fetchone()
            profile = dict(db.execute("SELECT * FROM profile WHERE id=1").fetchone())
            return {
                "question_id": question_id,
                "rating": rating,
                "answer": question["answer"],
                "explanation": question["explanation"],
                "source_quote": question["source_quote"],
                "xp_gained": xp,
                "pressure_bonus": pressure_bonus,
                "shards_gained": shards,
                "lesson_completed": lesson_completed,
                "lesson_bonus_xp": lesson_bonus_xp,
                "old_mastery": old_mastery,
                "mastery": float(progress["mastery"]),
                "next_due_at": progress["due_at"],
                "interval_days": float(progress["interval_days"]),
                "calibration": study.calibration_label(rating, confidence),
                "profile": profile,
            }

    def import_file(self, payload: dict) -> dict:
        filename = Path(str(payload.get("filename", "source.txt"))).name
        encoded = str(payload.get("data", ""))
        if not encoded:
            raise ValueError("file data is empty")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("file data is not valid base64") from error
        if len(raw) > 24 * 1024 * 1024:
            raise ValueError("file is too large (24 MB maximum)")
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            with tempfile.TemporaryDirectory(prefix="intellect-") as directory:
                source = Path(directory) / "source.pdf"
                output = Path(directory) / "source.txt"
                source.write_bytes(raw)
                result = subprocess.run(
                    ["pdftotext", "-layout", str(source), str(output)],
                    text=True,
                    capture_output=True,
                    timeout=45,
                )
                if result.returncode or not output.exists():
                    raise ValueError(result.stderr.strip() or "PDF text extraction failed")
                content = output.read_text(encoding="utf-8", errors="replace")
                if len(content.strip()) < 40:
                    raise ValueError("PDF has no usable text; it may be scanned")
        elif suffix in {".txt", ".md", ".tex", ".csv"}:
            content = raw.decode("utf-8", errors="replace")
        else:
            raise ValueError("supported files: PDF, Markdown, text, TeX, and CSV")
        return self.import_text({
            "title": payload.get("title") or Path(filename).stem,
            "campaign": payload.get("campaign") or "General",
            "content": content,
        })

    def import_text(self, payload: dict) -> dict:
        title = str(payload.get("title", "")).strip() or "Untitled material"
        content = str(payload.get("content", ""))
        campaign = str(payload.get("campaign", "General")).strip() or "General"
        if not content.strip():
            raise ValueError("material is empty")
        if len(content.encode("utf-8")) > MAX_BODY:
            raise ValueError("material is too large")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with study.connect(self.db_path) as db:
            row = db.execute("SELECT id FROM materials WHERE content_hash=?", (digest,)).fetchone()
            if row:
                return {"material_id": row["id"], "created": False}
            # A campaign naming a real course links the material to it, so newly
            # imported material inherits that course's exam pressure immediately.
            course = db.execute("SELECT id FROM courses WHERE code=?", (campaign,)).fetchone()
            material_id = db.execute(
                "INSERT INTO materials(title,path,content,content_hash,created_at,campaign,course_id) VALUES (?,?,?,?,?,?,?)",
                (
                    title,
                    "web://paste",
                    content,
                    digest,
                    study.now().isoformat(),
                    campaign,
                    course["id"] if course else None,
                ),
            ).lastrowid
            db.commit()
            if material_id is None:
                raise RuntimeError("material insert did not return an id")
            return {"material_id": material_id, "created": True, "course": campaign if course else None}

    def generate(self, payload: dict) -> dict:
        material_id = int(payload.get("material_id", 0))
        with study.connect(self.db_path) as db:
            if db.execute("SELECT 1 FROM materials WHERE id=?", (material_id,)).fetchone() is None:
                raise ValueError("material not found")
        if self.db_path != study.DB_PATH:
            raise ValueError("background generation is available only for the primary study database")
        study.start_generator(material_id)
        return {"started": True, "material_id": material_id}

    def bury(self, question_id: int) -> dict:
        with study.connect(self.db_path) as db:
            changed = db.execute("UPDATE questions SET status='buried' WHERE id=?", (question_id,)).rowcount
            db.commit()
        if not changed:
            raise ValueError("question not found")
        return {"buried": True, "question_id": question_id}

    def generation_status(self) -> dict:
        lines = []
        if study.LOG_PATH.exists():
            lines = study.LOG_PATH.read_text(errors="replace").splitlines()[-12:]
        return {"lines": lines}


class Handler(BaseHTTPRequestHandler):
    server_version = "Intellect/1.0"

    @property
    def api(self) -> StudyAPI:
        return self.server.api  # type: ignore[attr-defined]

    def log_message(self, format: str, *args) -> None:
        print(f"[intellect] {self.address_string()} {format % args}")

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("request is too large")
        raw = self.rfile.read(length)
        return json.loads(raw or b"{}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                return self._json({"ok": True, "service": "intellect"})
            if parsed.path == "/api/dashboard":
                self._json(self.api.dashboard())
                return
            if parsed.path == "/api/session":
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["12"])[0])
                campaign = query.get("campaign", [None])[0]
                topic = query.get("topic", [None])[0]
                self._json(self.api.session(limit, campaign, topic))
                return
            if parsed.path == "/api/lesson":
                query = parse_qs(parsed.query)
                campaign = query.get("campaign", [None])[0]
                self._json(self.api.lesson_session(campaign))
                return
            if parsed.path == "/api/courses":
                self._json(self.api.courses())
                return
            if parsed.path == "/api/classes":
                self._json(self.api.classes())
                return
            if parsed.path == "/api/path":
                query = parse_qs(parsed.query)
                self._json(self.api.path(query.get("campaign", [None])[0]))
                return
            if parsed.path == "/api/generation-status":
                self._json(self.api.generation_status())
                return
            self._static(parsed.path)
        except (ValueError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            self._json({"error": f"internal error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._body()
            routes = {
                "/api/review-preview": lambda: self.api.review_preview(payload),
                "/api/reviews": lambda: self.api.commit_review(payload),
                "/api/lesson-check": lambda: self.api.lesson_check(payload),
                "/api/materials": lambda: self.api.import_text(payload),
                "/api/material-files": lambda: self.api.import_file(payload),
                "/api/generate": lambda: self.api.generate(payload),
                "/api/bury": lambda: self.api.bury(int(payload.get("question_id", 0))),
                "/api/courses": lambda: self.api.create_course(payload),
                "/api/exams": lambda: self.api.create_exam(payload),
                "/api/material-course": lambda: self.api.assign_material(payload),
            }
            if parsed.path not in routes:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json(routes[parsed.path]())
        except (ValueError, json.JSONDecodeError, KeyError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            self._json({"error": f"internal error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (STATIC / relative).resolve()
        if STATIC.resolve() not in candidate.parents and candidate != STATIC.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            candidate = STATIC / "index.html"
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.name.endswith(".webmanifest"):
            content_type = "application/manifest+json"
        elif candidate.name.endswith(".js"):
            content_type = "text/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(body)))
        if candidate.name == "sw.js":
            # A cached service worker cannot ship its own replacement, which
            # would strand every installed client on an old build.
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Service-Worker-Allowed", "/")
        else:
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


class IntellectServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], api: StudyAPI):
        super().__init__(address, Handler)
        self.api = api


def serve(host: str = "127.0.0.1", port: int = 4173, db_path: Path = study.DB_PATH) -> None:
    server = IntellectServer((host, port), StudyAPI(db_path))
    print(f"Intellect running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Intellect local study web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--db", type=Path, default=study.DB_PATH)
    args = parser.parse_args()
    serve(args.host, args.port, args.db)


if __name__ == "__main__":
    main()
