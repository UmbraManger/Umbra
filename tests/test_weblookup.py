import json
import net_guard
import unittest
from unittest import mock

import server
from .helpers import IsolatedCase


BING_RSS = ('<rss><channel><item><title>A</title>'
            '<link>https://www.officialsite.com/scene/123</link></item>'
            '<item><title>B</title>'
            '<link>https://some-aggregator.com/x</link></item>'
            '</channel></rss>')
DDG_HTML = ('<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.other.com%2Fvideo%2F9'
            '&amp;rut=abc">hit</a>')


class SearchWebTests(IsolatedCase):
    def test_bing_results_are_parsed_and_skips_its_own_domain(self):
        with mock.patch.object(server, "safe_get") as g:
            g.return_value = mock.Mock(status_code=200, text=BING_RSS)
            got = server.search_web("Some Title Here")
        urls = [u for u in got]
        self.assertIn("https://www.officialsite.com/scene/123", urls)
        self.assertFalse(any("bing." in u for u in urls))

    def test_duckduckgo_uddg_hits_are_unescaped(self):
        with mock.patch.object(server, "safe_get") as g:
            g.return_value = mock.Mock(status_code=200, text=DDG_HTML)
            got = server.search_web("q")
        self.assertIn("https://www.other.com/video/9", got)


class WebLookupTests(IsolatedCase):
    def test_routes_the_first_candidate_an_installed_scraper_covers(self):
        with mock.patch.object(server, "search_web", return_value=[
                "https://www.aggregator.com/a", "https://official.com/v/1"]), \
             mock.patch.object(server.scraper_engine, "run_for_site") as rfs:
            def route(u, **kw):
                src = u if isinstance(u, str) else ""
                if "official.com" in src:
                    return {"title": "Real Scene", "date": "2020-01-01"}
                raise ValueError("no scraper installed for aggregator.com")
            rfs.side_effect = route
            got = server.web_lookup("scene", "Some Title")
        self.assertEqual(got["title"], "Real Scene")
        self.assertEqual(got["via"], "official.com")

    def test_no_candidates_is_a_404_that_the_caller_falls_back_from(self):
        with mock.patch.object(server, "search_web", return_value=[]):
            with self.assertRaises(Exception):
                server.web_lookup("scene", "Nothing To See")
