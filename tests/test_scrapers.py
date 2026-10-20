import json
import os
import unittest
from unittest import mock

import db
import net_guard
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
    status_code = 200       # safe_get reads status_code on every hop
    def raise_for_status(self): pass


class ManagementTests(IsolatedCase):
    def test_only_py_and_yaml_are_accepted(self):
        with self.assertRaises(ValueError):
            scrapers.add("evil.exe", b"x", "movie")

    def test_add_list_toggle_remove(self):
        sid = scrapers.add("site.yml", YAML, "movie")[0]
        [entry] = scrapers.list_all()
        self.assertTrue(entry["exists"] and entry["enabled"] and entry["size"] > 0)
        scrapers.toggle(sid)
        self.assertFalse(scrapers.list_all()[0]["enabled"])
        with self.assertRaises(ValueError):
            scrapers.run_by_id(sid, title="x")               # disabled
        scrapers.remove(sid)
        self.assertEqual(scrapers.list_all(), [])
        self.assertEqual(os.listdir(db.SCRAPER_DIR), ["meta.json"])


class BundledRemovalTests(IsolatedCase):
    def test_removing_a_bundled_scraper_tombstones_the_file(self):
        fn = "demo_scraper.py"
        with open(os.path.join(db.SCRAPER_DIR, fn), "wb") as f:
            f.write(b"x")
        sid = "bundled-demo"
        scrapers._save_meta([{"id": sid, "name": "demo", "file": fn,
                              "type": "python", "kind": "movie",
                              "enabled": True, "structure": None}])
        scrapers.remove(sid)
        self.assertEqual(scrapers.list_all(), [])
        self.assertTrue(os.path.exists(os.path.join(db.SCRAPER_DIR, "removed.json")))
        self.assertIn(fn, scrapers._removed())

    def test_install_bundled_respects_the_tombstone(self):
        import sys
        bundle = os.path.join(db.SCRAPER_DIR, "scrapers")
        os.makedirs(bundle, exist_ok=True)
        for fn in ("aaa.py", "gone.py"):
            with open(os.path.join(bundle, fn), "wb") as f:
                f.write(PY_SCRAPER)
        scrapers._mark_removed("gone.py")
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", db.SCRAPER_DIR, create=True):
            scrapers.install_bundled()
        self.assertEqual([s["file"] for s in scrapers._meta()], ["aaa.py"],
                         "the removed scraper must not be reinstalled on the next boot")

    def test_a_burst_of_parallel_deletes_keeps_every_tombstone(self):
        """Deleting many bundled scrapers rapid-fire (how the UI burst arrives via
        the threadpool) must not let last-writer-wins resurrect the others: every
        delete tombstones its file and every meta entry disappears."""
        import threading
        n = 12
        meta = []
        for i in range(n):
            sid, fn = f"bundled-s{i}", f"s{i}.py"
            with open(os.path.join(db.SCRAPER_DIR, fn), "wb") as f:
                f.write(b"x")
            meta.append({"id": sid, "name": f"s{i}", "file": fn, "type": "python",
                         "kind": "movie", "enabled": False, "structure": None})
        scrapers._save_meta(meta)
        threads = [threading.Thread(target=scrapers.remove, args=(f"bundled-s{i}",))
                   for i in range(n)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(scrapers.list_all(), [], "no meta entry survives the burst")
        self.assertEqual(scrapers._removed(), {f"s{i}.py" for i in range(n)},
                         "every tombstone lands, none is lost to a stale rewrite")


class MultiAssignTests(IsolatedCase):
    PY_SCENE = b'def scrape_scene(url):\n    return {}\n'

    def test_yaml_kind_list_is_stored_as_given(self):
        sid, kinds = scrapers.add("site.yaml", YAML, ["scene", "performer"])
        self.assertEqual(kinds, ["scene", "performer"])
        self.assertEqual(scrapers.list_all()[-1]["kind"], ["scene", "performer"])

    def test_python_assignment_is_corrected_against_the_source(self):
        # assigned 'movie' only, but the source proves scene work too → union
        _, kinds = scrapers.add("s.py", self.PY_SCENE, ["movie"])
        self.assertEqual(kinds, ["movie", "scene"])
        # bare source evidence adds kinds the caller forgot entirely
        _, kinds = scrapers.add("p.py", b'def scrape_performer(u):\n    ...\n', ["movie"])
        self.assertEqual(kinds, ["movie", "performer"])


class BrazzersActorTests(IsolatedCase):
    """brazzers_scraper._actor_to_perf: Project1Service /v1/actors object â†’
    Umbra performer fields (forms.js applyToPerfForm keys)."""
    ACTOR = {'name': 'Angela White', 'gender': 'female',
             'birthday': '1985-03-04T00:00:00+00:00',
             'birthPlace': 'New South Wales, Australia',
             'height': 62, 'weight': 62, 'measurements': '32GG-28-36',
             'aliases': [''],
             'images': {'profile': {'0': {'lg': {'url': 'http://m/lg.jpg'},
                                          'xs': {'url': 'http://m/xs.jpg'}}}}}

    def test_v1_actor_maps_to_umbra_performer(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scrapers"))
        import brazzers_scraper as b
        d = b._actor_to_perf(dict(self.ACTOR), "https://www.brazzers.com/pornstar/4685/x")
        self.assertEqual(d['name'], 'Angela White')
        self.assertEqual(d['gender'], 'f')
        self.assertEqual(d['birth'], '1985-03-04')
        self.assertEqual(d['nationality'], 'New South Wales, Australia')
        self.assertEqual(d['height'], 157)            # 62 in â†’ cm
        self.assertEqual(d['weight'], 62)
        self.assertEqual(d['measurements'], '32GG-28-36')
        self.assertEqual(d['photo'], 'http://m/lg.jpg')   # lg wins over xs
        self.assertNotIn('aliases', d)                # [""] filtered out
        self.assertEqual(d['kind'], 'performer')

    def test_metric_height_is_kept_as_is(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scrapers"))
        import brazzers_scraper as b
        a = dict(self.ACTOR, height=157)
        self.assertEqual(b._actor_to_perf(a)['height'], 157)


class P1SceneEnvelopeTests(IsolatedCase):
    """P1 detail endpoints wrap the release in {'meta':…, 'result':{…}} —
    get_scene must unwrap (RealityKings returned notFound for valid scenes)."""
    RELEASE = {'title': 'Public Pickup', 'dateReleased': '2026-10-17T12:00:00+00:00',
               'description': 'd', 'id': 123, 'duration': 1830,
               'actors': [{'name': 'Raissa Bellini'}], 'tags': [], 'studio': 'RK'}

    def _scrape(self, data, cap):
        import p1api
        with mock.patch.object(p1api, "api_get", return_value=data) as g:
            out = p1api.get_scene(123, "https://www.realitykings.com", "Reality Kings")
        self.assertEqual(g.call_args.args[0], cap)
        return out

    def test_wrapped_release_is_unpacked(self):
        out = self._scrape({'meta': {'count': 1}, 'result': dict(self.RELEASE)},
                           '/v2/releases/123')
        self.assertEqual(out['title'], 'Public Pickup')
        self.assertEqual(out['date'], '2026-10-17')
        self.assertEqual(out['duration_min'], 30)
        self.assertEqual(out['performers'][0]['name'], 'Raissa Bellini')
        self.assertNotIn('notFound', out)

    def test_bare_release_still_works(self):
        out = self._scrape(dict(self.RELEASE), '/v2/releases/123')
        self.assertEqual(out['title'], 'Public Pickup')


class PrivateScraperTests(IsolatedCase):
    """private.com.py — scene detail/search + performer profile, all HTML."""
    SCENE = ('<h1>Matty Mila Perez, how I became a pornstar</h1>'
             '<meta property="og:description" content="She explains how.">'
             '<meta property="og:image" content="https://p.test/c.jpg">'
             '<meta itemprop="duration" content="PT31M54S">'
             '<meta itemprop="uploadDate" content="2026-09-28T00:00:00+01:00">'
             '<ul class="scene-models-list-tags-sites">'
             '<li class="tag-models"><a href="/pornstar/8112-matty">Matty Mila Perez</a></li>'
             '<li class="tag-tags"><a href="/category/4k/">4K</a></li>'
             '<li class="tag-tags"><a href="/category/anal/">Anal</a></li></ul>'
             '<span class="title-site">Private Stars</span>')
    PERF = ('<h1>Matty Mila Perez</h1>'
            '<meta property="og:image" content="https://p.test/profile.jpg">'
            '<ul class="model-facts"><li><em>Measurements:</em>34-23-36</li>'
            '<li><em>Height:</em>157cm - 5ft 2in</li><li><em>Weight:</em>-</li>'
            '<li><em>Nationality:</em>Latvian</li><li><em>Hair Color:</em>Black</li>'
            '<li><em>Eye color:</em>Tattooed eyeliner</li></ul>')
    LIST = ('<a href="/scene/x/1">4K</a>'
            '<a href="/scene/how-i-became/27221">Matty Mila Perez, how I became a pornstar</a>'
            '<a href="/scene/other/2">Matty Mila Perez Fucks Her Boss</a>'
            '<a href="/scene/y/3">Your browser does not support the video tag.</a>')

    def _load(self):
        import sys, uuid, importlib.util
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "scrapers", "private.com.py")
        spec = importlib.util.spec_from_file_location("umbra_scr_" + uuid.uuid4().hex, p)
        pv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pv)

        class R:
            def __init__(self, text): self.text = text
            def raise_for_status(self): pass
        return pv, R

    def test_scene_page_maps_to_umbra_scene(self):
        pv, R = self._load()
        with mock.patch.object(pv.requests, "get", return_value=R(self.SCENE)) as g:
            out = pv.scrape(url="https://www.private.com/scene/m/27221")
        self.assertEqual(out['title'], 'Matty Mila Perez, how I became a pornstar')
        self.assertEqual(out['date'], '2026-09-28')
        self.assertEqual(out['duration_min'], 32)
        self.assertEqual(out['code'], '27221')
        self.assertEqual(out['performers'], [
            {'name': 'Matty Mila Perez', 'url': 'https://www.private.com/pornstar/8112-matty'}])
        self.assertEqual(out['tags'], ['4K', 'Anal'])
        self.assertEqual(out['studio'], 'Private Stars')
        self.assertEqual(out['cover_a'], 'https://p.test/c.jpg')

    def test_performer_profile_maps_to_umbra_performer(self):
        pv, R = self._load()
        with mock.patch.object(pv.requests, "get", return_value=R(self.PERF)):
            out = pv.scrape(url="https://www.private.com/pornstar/8112-matty")
        self.assertEqual(out['name'], 'Matty Mila Perez')
        self.assertEqual(out['height'], 157)
        self.assertEqual(out['measurements'], '34-23-36')
        self.assertEqual(out['hair'], 'Black')
        self.assertEqual(out['eyes'], 'Tattooed eyeliner')
        self.assertNotIn('weight', out)               # '-' filtered
        self.assertEqual(out['photo'], 'https://p.test/profile.jpg')

    def test_title_search_picks_best_card_detail(self):
        import algolia
        pv, R = self._load()
        with mock.patch.object(algolia, "title_match_score",
                               side_effect=lambda q, t: 100 if "how i became" in (t or "").lower() else 10) as sc:  # noqa: E731
            pages = {'search': R(self.LIST), 'detail': R(self.SCENE)}
            def fake_get(url, **kw):
                return pages['detail'] if '/scene/how-i-became/' in url else pages['search']
            with mock.patch.object(pv.requests, "get", side_effect=fake_get):
                out = pv.scrape(title="Matty Mila Perez, how I became a pornstar")
        self.assertEqual(sc.call_count, 2)
        self.assertEqual(out['title'], 'Matty Mila Perez, how I became a pornstar')
        self.assertEqual(out['duration_min'], 32)

    def test_site_route_prefers_the_kind_matching_scraper(self):
        """Two scrapers match x.com — a scene-only HTML mapping added first and a
        performer python scraper added later; performer fetch must take the later.
        (regression: first-host-match won, so /pornstar/ got the scene yaml)"""
        fn = "perf_fit.py"
        with open(os.path.join(db.SCRAPER_DIR, fn), "wb") as f:
            f.write(b'def scrape(**kw):\n    return {"name": "perf-fit"}\n')
        scout = "fit_scene.yml"
        with open(os.path.join(db.SCRAPER_DIR, scout), "wb") as f:
            f.write(YAML)
        scrapers._save_meta([
            {"id": "fit-1", "name": "x.com", "file": scout, "type": "yaml",
             "kind": ["scene"], "enabled": True, "structure": None},
            {"id": "fit-2", "name": "x.com", "file": fn, "type": "python",
             "kind": ["performer"], "enabled": True, "structure": None}])
        with mock.patch.object(db, "get_settings", return_value={"pyScrapers": True}):
            out = scrapers.run_for_site("https://x.com/pornstar/1",
                                        url="https://x.com/pornstar/1", kind="performer")
            self.assertEqual(out, {"name": "perf-fit"})
            with mock.patch.object(scrapers.requests, "get", return_value=FakeResponse()), \
                    _stub_public_dns():
                out = scrapers.run_for_site("https://x.com/pornstar/1",
                                            url="https://x.com/pornstar/1")  # no kind → first
        self.assertEqual(out, {"title": "Alpha", "year": 1999, "poster_f": "http://x.test/p.jpg"})


class NaughtyAmericaTests(IsolatedCase):
    """NaughtyAmerica.py — JSON-LD VideoObject scene + ld Person profile."""
    SCENE = ('<script type="application/ld+json">{"@context":"https://schema.org",'
             '"@type":"VideoObject","name":"Gracie Glam & Mikey Butders in Naughty Bookworms",'
             '"description":"Gracie Glam fails her class...",'
             '"thumbnailUrl":"https://img.test/800x534.jpg",'
             '"uploadDate":"2020-06-07T07:00:00+00:00",'
             '"actor":[{"@type":"Person","name":"Mikey Butders","gender":"Male"},'
             '{"@type":"Person","name":"Gracie Glam","gender":"Female"}]}</script>'
             '<div class="duration"><span>|</span> 30 min </div>'
             '<h2><span class="scene-title small-text">Site:</span>'
             '<a class="site-title grey-text link" href="/site/naughty-bookworms">Naughty Bookworms</a></h2>'
             '<a href="https://www.naughtyamerica.com/fantasy/ass-smacking-porn-videos">Ass Smacking</a>'
             '<a href="https://www.naughtyamerica.com/fantasy/remastered-porn-videos">REMASTERED HD</a>')
    PERF = ('<script type="application/ld+json">{"@context":"https://schema.org",'
            '"@type":"Person","name":"Angela White",'
            '"url":"https://www.naughtyamerica.com/pornstar/angela-white",'
            '"image":"https://img.test/profile.jpg",'
            '"description":"The horny porn star from Sydney.",'
            '"gender":"Female"}</script>')

    def _load(self):
        import uuid, importlib.util
        from bs4 import BeautifulSoup as BS
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "scrapers", "NaughtyAmerica.py")
        spec = importlib.util.spec_from_file_location("umbra_na_" + uuid.uuid4().hex, p)
        na = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(na)
        na._soup = BS
        return na

    def _feed(self, na, html):
        na._get = lambda url, retries=2: na._soup(html, 'html.parser')

    def test_scene_page_maps(self):
        na = self._load()
        self._feed(na, self.SCENE)
        out = na.scrape(url="https://www.naughtyamerica.com/scene/x-26021")
        self.assertEqual(out['title'], 'Gracie Glam & Mikey Butders in Naughty Bookworms')
        self.assertEqual(out['date'], '2020-06-07')
        self.assertEqual(out['duration_min'], 30)
        self.assertEqual(out['code'], '26021')
        self.assertEqual(out['studio'], 'Naughty Bookworms')
        self.assertEqual([p['name'] for p in out['performers']], ['Mikey Butders', 'Gracie Glam'])
        self.assertEqual(out['performers'][1]['gender'], 'f')
        self.assertEqual(out['tags'], ['Ass Smacking'])       # REMASTERED HD dropped
        self.assertEqual(out['cover_a'], 'https://img.test/800x534.jpg')

    def test_performer_profile_maps(self):
        na = self._load()
        self._feed(na, self.PERF)
        out = na.scrape(url="https://www.naughtyamerica.com/pornstar/angela-white")
        self.assertEqual(out['name'], 'Angela White')
        self.assertEqual(out['gender'], 'f')
        self.assertEqual(out['photo'], 'https://img.test/profile.jpg')
        self.assertEqual(out['bio'], 'The horny porn star from Sydney.')

    def test_name_lookup_guesses_the_slug(self):
        na = self._load()
        seen = {}
        def fake_get(url, retries=2):
            seen['url'] = url
            return na._soup(self.PERF, 'html.parser')
        na._get = fake_get
        out = na.scrape(title="Angela  White", kind="performer")
        self.assertEqual(seen['url'], 'https://www.naughtyamerica.com/pornstar/angela-white')
        self.assertEqual(out['name'], 'Angela White')

    def test_scene_title_search_is_honest(self):
        na = self._load()
        na._get = lambda url, retries=2: {'error': 'HTTP 202'}
        na._CAT = None
        out = na.scrape(title="whatever")
        self.assertIn('notFound', out)

    def test_title_search_matches_the_sitemap_catalog(self):
        na = self._load()
        self._feed(na, self.SCENE)          # any url returns the scene page
        seen = {}
        orig = na._scene
        na._scene = lambda u: (seen.__setitem__('u', u), orig(u))[1]
        na._CAT = {'scenes': [
            'https://www.naughtyamerica.com/scene/naomi-cruise-fucking-in-the-bed-with-her-big-ass-1354',
            'https://www.naughtyamerica.com/scene/gracie-glam-fucks-professor-to-pass-class-26021']}
        out = na.scrape(title="gracie glam professor class")
        self.assertEqual(seen['u'],
                         'https://www.naughtyamerica.com/scene/gracie-glam-fucks-professor-to-pass-class-26021')
        self.assertEqual(out['title'], 'Gracie Glam & Mikey Butders in Naughty Bookworms')

    def test_performer_name_search_uses_the_catalog_first(self):
        na = self._load()
        self._feed(na, self.PERF)
        seen = {}
        def fake_get(url, retries=2):
            seen['url'] = url
            return na._soup(self.PERF, 'html.parser')
        na._get = fake_get
        na._CAT = {'performers': [
            'https://www.naughtyamerica.com/pornstar/nicole-aniston']}
        out = na.scrape(title="Angela  White", kind="performer")
        self.assertEqual(seen['url'], 'https://www.naughtyamerica.com/pornstar/angela-white')
        self.assertEqual(out['name'], 'Angela White')

    def test_catalog_cache_is_written_and_reused_within_ttl(self):
        na = self._load()
        tmp = self.tmpfile("na.idx.json", b"")
        na._cat_path = lambda: tmp
        idx = ('<loc>https://naughtyamerica.com/sitemap-1.xml</loc>SITEMAPS'
               '<loc>https://naughtyamerica.com/scene-1.xml</loc>')
        child = ('<loc>https://www.naughtyamerica.com/scene/naomi-cruise-fucking-1354</loc>'
                 '<loc>https://www.naughtyamerica.com/pornstar/angela-white</loc>')
        pages = {'x': idx, 'https://naughtyamerica.com/scene-1.xml': child,
                 'https://naughtyamerica.com/sitemap-1.xml': child}
        na._get = lambda url, retries=2: na._soup(
            pages.get(url, pages['https://naughtyamerica.com/scene-1.xml']), 'html.parser')
        na._CAT = None
        na._index()
        d = json.load(open(tmp, encoding='utf-8'))
        self.assertEqual(d['scenes'], ['https://www.naughtyamerica.com/scene/naomi-cruise-fucking-1354'])
        self.assertEqual(d['performers'], ['https://www.naughtyamerica.com/pornstar/angela-white'])
        # fresh file: second call loads from disk without any network
        na._get = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network hit'))
        na._CAT = None
        self.assertEqual(na._index()['scenes'], ['https://www.naughtyamerica.com/scene/naomi-cruise-fucking-1354'])


