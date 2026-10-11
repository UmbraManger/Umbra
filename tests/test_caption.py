"""The native window is frameless: the page draws the title bar and the backend
owns the buttons behind it (minimize / maximize / close / resize grip).

`caption_colors()` still matters — it becomes the window's background_color, so
the app never flashes white before the page paints.
"""
import importlib

import db
from .helpers import IsolatedCase

_main = None


class _MainCase(IsolatedCase):
    """Imports the entry point only after the temp data dir is in place."""

    def setUp(self):
        super().setUp()
        global _main
        if _main is None:
            try:
                _main = importlib.import_module("main")
            except Exception as e:            # pragma: no cover
                self.skipTest(f"backend entry point not importable: {e}")


class _FakeWindow:
    """Stands in for the pywebview Window the controls call into."""

    def __init__(self):
        self.calls = []

    def minimize(self): self.calls.append("minimize")
    def maximize(self): self.calls.append("maximize")
    def restore(self): self.calls.append("restore")
    def destroy(self): self.calls.append("destroy")
    def resize(self, w, h, *a): self.calls.append(("resize", w, h))


class WindowBackgroundTests(_MainCase):

    def test_background_defaults_to_the_dark_shell(self):
        self.assertEqual(_main.caption_colors(), ("#100e0a", "#ece4d3"))

    def test_background_follows_the_light_theme(self):
        db.save_settings({**db.get_settings(), "theme": "light"})
        self.assertEqual(_main.caption_colors(), ("#f1ecdf", "#26200f"))

    def test_background_follows_every_swatch(self):
        for swatch in ("#141210", "#1b1420", "#10141a", "#151a14", "#f1ecdf"):
            db.save_settings({**db.get_settings(), "adv": {"background": swatch}})
            bg, fg = _main.caption_colors()
            self.assertEqual(bg, swatch.lower())
            self.assertEqual(fg, "#ece4d3", "the text stays on-theme (dark)")

    def test_a_junk_background_falls_back_to_the_theme_colour(self):
        db.save_settings({**db.get_settings(), "adv": {"background": "javascript:0"}})
        self.assertEqual(_main.caption_colors()[0], "#100e0a")


class WinControlsTests(_MainCase):
    """The buttons the drawn title bar calls through the pywebview js_api."""

    def controls(self):
        c = _main._WinControls()
        c._window = _FakeWindow()
        return c

    def test_the_api_surface_is_only_the_four_buttons(self):
        """pywebview walks the js_api with dir()/getattr() and recurses into any
        public object — a public window attribute would publish the whole Window
        (evaluate_js, destroy, ...) into the page."""
        c = _main._WinControls()
        public = {n for n in dir(c) if not n.startswith("_")}
        self.assertEqual(public, {"minimize", "toggle_max", "resize_to", "close"})

    def test_minimize_and_close_reach_the_window(self):
        c = self.controls()
        c.minimize()
        c.close()
        self.assertEqual(c._window.calls, ["minimize", "destroy"])

    def test_toggle_max_alternates_maximize_and_restore(self):
        c = self.controls()
        c.toggle_max()
        c.toggle_max()
        self.assertEqual(c._window.calls, ["maximize", "restore"])

    def test_resize_to_clamps_to_the_minimum_window_size(self):
        c = self.controls()
        c.resize_to(400, 300)
        c.resize_to(1200, 900)
        self.assertEqual(c._window.calls,
                         [("resize", 960, 640), ("resize", 1200, 900)])

    def test_a_missing_window_never_raises(self):
        c = _main._WinControls()
        c.minimize()
        c.toggle_max()
        c.resize_to(100, 100)
        c.close()

