"""HTTP-level smoke tests. Skipped automatically when fastapi/httpx (or the other
server dependencies such as cloudscraper) are not installed:

    pip install -r requirements.txt httpx
"""
import importlib
import os
import unittest

try:
    from fastapi.testclient import TestClient
    import cloudscraper  # noqa: F401  (server.py imports it at module level)
    HAVE_SERVER_DEPS = True
except Exception:                                   # pragma: no cover
    HAVE_SERVER_DEPS = False

from .helpers import IsolatedCase

_server = None


@unittest.skipUnless(HAVE_SERVER_DEPS, "fastapi/httpx/cloudscraper not installed")
class ServerCase(IsolatedCase):
    def setUp(self):
        super().setUp()
        global _server
        if _server is None:                          # imported once, into a temp data dir
            _server = importlib.import_module("server")
        self.srv = _server
        self.client = TestClient(self.srv.app, base_url="http://127.0.0.1")
        self.h = {"X-Obscura-Token": self.srv.API_TOKEN}

    def create_movie(self, **kw):
        body = {"title": "Alpha", "year": 2001, **kw}
        r = self.client.post("/api/movies", json=body, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def library(self):
        return self.client.get("/api/library", headers=self.h).json()


class SecurityTests(ServerCase):
    def test_api_requires_the_token(self):
        self.assertEqual(self.client.get("/api/ping").status_code, 403)
        r = self.client.get("/api/ping", headers=self.h)
        self.assertEqual((r.status_code, r.json()["ok"]), (200, True))

    def test_wrong_token_is_rejected(self):
        r = self.client.get("/api/ping", headers={"X-Obscura-Token": "nope"})
        self.assertEqual(r.status_code, 403)

    def test_foreign_host_and_origin_are_rejected(self):
        self.assertEqual(self.client.get(
            "/api/ping", headers={**self.h, "Host": "evil.example"}).status_code, 403)
        self.assertEqual(self.client.get(
            "/api/ping", headers={**self.h, "Origin": "http://evil.example"}).status_code, 403)

    def test_asset_routes_are_open_only_to_same_origin_fetches(self):
        # no token: a same-origin/absent Sec-Fetch-Site reaches the route (404: no such image)
        self.assertEqual(self.client.get("/api/images/i00000000").status_code, 404)
        r = self.client.get("/api/images/i00000000", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(r.status_code, 403)


class CrudTests(ServerCase):
    def test_create_read_update_delete_movie(self):
        mid = self.create_movie(actorIds=["p-1"])
        [m] = self.library()["movies"]
        self.assertEqual((m["id"], m["title"], m["actorIds"]), (mid, "Alpha", ["p-1"]))
        r = self.client.put("/api/movies", json={"id": mid, "title": "Beta"}, headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.library()["movies"][0]["title"], "Beta")
        self.assertEqual(self.client.delete(f"/api/movies/{mid}", headers=self.h).status_code, 200)
        self.assertEqual(self.library()["movies"], [])

    def test_updating_a_missing_record_is_404(self):
        r = self.client.put("/api/movies", json={"id": "mv-nope", "title": "x"}, headers=self.h)
        self.assertEqual(r.status_code, 404)

    def test_settings_round_trip(self):
        self.client.put("/api/settings", json={"theme": "light"}, headers=self.h)
        self.assertEqual(self.client.get("/api/settings", headers=self.h).json()["theme"], "light")


class ImageTests(ServerCase):
    def test_upload_then_fetch(self):
        r = self.client.post("/api/images", headers=self.h,
                             files={"file": ("a.png", b"\x89PNGdata", "image/png")})
        self.assertEqual(r.status_code, 200, r.text)
        got = self.client.get(r.json()["url"], headers=self.h)
        self.assertEqual((got.status_code, got.content), (200, b"\x89PNGdata"))


class DestructiveEndpointTests(ServerCase):
    def test_wipe_and_restore_need_explicit_confirmation(self):
        self.assertEqual(self.client.post("/api/wipe", json={}, headers=self.h).status_code, 400)
        r = self.client.post("/api/backup/restore", headers=self.h,
                             files={"file": ("b.zip", b"x")}, data={"confirm": ""})
        self.assertEqual(r.status_code, 400)

    def test_wipe_empties_the_library(self):
        self.create_movie()
        r = self.client.post("/api/wipe", json={"confirm": "DELETE MY LIBRARY"}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.library()["movies"], [])


class KnownBugTests(ServerCase):
    def test_deleting_the_video_file_fails_closed_without_scan_folders(self):
        """Regression (analysis #7, fixed): no scan folders configured → the file
        delete is refused (403) and the file survives; the row is untouched."""
        victim = self.tmpfile("anywhere/precious.mp4")
        mid = self.create_movie(filePath=victim)
        r = self.client.delete(f"/api/movies/{mid}?file=1&confirm=DELETE", headers=self.h)
        self.assertGreaterEqual(r.status_code, 400)
        self.assertTrue(os.path.exists(victim))

    def test_update_cannot_repoint_the_file_path(self):
        """Regression (analysis #1, fixed): PUT ignores a filePath repoint that
        isn't inside the configured scan folders — it never errors, because the
        frontend sends whole items on update."""
        real = self.tmpfile("lib/real.mp4")
        mid = self.create_movie(filePath=real)
        self.client.put("/api/movies", headers=self.h,
                        json={"id": mid, "filePath": "/etc/hosts"})
        self.assertEqual(self.library()["movies"][0]["filePath"], real)
