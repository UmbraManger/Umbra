"""The native title bar must follow the app instead of glaring white.

Windows 10 (build 19045 and older) rejects DWMWA_CAPTION_COLOR (35) and
DWMWA_TEXT_COLOR (36) with E_INVALIDARG, so here the immersive-dark fallback is
what actually paints the bar. The 'white title bar' bug: the colour converter
choked on the leading '#', the bare `except` swallowed it, and the immersive
fallback was skipped too — so nothing was applied at all.
"""
import importlib

import db
from .helpers import IsolatedCase

_main = None


class CaptionColorTests(IsolatedCase):

    def setUp(self):
        super().setUp()
        global _main
        if _main is None:
            try:
                _main = importlib.import_module("main")
            except Exception as e:            # pragma: no cover
                self.skipTest(f"backend entry point not importable: {e}")

    def test_colorref_is_bgr_and_tolerates_a_missing_hash(self):
        self.assertEqual(_main.colorref("#100e0a"), 0x000A0E10)   # 0x00BBGGRR
        self.assertEqual(_main.colorref("100e0a"), 0x000A0E10)

    def test_colorref_expands_short_hex(self):
        self.assertEqual(_main.colorref("#fff"), 0x00FFFFFF)
        self.assertEqual(_main.colorref("#f00"), 0x000000FF)

    def test_colorref_returns_none_instead_of_raising(self):
        """A stray settings value must not take the whole repaint down."""
        self.assertIsNone(_main.colorref("not a colour"))
        self.assertIsNone(_main.colorref("#12345"))
        self.assertIsNone(_main.colorref("#zzzzzz"))

    def test_caption_defaults_to_the_dark_shell(self):
        self.assertEqual(_main.caption_colors(), ("#100e0a", "#ece4d3"))

    def test_caption_follows_the_light_theme(self):
        db.save_settings({**db.get_settings(), "theme": "light"})
        self.assertEqual(_main.caption_colors(), ("#f1ecdf", "#26200f"))

    def test_caption_follows_every_background_swatch(self):
        for swatch in ("#141210", "#1b1420", "#10141a", "#151a14", "#f1ecdf"):
            db.save_settings({**db.get_settings(), "adv": {"background": swatch}})
            bg, fg = _main.caption_colors()
            self.assertEqual(bg, swatch.lower())
            self.assertEqual(fg, "#ece4d3", "the caption text stays on-theme (dark)")

    def test_a_junk_background_falls_back_to_the_theme_colour(self):
        db.save_settings({**db.get_settings(), "adv": {"background": "javascript:0"}})
        self.assertEqual(_main.caption_colors()[0], "#100e0a")

    def test_is_dark_drives_the_fallback_the_bar_actually_uses(self):
        self.assertTrue(_main.is_dark("#100e0a"))     # Ink & Amber
        self.assertTrue(_main.is_dark("#1b1420"))     # Plum swatch
        self.assertFalse(_main.is_dark("#f1ecdf"))    # Parchment / light theme
        self.assertTrue(_main.is_dark("rubbish"))     # garbage -> dark, never white