class KindDetectionTests(IsolatedCase):
    SRC_PERFORMER = "def performer_from_url(url):\n    ...\n\ndef performer_search(n):\n    ...\n\ndef scrape(name=\"\"):\n    ...\n"
    SRC_MOVIE = "def _is_movie_url(href):\n    ...\n\ndef _get_movie_by_url(url):\n    ...\n\ndef scrape(**kw):\n    ...\n"
    SRC_SCENE = "def search_scenes(q):\n    ...\n\ndef scrape_scene(url):\n    ...\n\ndef search_performers(q):\n    ...\n\ndef scrape_performer(url):\n    ...\n\ndef scrape(kind=\"\"):\n    ...\n"
    # dispatch-only: no local defs, the site's scenes are reached through a
    # shared API module â€” still scene-capable (brazzers-style)
    SRC_SHADER = "def scrape(url, kind=''):\n    ...\n    if kind == 'performer':\n        return _performer(url)\n    return p1api.scene_by_url(url, SITE_URL)\n\ndef _performer(url):\n    ...\n"

    def test_source_is_classified_by_what_it_implements(self):
        self.assertEqual(scrapers.detect_kind(self.SRC_PERFORMER), "performer")
        self.assertEqual(scrapers.detect_kind(self.SRC_MOVIE), "movie")
        # scenes+performers together â†’ the dominant-kind word wins
        self.assertEqual(scrapers.detect_kind(self.SRC_SCENE), "scene")

    def test_one_source_can_carry_several_kinds(self):
        # defines both kinds â†’ multi-classification list, best evidence first
        self.assertEqual(scrapers.detect_kinds(self.SRC_SCENE), ["scene", "performer"])
        # dispatches scenes through a helper module while scraping performers
        # itself â†’ both kinds, performer (the def) stays primary (brazzers)
        self.assertEqual(scrapers.detect_kinds(self.SRC_SHADER), ["performer", "scene"])
        self.assertEqual(scrapers.detect_kind(self.SRC_SHADER), "performer")

    def test_the_real_bundled_library_is_not_all_movies(self):
        lib = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(scrapers.__file__))), "scrapers")
        if not os.path.isdir(lib):
            self.skipTest("bundled scraper sources not present in the dev tree")
        kinds = {}
        for fn in sorted(os.listdir(lib)):
            if fn.endswith(".py"):
                with open(os.path.join(lib, fn), encoding="utf-8", errors="replace") as f:
                    kinds[fn] = scrapers.detect_kinds(f.read())
        self.assertTrue(all(isinstance(k, list) and k for k in kinds.values()),
                        f"every bundled scraper needs at least one kind; got {kinds}")
        self.assertEqual({g for ks in kinds.values() for g in ks}, {"movie", "scene", "performer"},
                         f"the library should cover every kind; got {kinds}")
        # trouble cases: pure bio sites stay performer-only, pure movie APIs
        # stay movie-only, and dual dispatchers carry BOTH scene and performer
        self.assertEqual(kinds["brazzers_scraper.py"], ["performer", "scene"])
        self.assertEqual(kinds["evilangel_scraper.py"], ["performer", "scene"])
        self.assertEqual(kinds["babe" "pedia_scraper.py"], ["performer"])
        self.assertEqual(kinds["Erotik.py"], ["movie"])

    def test_install_bundled_migrates_old_movie_labels(self):
        """Entries installed before auto-detection (all 'movie') are re-classified
        on the next boot from the refreshed file."""
        import sys
        bundle = os.path.join(db.SCRAPER_DIR, "scrapers")
        os.makedirs(bundle, exist_ok=True)
        with open(os.path.join(bundle, "perf.py"), "wb") as f:
            f.write(self.SRC_PERFORMER.encode())
        old = {"id": "bundled-perf", "name": "perf", "file": "perf.py",
               "type": "python", "kind": "movie", "enabled": False, "structure": None}
        scrapers._save_meta([old])
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", db.SCRAPER_DIR, create=True):
            scrapers.install_bundled()
        [entry] = scrapers._meta()
        self.assertEqual(entry["kind"], ["performer"])


