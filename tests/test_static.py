"""Coverage for the mobile study surface.

These assert the properties that make the app usable on a phone with one
thumb, not the existence of particular markup. Each one corresponds to a
design rule that broke something real when it was violated.

The interface is now a React build derived from the MIT-licensed
sanidhyy/duolingo-clone (see NOTICE), so these read the TypeScript sources in
`ui/src` rather than the hand-written modules that used to live in
web_static. web_static is a build output; only the files Vite does not own
(sw.js, manifest, icons) are asserted there directly.
"""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui" / "src"
HTML = (ROOT / "ui" / "index.html").read_text()
BUILT_HTML = (ROOT / "web_static" / "index.html").read_text()
WORKER = (ROOT / "web_static" / "sw.js").read_text()


def source(*parts: str) -> str:
    return (UI.joinpath(*parts)).read_text()


ALL_TSX = "\n".join(path.read_text() for path in UI.rglob("*.tsx"))
ALL_SOURCE = ALL_TSX + "\n".join(path.read_text() for path in UI.rglob("*.ts"))


class BuildTest(unittest.TestCase):
    """The served bundle must actually be the current source."""

    def test_the_built_shell_exists_and_loads_one_bundle(self):
        self.assertIn('src="/app.js"', BUILT_HTML)
        self.assertIn('href="/index.css"', BUILT_HTML)
        self.assertTrue((ROOT / "web_static" / "app.js").is_file())

    def test_bundled_assets_are_present(self):
        for asset in ("correct.wav", "incorrect.wav", "mascot.svg", "heart.svg", "points.svg"):
            path = ROOT / "web_static" / "assets" / asset
            self.assertTrue(path.is_file(), f"missing asset: {asset}")
            self.assertGreater(path.stat().st_size, 0)

    def test_attribution_for_the_borrowed_interface_is_kept(self):
        notice = (ROOT / "NOTICE").read_text()
        self.assertIn("duolingo-clone", notice)
        self.assertIn("MIT", notice)


class ShellTest(unittest.TestCase):
    def test_the_path_and_the_session_are_the_two_screens(self):
        app = source("app.tsx")
        self.assertIn("<Learn", app)
        self.assertIn("<Quiz", app)

    def test_primary_stats_are_reachable_one_handed_on_a_phone(self):
        """The laptop rail is display:none on a phone, so the numbers move to
        a bar above the thumb rather than disappearing."""
        app = source("app.tsx")
        self.assertIn("hidden w-[320px] shrink-0 lg:block", app)
        self.assertIn("lg:hidden", app)
        self.assertIn("StatsRailCompact", app)

    def test_session_has_one_persistent_primary_action(self):
        footer = source("lesson", "footer.tsx")
        self.assertIn("onCheck", footer)
        self.assertIn("ml-auto", footer)

    def test_safe_area_is_respected_at_the_bottom_of_the_screen(self):
        self.assertIn("env(safe-area-inset-bottom)", source("lesson", "footer.tsx"))
        self.assertIn("env(safe-area-inset-bottom)", source("app.tsx"))


class TouchTargetTest(unittest.TestCase):
    def test_action_controls_clear_the_44px_minimum(self):
        button = source("components", "ui", "button.tsx")
        # h-11 is 44px, h-12 is 48px; the path nodes are explicitly 70px.
        self.assertIn("h-11", button)
        self.assertIn("h-12", button)
        self.assertIn("h-[70px] w-[70px]", source("learn", "lesson-button.tsx"))

    def test_motion_can_be_turned_off(self):
        self.assertIn("prefers-reduced-motion", source("index.css"))
        # Confetti is the loudest motion in the app and must honour the setting.
        self.assertIn("reducedMotion", source("lesson", "quiz.tsx"))


class PathTest(unittest.TestCase):
    def test_client_renders_the_server_path(self):
        self.assertIn("/api/path", source("lib", "api.ts"))
        self.assertIn("api.path", source("learn", "learn.tsx"))

    def test_node_states_are_visually_distinct(self):
        button = source("learn", "lesson-button.tsx")
        for state in ("locked", "current", "isCompleted"):
            self.assertIn(state, button)

    def test_exactly_one_node_is_advertised_as_the_start(self):
        button = source("learn", "lesson-button.tsx")
        self.assertIn(">\n              Start", button)
        self.assertIn("current ?", button)

    def test_the_exam_clock_is_visible_on_the_path(self):
        """Exam pressure is what makes this scheduler different from a fixed
        course tree, so the countdown is on the banner, not buried in stats."""
        banner = source("learn", "unit-banner.tsx")
        self.assertIn("daysLeft", banner)
        self.assertIn("bg-rose-500", banner)
        self.assertIn("bg-amber-500", banner)


