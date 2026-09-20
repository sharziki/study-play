"""Gates on the heading a learner reads above a unit.

A unit heading is the only name a body of material ever has in the app. The
importers derived it from a URL slug with `.title()`, so the path showed
"STAT 350 · 10.3 Ht For Mean Sigma Unknown" and "7.4 Discret Rvs And Clt". Every
case below is a heading that actually shipped.
"""

import sqlite3
import unittest

import titles
from tools.retitle_materials import retitle


class HumanizeTest(unittest.TestCase):
    def test_unreadable_abbreviations_are_expanded(self):
        self.assertEqual(
            titles.humanize("STAT 350 · 10.3 Ht For Mean Sigma Unknown"),
            "STAT 350 · 10.3 Hypothesis Testing for Mean Sigma Unknown",
        )

    def test_spoken_acronyms_keep_their_form_in_the_right_case(self):
        """"CLT" is clearer than "Central Limit Theorem" in a heading, but
        "Clt" is not a word."""
        self.assertEqual(titles.humanize("STAT 350 · 7.3 Clt"), "STAT 350 · 7.3 CLT")
        self.assertEqual(
            titles.humanize("STAT 350 · 12.1 Intro One Way Anova"),
            "STAT 350 · 12.1 Intro One Way ANOVA",
        )

    def test_a_source_typo_is_corrected(self):
        """The upstream filename says "discret". It shipped to the learner."""
        self.assertIn("Discrete Random Variables", titles.humanize("STAT 350 · 7.4 Discret Rvs And Clt"))

    def test_small_words_stop_being_capitalised(self):
        self.assertEqual(
            titles.humanize("STAT 350 · 3.2 Measures Of Central Tendency"),
            "STAT 350 · 3.2 Measures of Central Tendency",
        )

    def test_a_small_word_opening_the_description_stays_capitalised(self):
        """"· The Structure" must not become "· the Structure"; the separator
        starts a clause even though the word is not first in the string."""
        self.assertEqual(
            titles.humanize("STAT 350 · 2.1 · The Structure Of A Data Set"),
            "STAT 350 · 2.1 · The Structure of a Data Set",
        )

    def test_paired_abbreviations_read_as_one_idea(self):
        """"Ci Ht" is two abbreviations for one heading. Expanding each in
        isolation gives "Confidence Interval Hypothesis Testing"."""
        self.assertEqual(
            titles.humanize("STAT 350 · 11.1 Ci Ht Two Samples"),
            "STAT 350 · 11.1 Confidence Intervals and Hypothesis Testing Two Samples",
        )

    def test_humanize_is_idempotent(self):
        """The retitling tool runs against a live database and must be re-runnable."""
        for original in (
            "STAT 350 · 10.1 Ht Errors And Power",
            "STAT 350 · 5.1 Discrete Rvs And Pmfs",
            "STAT 350 · 9.5 Ci Cb Sigma Unknown",
            "CS 18000 · 4. Searching and Sorting",
        ):
            once = titles.humanize(original)
            self.assertEqual(titles.humanize(once), once, original)

    def test_a_readable_heading_is_left_alone(self):
        for good in (
            "CS 18000 · 1. Java Fundamentals — Types, Variables, and Control Flow",
            "MA 26100 · 5. Vector Calculus",
            "Putnam 2025 — Problems & Solutions",
        ):
            self.assertEqual(titles.humanize(good), good)

    def test_importer_and_tool_agree_on_the_same_heading(self):
        """A re-import must not reintroduce the heading the tool just fixed."""
        composed = titles.section_title("STAT 350 ·", "10.3", "ht-for-mean-sigma-unknown")
        self.assertEqual(composed, titles.humanize("STAT 350 · 10.3 Ht For Mean Sigma Unknown"))


class RetitleToolTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE materials (id INTEGER PRIMARY KEY, title TEXT)")
        self.db.executemany(
            "INSERT INTO materials(id,title) VALUES (?,?)",
            [(1, "STAT 350 · 7.3 Clt"), (2, "MA 26100 · 5. Vector Calculus")],
        )

    def test_only_unreadable_rows_are_rewritten(self):
        changed = retitle(self.db, verbose=False)
        self.assertEqual(changed, 1)
        titles_now = dict(self.db.execute("SELECT id, title FROM materials"))
        self.assertEqual(titles_now[1], "STAT 350 · 7.3 CLT")
        self.assertEqual(titles_now[2], "MA 26100 · 5. Vector Calculus")

    def test_a_second_run_changes_nothing(self):
        retitle(self.db, verbose=False)
        self.assertEqual(retitle(self.db, verbose=False), 0)


if __name__ == "__main__":
    unittest.main()