class PythonScraperTests(IsolatedCase):
    def test_python_scrapers_are_off_by_default(self):
        sid = scrapers.add("s.py", PY_SCRAPER, "movie")[0]
        with self.assertRaisesRegex(ValueError, "disabled"):
            scrapers.run_by_id(sid, title="abc")

    def test_enabled_scraper_runs_and_only_gets_kwargs_it_accepts(self):
        db.save_settings({"pyScrapers": True})
        sid = scrapers.add("s.py", PY_SCRAPER, "movie")[0]
        self.assertEqual(scrapers.run_by_id(sid, title="abc", kind="movie", domain="d"),
                         {"title": "ABC"})
        sid2 = scrapers.add("k.py", PY_KWARGS, "movie")[0]
        self.assertEqual(scrapers.run_by_id(sid2, title="a", kind="movie", domain="d")["kw"],
                         ["domain", "kind", "title", "url"])


class YamlScraperTests(IsolatedCase):
    def test_selectors_and_transforms(self):
        sid = scrapers.add("site.yml", YAML, "movie")[0]
        with mock.patch.object(scrapers.requests, "get", return_value=FakeResponse()) as g, \
                _stub_public_dns():        # run_yaml now guards the target (P1 SSRF)
            out = scrapers.run_by_id(sid, title="My Title")
        self.assertEqual(out, {"title": "Alpha", "year": 1999,
                               "poster_f": "http://x.test/p.jpg"})
        self.assertIn("My%20Title", g.call_args.args[0])

    def test_needs_url_or_search_template(self):
        p = self.tmpfile("bare.yml", b"fields: {}")
        with self.assertRaises(ValueError):
            scrapers.run_yaml(p, title="x")

    def test_duration_transform_variants(self):
        for raw, mins in [("12:34", 13), ("1:02:12", 62), ("PT12M34S", 13),
                          ("PT1H02M", 62), ("75 min", 75), ("", None)]:
            self.assertEqual(scrapers._duration_min(raw), mins, raw)

    def test_list_keys_split_into_arrays(self):
        y = ('search: {url: "https://s.test/?q={title}"}\nfields:\n'
             ' catNames: {selector: "span.cat", attr: text}\n'
             ' performers: {selector: "span.cast", attr: text}'
             '   # a, b ,  → ["a","b"]\n')
        html = ('<span class="cat">Lesbians, Anal</span>'
                '<span class="cast">Angela White,  Abella Danger</span>')
        with mock.patch.object(scrapers, "FakeResponseRequested", False, create=True):
            pass
        p = self.tmpfile("list.yml", y.encode())
        class R:  # noqa: E701
            text = html
            status_code = 200
            def raise_for_status(self): pass
        with mock.patch.object(scrapers.requests, "get", return_value=R()), \
                _stub_public_dns():
            out = scrapers.run_yaml(p, title="t")
        self.assertEqual(out, {"catNames": ["Lesbians", "Anal"],
                               "performers": ["Angela White", "Abella Danger"]})


    def test_multi_select_and_jsonld_attr(self):
        # multi: select-all → arrays (private.com-style cast/category lists);
        # ld: — dotted path into an embedded JSON-LD VideoObject (RK-style pages)
        y = ('search: {url: "https://s.test/?q={title}"}\nfields:\n'
             ' performers: {selector: "li.tag-models a", attr: text, multi: true}\n'
             ' catNames: {selector: "li.tag-tags a", attr: text, multi: true}\n'
             ' title: {selector: "script[type=\\"application/ld+json\\"]", attr: ld:name}\n'
             ' cover_a: {selector: "script[type=\\"application/ld+json\\"]",'
             ' attr: "ld:thumbnailUrl.0"}\n')
        html = ('<li class="tag-models"><a>Matty Mila Perez</a></li>'
                '<li class="tag-models"><a>Papi Rodriguez</a></li>'
                '<li class="tag-tags"><a>4K</a></li><li class="tag-tags"><a>Anal</a></li>'
                '<script type="application/ld+json">{"@context":"https://schema.org",'
                '"@type":"VideoObject","name":"Public Pickup",'
                '"thumbnailUrl":["https://x.test/p.jpg","https://x.test/q.jpg"]}</script>')
        p = self.tmpfile("multi.yml", y.encode())
        class R:  # noqa: E701
            text = html
            status_code = 200
            def raise_for_status(self): pass
        with mock.patch.object(scrapers.requests, "get", return_value=R()), \
                _stub_public_dns():
            out = scrapers.run_yaml(p, title="t")
        self.assertEqual(out, {"performers": ["Matty Mila Perez", "Papi Rodriguez"],
                               "catNames": ["4K", "Anal"],
                               "title": "Public Pickup",
                               "cover_a": "https://x.test/p.jpg"})


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


