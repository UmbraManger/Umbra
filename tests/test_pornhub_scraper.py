"""Pornhub bundled scraper - offline checks of its parsing helpers.

Imports the scraper file directly (no network) and feeds it fabricated soup.
"""

import importlib.util
import os
import unittest

from bs4 import BeautifulSoup

_SPEC = importlib.util.spec_from_file_location(
    "umbra_pornhub_scraper",
    os.path.join(os.path.dirname(__file__), "..", "scrapers", "pornhub.py"))
ph = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ph)


class DurationTests(unittest.TestCase):
    def test_iso_pt(self):
        self.assertEqual(ph._duration_min("PT00H12M26S"), 12)

    def test_hours(self):
        self.assertEqual(ph._duration_min("PT1H00M00S"), 60)

    def test_garbage(self):
        self.assertIsNone(ph._duration_min("not a duration"))


class MatchTests(unittest.TestCase):
    def test_exact_and_punctuation_normalized(self):
        q = "Stepbro! Help Me Take Pics"
        self.assertEqual(ph._match_score(q, "Stepbro Help Me Take Pics"), (0, 0))

    def test_overlap_never_below_exact(self):
        # overlap > 10 used to produce negative scores outranking exact
        q = "a b c d e f g h i j k l"
        t = "a b c d e f g h i j k l m n o p"
        self.assertLess(ph._match_score(q, q), ph._match_score(q, t))


class PerformerTests(unittest.TestCase):
    def test_pornstar_chips(self):
        soup = BeautifulSoup(
            '<div class="video-info-row js-suggestionsRow">'
            '<div class="pornstarsWrapper"><p>Pornstars</p>'
            '<a data-label="pornstar">Rae Lil Black</a>'
            '<a data-label="pornstar">Mick Blue</a>'
            '<a data-label="pornstar">Rae Lil Black</a></div></div>', "html.parser")
        self.assertEqual(ph._performers(soup), ["Rae Lil Black", "Mick Blue"])

    def test_nav_dropdown_is_not_cast(self):
        soup = BeautifulSoup(
            '<ul class="dropdownPornstarsList">'
            '<li class="performerCard"><a href="/pornstar/rae-lil-black" alt="Rae Lil Black"></a></li></ul>',
            "html.parser")
        self.assertEqual(ph._performers(soup), [])


class CategoryTests(unittest.TestCase):
    def test_categories_then_tags_case_insensitive(self):
        soup = BeautifulSoup(
            '<div><a data-label="category">Big Ass</a>'
            '<a data-label="category">HD Porn</a>'
            '<a data-label="tag"><span>big ass</span></a>'
            '<a data-label="tag"><span>creampie</span></a></div>', "html.parser")
        self.assertEqual(ph._categories(soup),
                         ["Big Ass", "HD Porn", "creampie"])


if __name__ == "__main__":
    unittest.main()