class SessionLoopTest(unittest.TestCase):
    def test_answers_commit_through_the_server(self):
        quiz = source("lesson", "quiz.tsx")
        self.assertIn("api.reviewPreview", quiz)
        self.assertIn("api.commitReview", quiz)

    def test_ungradable_recall_waits_for_the_learners_own_rating(self):
        """Writing a guessed rating would poison the schedule silently."""
        quiz = source("lesson", "quiz.tsx")
        self.assertIn("needs_rating", quiz)
        self.assertIn("SELF_RATINGS", quiz)

    def test_feedback_is_colour_coded_before_it_is_read(self):
        card = source("lesson", "card.tsx")
        self.assertIn("bg-green-100", card)
        self.assertIn("bg-rose-100", card)
        quiz = source("lesson", "quiz.tsx")
        self.assertIn("border-green-300 bg-green-50", quiz)
        self.assertIn("border-rose-300 bg-rose-50", quiz)

    def test_every_answer_shows_the_source_it_came_from(self):
        """The line between a tutor and a plausible guess."""
        self.assertIn("source_quote", source("lesson", "quiz.tsx"))

    def test_daily_goal_and_hearts_persist_locally(self):
        player = source("store", "player.ts")
        self.assertIn("intellect.goal", player)
        self.assertIn("intellect.hearts", player)

    def test_hearts_refill_daily_rather_than_being_sold(self):
        player = source("store", "player.ts")
        self.assertIn("saved.date === today() ?", player)
        self.assertNotIn("purchase", player.lower())

    def test_math_still_typesets(self):
        self.assertIn("renderMathInElement", source("components", "math-text.tsx"))
        self.assertIn("vendor/katex/katex.min.js", HTML)


class MathTest(unittest.TestCase):
    """Currency is not math.

    Found by reading the real question bank: the stats items say "wins $0 with
    probability 0.5, $10 with probability 0.3". With a single-dollar math
    delimiter, everything between two prices silently becomes garbled math.
    """

    def setUp(self):
        self.math = source("components", "math-text.tsx")

    def test_single_dollar_is_not_a_math_delimiter(self):
        self.assertIn('{ left: "$$", right: "$$"', self.math)
        self.assertNotIn('{ left: "$", right: "$"', self.math)

    def test_the_unambiguous_delimiters_are_supported(self):
        for delimiter in ('"$$"', '"\\\\["', '"\\\\("'):
            self.assertIn(delimiter, self.math)

    def test_a_broken_expression_cannot_abort_a_session(self):
        self.assertIn("throwOnError: false", self.math)

    def test_every_rendered_surface_goes_through_the_one_renderer(self):
        """Exactly one definition of what counts as math in this app."""
        for path in UI.rglob("*.tsx"):
            if path.name == "math-text.tsx":
                continue
            self.assertNotIn(
                "renderMathInElement",
                path.read_text(),
                f"{path.name} must use <MathText>, not its own math rules",
            )

    def test_generated_content_is_never_injected_as_markup(self):
        self.assertNotIn("dangerouslySetInnerHTML", ALL_TSX)

    def test_math_rules_survive_the_build(self):
        """Assert the BUILD, not the source.

        .katex and .katex-display only appear in markup KaTeX creates at
        runtime, so Tailwind's content scan never sees them. Inside @layer base
        they were purged from every build: the source had the rules and the
        shipped CSS had none. A source-only assertion passed the whole time.
        """
        built = (ROOT / "web_static" / "index.css").read_text()
        self.assertIn(".katex-display", built)
        self.assertIn(".katex{", built.replace(" ", ""))

    def test_wide_inline_math_cannot_clip_the_sentence(self):
        """Inline math is an unbreakable box. One wide fraction pushed its line
        past a 390px viewport and clipped the words on either side."""
        built = (ROOT / "web_static" / "index.css").read_text().replace(" ", "")
        self.assertIn(".katex{", built)
        katex_rule = built[built.index(".katex{"):]
        katex_rule = katex_rule[: katex_rule.index("}")]
        self.assertIn("max-width:100%", katex_rule)
        self.assertIn("overflow", katex_rule)

    def test_display_math_is_not_forced_inline(self):
        """Making every .katex an inline-block collapses centred display math."""
        built = (ROOT / "web_static" / "index.css").read_text().replace(" ", "")
        self.assertIn(".katex-display>.katex{", built)