# net_guard resolves the target host before fetching; example.test is reserved
# (RFC 6761) and never resolves on this machine, so tests whose fetch should be
# ALLOWED stub the resolver to one public address. Blocked cases use numeric
# IPs, which getaddrinfo parses locally â€” no live network in any test here.
_PUBLIC_DNS = [(2, 1, 6, "", ("93.184.216.34", 443))]


def _stub_public_dns():
    return mock.patch("net_guard.socket.getaddrinfo", return_value=_PUBLIC_DNS)


class YamlTargetGuardTests(IsolatedCase):
    """Regression (P1, SSRF): run_yaml's target â€” the caller-supplied url or the
    YAML search.url template â€” must pass net_guard before any fetch."""

    def _yaml(self, tpl: str) -> str:
        return self.tmpfile("guard.yml",
                            f'search: {{url: "{tpl}"}}\nfields: {{}}\n'.encode())

    def test_run_yaml_blocks_loopback_target(self):
        p = self._yaml("http://127.0.0.1:9/x")
        with mock.patch.object(scrapers.requests, "get") as g, \
                mock.patch("socket.create_connection") as conn:
            with self.assertRaisesRegex(ValueError, "blocked unsafe"):
                scrapers.run_yaml(p, title="x")
        g.assert_not_called()
        conn.assert_not_called()

    def test_run_yaml_blocks_cloud_metadata_target(self):
        p = self._yaml("http://169.254.169.254/latest/meta-data/")
        with mock.patch.object(scrapers.requests, "get") as g:
            with self.assertRaisesRegex(ValueError, "blocked unsafe"):
                scrapers.run_yaml(p, title="x")
        g.assert_not_called()

    def test_run_yaml_allows_public_https(self):
        p = self._yaml("https://example.test/search?q={title}")
        with mock.patch.object(scrapers.requests, "get", return_value=FakeResponse()) as g, \
                _stub_public_dns():
            scrapers.run_yaml(p, title="My Title")
        g.assert_called_once()
        self.assertIn("https://example.test/search?q=My%20Title",
                      g.call_args.args[0])

    def test_run_yaml_rejects_non_http_scheme(self):
        p = self._yaml("file:///C:/Windows/win.ini")
        with mock.patch.object(scrapers.requests, "get") as g:
            with self.assertRaisesRegex(ValueError, "blocked unsafe"):
                scrapers.run_yaml(p, title="x")
        g.assert_not_called()


