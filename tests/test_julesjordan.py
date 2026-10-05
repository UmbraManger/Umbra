"""Regression: JulesJordan scene pages must not report the site's own
"Movies"/"DVDs" navigation as the scene's movie.

The scene form takes groups[0] as the movie title, so a nav link to the
movie listing used to fill the field with a label like "Movies" and file
the scene under a movie that never existed.
"""
import importlib.util
import os
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPER = os.path.join(ROOT, "scrapers", "julesjordan.py")

try:
    _spec = importlib.util.spec_from_file_location("obscura_julesjordan", SCRAPER)
    jj = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(jj)
    IMPORT_ERROR = None
except Exception as exc:                      # pragma: no cover
    jj = None
    IMPORT_ERROR = exc

requires_lxml = unittest.skipIf(jj is None, f"julesjordan scraper unavailable: {IMPORT_ERROR}")

URL = "https://www.julesjordan.com/trial/scenes/some-scene_vids.html"

NAV = """
<header><nav>
  <a href="/dvds/">DVDs</a>
  <a href="/movies/">Movies</a>
  <a href="/trial/scenes/">Scenes</a>
</nav></header>
"""


def scrape(html):
    # _find_card_thumbnail() walks live listing pages for a cover; the tests
    # only care about the fields parsed out of the given html.
    with mock.patch.object(jj, "_find_card_thumbnail", return_value=""):
        out = jj.scrape_scene_detail(URL, html=html)
    return out.get("groups")


@requires_lxml
class GroupExtractionTests(unittest.TestCase):
    def test_listing_nav_is_not_reported_as_a_movie(self):
        groups = scrape(f"<html><body>{NAV}<h1>Some Scene</h1></body></html>")
        self.assertIn(groups, (None, []))

    def test_real_movie_link_wins_over_the_nav_link(self):
        html = f"""<html><body>{NAV}
          <h1>Some Scene</h1>
          <div class="meta-item">Released<div>September 7, 2026</div></div>
          <div class="meta-item">Starring<div>
            <a href="/trial/models/x">Angela White</a></div></div>
          <div class="meta-item">Movie<div>
            <a href="/dvds/123/great-movie-title.html">Great Movie Title</a></div></div>
        </body></html>"""
        groups = scrape(html)
        self.assertEqual(groups[0]["name"], "Great Movie Title")
        self.assertTrue(groups[0]["url"].endswith("/dvds/123/great-movie-title.html"))

    def test_plain_text_movie_row_is_used_when_there_is_no_link(self):
        html = f"""<html><body>{NAV}
          <h1>Some Scene</h1>
          <div class="meta-item">Movie<div>Great Movie Title</div></div>
        </body></html>"""
        self.assertEqual(scrape(html), [{"name": "Great Movie Title"}])

    def test_footer_and_breadcrumb_index_links_are_ignored(self):
        html = """<html><body>
          <ul class="crumbs">
            <li><a href="/">Home</a></li>
            <li><a href="/dvds/">Movies</a></li>
            <li><a href="/dvds/123/great-movie-title.html">Great Movie Title</a></li>
          </ul>
          <h1>Some Scene</h1>
          <footer>
            <a href="/dvds/">DVDs</a>
            <a href="/movies/">Movies</a>
          </footer>
        </body></html>"""
        groups = scrape(html)
        self.assertEqual([g["name"] for g in groups], ["Great Movie Title"])

    def test_related_box_ranks_below_the_scene_details(self):
        html = """<html><body>
          <h1>Some Scene</h1>
          <div class="details">
            <a href="/movies/123/great-movie-title.html">Great Movie Title</a>
          </div>
          <div class="jj-related">
            <a href="/movies/999/other-movie.html">Other Movie</a>
          </div>
        </body></html>"""
        self.assertEqual([g["name"] for g in scrape(html)],
                         ["Great Movie Title", "Other Movie"])


if __name__ == "__main__":
    unittest.main()
