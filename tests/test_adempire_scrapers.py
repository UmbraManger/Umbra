"""Elegant Angel / WCPclub (shared ADE-platform) scrapers - offline checks."""

import importlib.util
import os
import unittest

from bs4 import BeautifulSoup

ROOT = os.path.join(os.path.dirname(__file__), "..", "scrapers")


def load(fname, modname):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(ROOT, fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ea = load("elegantangel.com.py", "umbra_ea")
wcp = load("wcpclub.com.py", "umbra_wcp")


class ParseTests(unittest.TestCase):
    def test_duration_hours_and_minutes(self):
        self.assertEqual(wcp._duration_min("Released: Dec 02, 2011 Length: 2 hrs. 49 mins."), 169)
        self.assertEqual(ea._duration_min("Length: 36 min"), 36)
        self.assertEqual(ea._duration_min("Length: 43 mins."), 43)

    def test_released_to_date(self):
        self.assertEqual(wcp._date_min_max("Released: Dec 02, 2011"), "2011-12-02")
        self.assertEqual(ea._date_min_max("Released: Oct 27, 2026"), "2026-10-27")

    def test_slug_title_after_site_prefix(self):
        self.assertEqual(wcp._slug_of("/shop/1596711/how-to-train-a-delinquent-teen-porn-videos.html"),
                         "how-to-train-a-delinquent-teen-porn-videos")
        self.assertEqual(ea._slug_of("/1806212/elegant-angel-candy-for-the-boogeyman-streaming-scene-video.html"),
                         "elegant-angel-candy-for-the-boogeyman-streaming-scene-video")

    def test_match_exact_first(self):
        q = "How To Train A Delinquent Teen"
        self.assertLess(wcp._match_score(q, "how-to-train-a-delinquent-teen-porn-videos"),
                        wcp._match_score(q, "how-to-train-a-delinquent-teen-3-porn-videos"))


class NamingTests(unittest.TestCase):
    """Local file naming: 'Performers, Performers - Title'."""
    def test_split_single_and_multi_performer(self):
        self.assertEqual(ea._split_perf_title("Anna Claire Clouds - Big Ass Dp"),
                         (["Anna Claire Clouds"], "Big Ass Dp"))
        self.assertEqual(ea._split_perf_title("Anna Claire Clouds, Angela White - Big Ass Dp"),
                         (["Anna Claire Clouds", "Angela White"], "Big Ass Dp"))
        self.assertEqual(wcp._split_perf_title("Emma Rosie - Fuck All Her Holes"),
                         (["Emma Rosie"], "Fuck All Her Holes"))

    def test_plain_titles_pass_through(self):
        self.assertEqual(ea._split_perf_title("Candy for the Boogeyman"),
                         ([], "Candy for the Boogeyman"))
        self.assertEqual(ea._split_perf_title("Big Wet Tits 27"), ([], "Big Wet Tits 27"))
        # a head with digits is not a performer list
        self.assertEqual(ea._split_perf_title("Top 10 - Asses"), ([], "Top 10 - Asses"))


class DetailSoupTests(unittest.TestCase):
    MARKUP = """
    <h1 class="description">The Title</h1>
    <meta property="og:image" content="https://img.example/f.jpg"/>
    <a data-Label="Performer"><div class="performer-name">Star One</div></a>
    <a data-Label="Performer">Bare Name</a>
    <a data-Label="Tag">Christmas</a><a data-Label="Tag">christmas</a><a data-Label="Tag">Anal</a>
    <div class="studio">Studio: West Coast Productions</div>
    <div class="director">Director: Sid Knox</div>
    <div class="release-date">Released: Oct 27, 2026</div>
    <div class="release-date">Length: 36 min</div>
    <div class="synopsis"><p>Santa wants candy.</p></div>
    """

    def _check(self, m):
        out = m._scrape_soup(BeautifulSoup(self.MARKUP, "html.parser"))
        self.assertIn("The Title", out["title"])
        self.assertEqual(out["performers"], ["Star One", "Bare Name"])
        self.assertEqual(out["catNames"], ["Christmas", "Anal"])
        self.assertEqual(out["studioName"], "West Coast Productions")
        self.assertEqual(out["director"], "Sid Knox")
        self.assertEqual(out["date"], "2026-10-27")
        self.assertEqual(out["durationMin"], 36)
        self.assertEqual(out["posterF"], "https://img.example/f.jpg")
        self.assertEqual(out["description"], "Santa wants candy.")

    def test_both_modules_share_the_layout(self):
        self._check(ea)
        self._check(wcp)


ADE_MARKUP = """
<h1 class="movie-page__heading__title">Big Ass DP <small>(2026)</small> | Elegant Angel Select</h1>
<meta property="og:image" content="https://img.example/front.jpg"/>
<a id="front-cover" data-href="https://img.example/big.jpg"></a>
<a label="Performer">Anna Claire Clouds</a><a label="Performer">Seth Gamble</a>
<a name="categories"></a><ul><a>Anal</a><a>Big Butt</a></ul>
<a label="Studio">Elegant Angel Select</a>
<a label="Director">Sid Knox</a>
<meta itemprop="datePublished" content="2026-07-15T00:00:00Z"/>
<span>Length: 43 mins.</span>
<div itemprop="description">Anna Claire Clouds and her big juicy ass.</div>
"""


class AdeMasterLayoutTests(unittest.TestCase):
    """Adultdvdempire master pages (search fallback) parse with the same soup."""
    def test_master_page_fields(self):
        for m in (ea, wcp):
            out = m._scrape_soup(BeautifulSoup(ADE_MARKUP, "html.parser"))
            self.assertEqual(out["title"], "Big Ass DP")
            self.assertEqual(out["performers"], ["Anna Claire Clouds", "Seth Gamble"])
            self.assertEqual(out["catNames"], ["Anal", "Big Butt"])
            self.assertEqual(out["studioName"], "Elegant Angel Select")
            self.assertEqual(out["director"], "Sid Knox")
            self.assertEqual(out["date"], "2026-07-15")
            self.assertEqual(out["durationMin"], 43)
            self.assertEqual(out["posterF"], "https://img.example/big.jpg")
            self.assertEqual(out["description"], "Anna Claire Clouds and her big juicy ass.")


if __name__ == "__main__":
    unittest.main()