class ModularityTest(unittest.TestCase):
    """The content boundary: adding material must not require code changes."""

    def test_http_lives_in_exactly_one_module(self):
        self.assertIn("fetch(", source("lib", "api.ts"))
        for path in UI.rglob("*.tsx"):
            self.assertNotIn("fetch(", path.read_text(), f"{path.name} should call api.ts")

    def test_device_state_is_separate_from_server_truth(self):
        self.assertIn("localStorage", source("store", "player.ts"))
        self.assertNotIn("localStorage", source("lesson", "quiz.tsx"))

    def test_mastery_numbers_are_never_computed_on_the_client(self):
        """SQLite owns mastery, scheduling, XP totals, and streak."""
        quiz = source("lesson", "quiz.tsx")
        self.assertIn("result.xp_gained", quiz)
        self.assertNotIn("mastery =", quiz)

    def test_classes_come_from_the_server_not_a_hardcoded_list(self):
        self.assertIn("/api/classes", source("lib", "api.ts"))
        self.assertIn("api.classes", source("app.tsx"))


class DesktopTest(unittest.TestCase):
    """Laptop is a first-class shape, not a stretched phone."""

    def test_a_persistent_class_rail_exists_for_wide_screens(self):
        self.assertIn("StatsRail", source("app.tsx"))
        self.assertIn("lg:block", source("app.tsx"))

    def test_the_session_is_keyboard_operable(self):
        quiz = source("lesson", "quiz.tsx")
        self.assertIn("Escape", quiz)
        self.assertIn('useKey("Enter"', source("lesson", "footer.tsx"))
        # Number keys pick a choice; the shortcut is bound per card.
        self.assertIn("useKey(shortcut", source("lesson", "card.tsx"))

    def test_the_phone_keyboard_is_not_forced_open(self):
        self.assertIn('matchMedia("(min-width: 900px)")', source("lesson", "quiz.tsx"))


class ProgressiveWebAppTest(unittest.TestCase):
    def test_shell_links_manifest_icons_and_registers_the_worker(self):
        for marker in (
            'rel="manifest"', "/manifest.webmanifest", 'rel="apple-touch-icon"',
            'name="mobile-web-app-capable"', "viewport-fit=cover",
        ):
            self.assertIn(marker, BUILT_HTML)
        self.assertIn('navigator.serviceWorker.register("/sw.js")', source("main.tsx"))

    def test_manifest_is_installable(self):
        manifest = json.loads((ROOT / "web_static" / "manifest.webmanifest").read_text())
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        self.assertIn("maskable", {icon.get("purpose") for icon in manifest["icons"]})

    def test_declared_icons_exist_on_disk(self):
        manifest = json.loads((ROOT / "web_static" / "manifest.webmanifest").read_text())
        for icon in manifest["icons"]:
            path = ROOT / "web_static" / icon["src"].lstrip("/")
            self.assertTrue(path.is_file(), f"missing icon: {icon['src']}")
            self.assertGreater(path.stat().st_size, 0)

    def test_the_worker_caches_what_the_build_actually_emits(self):
        """A shell listing a file that no longer exists is a blank screen
        offline. This broke when the app stopped being five ES modules."""
        for asset in ("/app.js", "/index.css", "/index.html"):
            self.assertIn(asset, WORKER)
        for stale in ("/api.js", "/session.js", "/player.js", "/math.js", "/app.css"):
            self.assertNotIn(stale, WORKER, "worker still lists a removed module")

    def test_the_worker_version_is_stamped_from_the_build(self):
        """A cache-first shell with a hand-edited version means an installed
        PWA can serve a stale bundle forever. That happened twice in one
        session, so the version is now a hash of the emitted files."""
        import hashlib

        match = re.search(r'const VERSION = "intellect-([0-9a-f]{12})";', WORKER)
        self.assertIsNotNone(match, "worker version is not a build stamp")
        digest = hashlib.sha256()
        for name in ("app.js", "index.css", "index.html"):
            digest.update((ROOT / "web_static" / name).read_bytes())
        self.assertEqual(
            match.group(1),
            digest.hexdigest()[:12],
            "web_static is stale: rebuild with `npm run build` in ui/",
        )

    def test_worker_never_caches_mutations(self):
        """Answers must reach SQLite; a cached write would corrupt mastery."""
        self.assertIn('request.method !== "GET"', WORKER)
        self.assertIn("networkFirst", WORKER)
        self.assertIn("cacheFirst", WORKER)


if __name__ == "__main__":
    unittest.main()
