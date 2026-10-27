"""ManyVids bundled scraper - offline checks of its parsing helpers."""

import importlib.util
import os
import unittest

from bs4 import BeautifulSoup

_SPEC = importlib.util.spec_from_file_location(
    "umbra_manyvids_scraper",
    os.path.join(os.path.dirname(__file__), "..", "scrapers", "manyvids.py"))
mv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mv)


class TagTests(unittest.TestCase):
    MARKUP = '<a class="TagHashX__mavTag" data-event-category="Engagements" ' \
             'data-event-label="BigAss" href="/Vids/bigass">#BigAss</a>'

    def test_camel_case_split_and_dedupe(self):
        soup = BeautifulSoup(self.MARKUP +
                             '<a data-event-category="Engagements" data-event-label="Twerk" href="/Vids/twerk">#Twerk</a>' +
                             '<a data-event-category="Engagements" data-event-label="BigAss" href="/Vids/bigass">#BigAss</a>',
                             "html.parser")
        self.assertEqual(mv._tags(soup), ["Big Ass", "Twerk"])

    def test_slug_mismatch_dropped(self):
        soup = BeautifulSoup(
            '<a data-event-category="Engagements" data-event-label="GUEST" href="#">#GUEST</a>' +
            '<a data-event-category="Engagements" data-event-label="Anal" href="/Vids/anal">#Anal</a>',
            "html.parser")
        self.assertEqual(mv._tags(soup), ["Anal"])


class SearchCardTests(unittest.TestCase):
    def test_aria_label_title(self):
        soup = BeautifulSoup(
            '<a href="/Video/1/x" aria-label="Night Ride by Kira on ManyVids.">x</a>',
            "html.parser")
        results = mv._search_cards(soup)
        self.assertEqual(results, [{"title": "Night Ride", "url": "https://www.manyvids.com/Video/1/x"}])


if __name__ == "__main__":
    unittest.main()
