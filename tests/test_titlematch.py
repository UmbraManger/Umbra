import unittest

import titlematch


class TokenCoverageTests(unittest.TestCase):
    def test_punctuation_and_symbols_are_ignored(self):
        """Windows filenames cannot carry ':' '|' '?''*', so an imported
        'Case 2 Big Trouble' must score the site's 'Case 2: Big Trouble'
        at full coverage (regression: bulk fetch picked wrong scenes)."""
        self.assertEqual(titlematch.coverage("Case 2 Big Trouble", "Case 2: Big Trouble"), 1.0)
        self.assertEqual(titlematch.coverage("Sophie's First", "Sophies First"), 1.0)

    def test_best_prefers_the_full_token_cover(self):
        cands = [
            {"title": "Late Night With Naomi", "url": "u1"},
            {"title": "Naomi Banx: First Chase", "url": "u2"},
        ]
        self.assertEqual(titlematch.best(cands, "Naomi Banx First Chase")["url"], "u2")

    def test_best_falls_back_to_site_order_without_overlap(self):
        cands = [{"title": "Unrelated Title A", "url": "u1"},
                 {"title": "Unrelated Title B", "url": "u2"}]
        # none of these cover half the query — keep the site's own ranking
        self.assertIs(titlematch.best(cands, "Totally Different Query"), cands[0])

    def test_best_passes_through_non_lists(self):
        self.assertIsNone(titlematch.best(None, "x"))
        self.assertEqual(titlematch.best([], "x"), [])
        self.assertEqual(titlematch.best({"title": "One"}, "One"), {"title": "One"})
