import os
import unittest
from unittest import mock

import server
from .helpers import IsolatedCase


class OfficialSweepTests(IsolatedCase):
    """Bulk web routing: the bundled official-sites catalog is swept first and
    a loose match (e.g. Brazzers' broad search picking another scene) is
    rejected instead of applied."""

    def test_official_catalog_lists_the_big_studios(self):
        import official_sites
        d = {domain for domain, _ in official_sites.OFFICIAL_SITES}
        for expected in ("julesjordan.com", "elegantangel.com", "evilangel.com",
                         "brazzers.com", "naughtyamerica.com", "realitykings.com"):
            self.assertIn(expected, d)

    def test_low_coverage_result_is_rejected_and_engine_candied_next(self):
        with mock.patch.object(server.scraper_engine, "run_for_site") as rfs, \
             mock.patch.object(server, "search_web", return_value=[]):
            def route(u, **kw):
                if u == "brazzers.com":
                    return {"title": "Completely Unrelated Other Scene", "url": u}
                return {"notFound": True}
            rfs.side_effect = route
            # nothing covers the query → 'no match' error (empty search_web)
            with self.assertRaises(Exception):
                server.web_lookup("scene", "Totally Different Movie Title Here")

    def test_official_hit_with_matching_title_wins_and_is_tagged(self):
        with mock.patch.object(server.scraper_engine, "run_for_site") as rfs, \
             mock.patch.object(server, "search_web", return_value=[]):
            def route(u, **kw):
                if u == "julesjordan.com":
                    return {"title": "'Romeo And Juliet' With Nicole",
                            "url": "https://www.julesjordan.com/scene/1"}
                return {"notFound": True}
            rfs.side_effect = route
            got = server.web_lookup("scene", "Romeo And Juliet With Nicole")
        self.assertEqual(got.get("via"), "julesjordan.com")


class ScannerSelfHealTests(IsolatedCase):
    def test_a_marked_file_without_a_library_row_is_offered_again(self):
        """Records deleted through any path must not leave the file stuck as
        'imported' in the Import From Scan dialog."""
        v = self.tmpfile("lib/film.mp4")
        import db, scanner
        scanner.mark_done(v)
        r = server._scan_candidates([os.path.dirname(v)])
        self.assertTrue(all(f["imported"] is False for f in r), r)

    def test_marked_file_with_a_row_stays_imported(self):
        import scanner
        v = self.tmpfile("lib2/film2.mp4", b"v")
        scanner.mark_done(v)
        scanner.import_file(v, "movie", "Film 2")
        r = server._scan_candidates([os.path.dirname(v)])
        self.assertTrue(all(f["imported"] for f in r), r)