class NetGuardTests(unittest.TestCase):
    """safe_image_url unit checks â€” numeric hosts only, so getaddrinfo parses
    them locally and no DNS query leaves the machine."""

    def test_guard_blocks_loopback(self):
        self.assertFalse(net_guard.safe_image_url("http://127.0.0.1/"))

    def test_guard_blocks_cloud_metadata(self):
        self.assertFalse(net_guard.safe_image_url("http://169.254.169.254/"))

    def test_guard_blocks_private_lan(self):
        self.assertFalse(net_guard.safe_image_url("http://10.0.0.1/"))

    def test_guard_blocks_non_url(self):
        self.assertFalse(net_guard.safe_image_url("not-a-url"))


class _Redirect:
    """Minimal 3xx response: only status_code + Location are read by safe_get."""
    def __init__(self, location: str, status: int = 302):
        self.status_code = status
        self.headers = {"Location": location}


class _Ok:
    status_code = 200
    text = ""


class _StubSession:
    """Scripted session: replays queued responses, records every (url, kw)."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kw):
        self.calls.append((url, kw))
        return self.responses.pop(0)


class SafeGetTests(unittest.TestCase):
    """P2: safe_get re-validates every redirect hop (Gap 2, blind redirects).
    All stubs â€” no live network: the loopback hop is a numeric IP (parsed
    locally), allowed hostnames run with the resolver stubbed to a public IP."""

    def test_safe_get_blocks_redirect_to_loopback(self):
        s = _StubSession(_Redirect("http://127.0.0.1:8080/admin"))
        with self.assertRaises(ValueError):
            net_guard.safe_get(s, "http://cdn.example/pic.jpg", timeout=5)
        self.assertEqual(len(s.calls), 1)                 # loopback hop never fetched
        self.assertFalse(s.calls[0][1].get("allow_redirects"))   # manual redirects
        self.assertEqual(s.calls[0][1]["timeout"], 5)     # **kw passes through

    def test_safe_get_allows_public_redirect(self):
        final = _Ok()
        s = _StubSession(_Redirect("https://img.cdn.test/pic.jpg"), final)
        with _stub_public_dns():
            r = net_guard.safe_get(s, "https://entry.example/x")
        self.assertIs(r, final)
        self.assertEqual([u for u, _ in s.calls],
                         ["https://entry.example/x", "https://img.cdn.test/pic.jpg"])

    def test_safe_get_stops_after_max_redirects(self):
        s = _StubSession(*[_Redirect("https://loop.example/x")] * (net_guard.MAX_REDIRECTS + 1))
        with _stub_public_dns():
            with self.assertRaises(ValueError):
                net_guard.safe_get(s, "https://loop.example/x")
        self.assertEqual(len(s.calls), net_guard.MAX_REDIRECTS + 1)

    def test_safe_get_rejects_https_to_http_downgrade(self):
        # Policy (deliberate P2 choice): the http target below is public and
        # would pass the host guard, but after an encrypted hop we never
        # silently degrade the fetch to plaintext.
        s = _StubSession(_Redirect("http://img.cdn.test/pic.jpg"), _Ok())
        with _stub_public_dns():
            with self.assertRaises(ValueError):
                net_guard.safe_get(s, "https://entry.example/x")
        self.assertEqual(len(s.calls), 1)
