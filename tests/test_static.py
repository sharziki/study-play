import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StaticAppTest(unittest.TestCase):
    def test_shell_has_keyboard_first_dashboard_and_accessible_dialog(self):
        html = (ROOT / "web_static" / "index.html").read_text()
        self.assertIn('id="start-sprint"', html)
        self.assertIn('id="study-view"', html)
        self.assertIn('id="import-dialog"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('id="answer-input"', html)

    def test_shell_has_first_principles_lesson_checks_and_audio_controls(self):
        html = (ROOT / "web_static" / "index.html").read_text()
        script = (ROOT / "web_static" / "app.js").read_text()
        for marker in (
            'id="lesson-view"', 'id="lesson-primitives"', 'id="lesson-derivation"',
            'id="worked-example"', 'id="lesson-checks"', 'id="sound-toggle"',
            'id="volume-control"', 'aria-live="polite"',
        ):
            self.assertIn(marker, html)
        self.assertIn("AudioContext", script)
        self.assertIn("localStorage", script)
        self.assertIn("/api/lesson-check", script)

    def test_local_math_and_pangram_fonts_are_wired(self):
        html = (ROOT / "web_static" / "index.html").read_text()
        css = (ROOT / "web_static" / "app.css").read_text()
        script = (ROOT / "web_static" / "app.js").read_text()
        for asset in (
            "vendor/katex/katex.min.css", "vendor/katex/katex.min.js",
            "vendor/katex/auto-render.min.js",
        ):
            self.assertIn(asset, html)
        self.assertIn("PPEditorialOld-Regular.woff2", css)
        self.assertIn("PPEditorialSans-Medium.woff2", css)
        self.assertIn("renderMathInElement", script)
        self.assertIn("step-explanation", script)
        for name in (
            "PPEditorialOld-Regular.woff2", "PPEditorialOld-Italic.woff2",
            "PPEditorialSans-Medium.woff2", "PPWriter-RegularText.woff2",
        ):
            self.assertTrue((ROOT / "web_static" / "fonts" / name).is_file())

    def test_study_chamber_is_single_viewport_and_swaps_to_feedback(self):
        css = (ROOT / "web_static" / "app.css").read_text()
        script = (ROOT / "web_static" / "app.js").read_text()
        self.assertIn("body:has(#study-view.is-visible)", css)
        self.assertIn("height: 100dvh", css)
        self.assertIn(".challenge-shell.has-feedback", css)
        self.assertIn('classList.add("has-feedback")', script)
        self.assertIn('classList.remove("has-feedback")', script)

    def test_assets_define_focus_mobile_and_reduced_motion_states(self):
        css = (ROOT / "web_static" / "app.css").read_text()
        self.assertIn(":focus-visible", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("@media (max-width: 720px)", css)
        js = (ROOT / "web_static" / "app.js").read_text()
        self.assertIn("startSprint", js)
        self.assertIn("commitReview", js)
        self.assertIn("keydown", js)


if __name__ == "__main__":
    unittest.main()
