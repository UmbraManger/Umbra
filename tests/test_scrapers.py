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
