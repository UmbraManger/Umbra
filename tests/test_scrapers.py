import os
from unittest import mock

import db
import scrapers
from .helpers import IsolatedCase

PY_SCRAPER = b'def scrape(title="", url=""):\n    return {"title": title.upper()}\n'
PY_KWARGS = b'def scrape(**kw):\n    return {"kw": sorted(kw)}\n'
YAML = b"""
search: {url: "https://example.test/search?q={title}"}
fields:
  title:    {selector: "h1.title",  attr: text}
  year:     {selector: "span.year", attr: text, transform: int}
  poster_f: {selector: "img.poster", attr: src}
"""
HTML = ('<h1 class="title">Alpha</h1><span class="year">Released 1999</span>'
        '<img class="poster" src="http://x.test/p.jpg">')


class FakeResponse:
    text = HTML
    def raise_for_status(self): pass


class ManagementTests(IsolatedCase):
    def test_only_py_and_yaml_are_accepted(self):
        with self.assertRaises(ValueError):
            scrapers.add("evil.exe", b"x", "movie")

    def test_add_list_toggle_remove(self):
        sid = scrapers.add("site.yml", YAML, "movie")
        [entry] = scrapers.list_all()
        self.assertTrue(entry["exists"] and entry["enabled"] and entry["size"] > 0)
        scrapers.toggle(sid)
        self.assertFalse(scrapers.list_all()[0]["enabled"])
        with self.assertRaises(ValueError):
            scrapers.run_by_id(sid, title="x")               # disabled
        scrapers.remove(sid)
        self.assertEqual(scrapers.list_all(), [])
        self.assertEqual(os.listdir(db.SCRAPER_DIR), ["meta.json"])


class PythonScraperTests(IsolatedCase):
    def test_python_scrapers_are_off_by_default(self):
        sid = scrapers.add("s.py", PY_SCRAPER, "movie")
        with self.assertRaisesRegex(ValueError, "disabled"):
            scrapers.run_by_id(sid, title="abc")

    def test_enabled_scraper_runs_and_only_gets_kwargs_it_accepts(self):
        db.save_settings({"pyScrapers": True})
        sid = scrapers.add("s.py", PY_SCRAPER, "movie")
        self.assertEqual(scrapers.run_by_id(sid, title="abc", kind="movie", domain="d"),
                         {"title": "ABC"})
        sid2 = scrapers.add("k.py", PY_KWARGS, "movie")
        self.assertEqual(scrapers.run_by_id(sid2, title="a", kind="movie", domain="d")["kw"],
                         ["domain", "kind", "title", "url"])


class YamlScraperTests(IsolatedCase):
    def test_selectors_and_transforms(self):
        sid = scrapers.add("site.yml", YAML, "movie")
        with mock.patch.object(scrapers.requests, "get", return_value=FakeResponse()) as g:
            out = scrapers.run_by_id(sid, title="My Title")
        self.assertEqual(out, {"title": "Alpha", "year": 1999,
                               "poster_f": "http://x.test/p.jpg"})
        self.assertIn("My%20Title", g.call_args.args[0])

    def test_needs_url_or_search_template(self):
        p = self.tmpfile("bare.yml", b"fields: {}")
        with self.assertRaises(ValueError):
            scrapers.run_yaml(p, title="x")


class SiteRoutingTests(IsolatedCase):
    def test_no_matching_scraper_is_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, "no scraper installed"):
            scrapers.run_for_site("https://nothing.example/x", title="t")

    def test_scraper_named_after_host_is_used(self):
        db.save_settings({"pyScrapers": True})
        scrapers.add("shop.example.py", PY_SCRAPER, "movie")
        out = scrapers.run_for_site("https://shop.example/x", title="t")
        self.assertEqual(out, {"title": "T"})

    def test_host_match_is_not_a_substring_match(self):
        """Regression (analysis D6, fixed): host routing is dot-boundary exact, so
        'ex.com' no longer matches a scraper named 'apex.com.py'."""
        db.save_settings({"pyScrapers": True})
        scrapers.add("apex.com.py", PY_SCRAPER, "movie")
        with self.assertRaises(ValueError):
            scrapers.run_for_site("https://ex.com/x", title="t")


class KnownBugTests(IsolatedCase):
    def test_remove_cannot_delete_files_outside_the_scraper_folder(self):
        """Regression (analysis #4, fixed): meta.json's 'file' is validated as a
        bare name inside the scraper dir, so a crafted/restored entry cannot make
        remove() delete '../victim'."""
        victim = os.path.join(db.DATA_DIR, "victim.txt")
        with open(victim, "w") as f:
            f.write("keep me")
        scrapers._save_meta([{"id": "x1", "name": "x.py", "file": "../victim.txt",
                              "type": "python", "kind": "movie", "enabled": True}])
        scrapers.remove("x1")
        self.assertTrue(os.path.exists(victim))
