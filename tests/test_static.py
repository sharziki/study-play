"""Coverage for the mobile study surface.

These assert the properties that make the app usable on a phone with one
thumb, not the existence of particular markup. Each one corresponds to a
design rule that broke something real when it was violated.
"""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web_static" / "index.html").read_text()
CSS = (ROOT / "web_static" / "app.css").read_text()
JS = (ROOT / "web_static" / "app.js").read_text()


class ShellTest(unittest.TestCase):
    def test_every_primary_screen_exists(self):
        for screen in ("screen-path", "screen-review", "screen-library", "screen-you", "screen-session"):
            self.assertIn(f'id="{screen}"', HTML)

    def test_navigation_is_a_thumb_reachable_tab_bar(self):
        self.assertIn('class="tabbar"', HTML)
        self.assertNotIn("<aside", HTML, "a sidebar is unreachable one-handed on a phone")
        self.assertIn(".tabbar {", CSS)

    def test_path_screen_renders_without_javascript(self):
        """The shell must paint before app.js runs, or a slow phone shows nothing."""
        self.assertIn('class="screen is-active" id="screen-path"', HTML)

    def test_session_has_one_persistent_primary_action(self):
        self.assertIn('id="session-action"', HTML)
        self.assertIn("btn-primary btn-block", HTML)

    def test_import_dialog_is_reachable_and_accessible(self):
        self.assertIn('id="import-dialog"', HTML)
        self.assertIn('aria-live="polite"', HTML)


class TouchTargetTest(unittest.TestCase):
    def test_action_controls_clear_the_44px_minimum(self):
        for rule in ("min-height: 52px", "min-height: 56px", "min-height: 60px"):
            self.assertIn(rule, CSS)

    def test_narrow_phones_get_a_tightened_path(self):
        self.assertIn("@media (max-width: 380px)", CSS)

    def test_motion_can_be_turned_off(self):
        self.assertIn("prefers-reduced-motion", CSS)

    def test_dark_mode_is_handled(self):
        self.assertIn("prefers-color-scheme: dark", CSS)


class PathTest(unittest.TestCase):
    def test_client_renders_the_server_path(self):
        self.assertIn("/api/path", JS)
        self.assertIn("renderPath", JS)

    def test_node_states_are_visually_distinct(self):
        for rule in (".node.is-complete", ".node.is-locked", ".node.is-current", ".node.is-next", ".node.is-open"):
            self.assertIn(rule, CSS)

    def test_exactly_one_node_is_advertised_as_the_start(self):
        self.assertIn('textContent = "START"', JS)
        self.assertIn(".node-start", CSS)


class SessionLoopTest(unittest.TestCase):
    def test_answers_commit_through_the_server(self):
        self.assertIn("/api/review-preview", JS)
        self.assertIn("/api/reviews", JS)

    def test_missed_items_return_before_the_set_ends(self):
        self.assertIn("session.questions.push(question)", JS)

    def test_feedback_is_colour_coded_before_it_is_read(self):
        for rule in (".choice.is-right", ".choice.is-wrong", ".verdict.is-right", ".verdict.is-wrong"):
            self.assertIn(rule, CSS)

    def test_daily_goal_and_hearts_persist_locally(self):
        self.assertIn("intellect.goal", JS)
        self.assertIn("intellect.hearts", JS)

    def test_hearts_refill_daily_rather_than_being_sold(self):
        self.assertIn("if (saved.date !== today()) return MAX_HEARTS;", JS)

    def test_math_still_typesets(self):
        self.assertIn("renderMathInElement", JS)
        self.assertIn("vendor/katex/katex.min.js", HTML)


class ProgressiveWebAppTest(unittest.TestCase):
    def test_shell_links_manifest_icons_and_registers_the_worker(self):
        for marker in (
            'rel="manifest"', "/manifest.webmanifest", 'rel="apple-touch-icon"',
            'name="mobile-web-app-capable"', "viewport-fit=cover",
        ):
            self.assertIn(marker, HTML)
        self.assertIn('navigator.serviceWorker.register("/sw.js")', JS)

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

    def test_worker_never_caches_mutations(self):
        """Answers must reach SQLite; a cached write would corrupt mastery."""
        worker = (ROOT / "web_static" / "sw.js").read_text()
        self.assertIn('request.method !== "GET"', worker)
        self.assertIn("networkFirst", worker)
        self.assertIn("cacheFirst", worker)


if __name__ == "__main__":
    unittest.main()


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground: str, background: str) -> float:
    high, low = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ContrastTest(unittest.TestCase):
    """A gamified palette drifts bright. These floors keep it readable.

    Measured in a browser first: the original --green was 2.47:1 under white
    text, which fails even the large-text floor, so the button label was the
    least readable thing on the screen.
    """

    def _token(self, name: str) -> str:
        import re

        match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}})", CSS)
        self.assertIsNotNone(match, f"missing token {name}")
        return match.group(1)

    def test_white_text_on_the_primary_action_is_legible(self):
        self.assertGreaterEqual(contrast("#ffffff", self._token("--green")), 4.5)

    def test_white_text_on_secondary_fills_is_legible(self):
        for token in ("--blue", "--red"):
            self.assertGreaterEqual(contrast("#ffffff", self._token(token)), 4.5, token)

    def test_secondary_and_tertiary_text_clear_the_small_text_floor(self):
        wash = self._token("--wash")
        for token in ("--ink", "--ink-soft", "--ink-faint"):
            self.assertGreaterEqual(contrast(self._token(token), wash), 4.5, token)
