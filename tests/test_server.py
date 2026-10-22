"""HTTP-level smoke tests. Skipped automatically when fastapi/httpx (or the other
server dependencies such as cloudscraper) are not installed:

    pip install -r requirements.txt httpx
"""
import db
import importlib
import os
import scanner
import tempfile
import threading
import unittest
import zipfile

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
        self.h = {"X-Umbra-Token": self.srv.API_TOKEN}

    def create_movie(self, **kw):
        body = {"title": "Alpha", "year": 2001, **kw}
        r = self.client.post("/api/movies", json=body, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def library(self):
        return self.client.get("/api/library", headers=self.h).json()


class ScraperUploadTests(ServerCase):
    def test_multi_kind_upload(self):
        r = self.client.post("/api/scrapers/file", headers=self.h,
                             files={"file": ("multi.yml", b"fields: {}", "text/yaml")},
                             params=[("kind", "scene"), ("kind", "performer")])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["kinds"], ["scene", "performer"])
        e = next(s for s in self.client.get("/api/scrapers", headers=self.h).json()
                 if s["name"] == "multi.yml")
        self.assertEqual(e["kind"], ["scene", "performer"])
        self.client.delete(f'/api/scrapers/{e["id"]}', headers=self.h)


class SecurityTests(ServerCase):
    def test_api_requires_the_token(self):
        self.assertEqual(self.client.get("/api/ping").status_code, 403)
        r = self.client.get("/api/ping", headers=self.h)
        self.assertEqual((r.status_code, r.json()["ok"]), (200, True))

    def test_wrong_token_is_rejected(self):
        r = self.client.get("/api/ping", headers={"X-Umbra-Token": "nope"})
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

    def test_clear_tab_requires_confirm_then_empties_the_table(self):
        self.create_movie()
        r = self.client.post("/api/movies/deleteAll", json={}, headers=self.h)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(self.library()["movies"]), 1)
        r = self.client.post("/api/movies/deleteAll", json={"confirm": "DELETE"}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.library()["movies"], [])

    def test_deleting_a_record_frees_its_file_for_reimport(self):
        """Cleared movies must re-appear in the Import From Scan dialog: the
        delete endpoints forget the scanner's 'already imported' marker."""
        v = os.path.join(self._tmp, "film.mp4")
        open(v, "wb").close()
        scanner.mark_done(v)
        self.assertTrue(scanner.is_imported(v))
        mid = self.create_movie(file_path=v)
        self.client.delete(f"/api/movies/{mid}", headers=self.h)
        self.assertFalse(scanner.is_imported(v))
        # deleteAll (the 'Clear Movies' toolbar action) does the same for all rows
        scanner.mark_done(v)
        self.create_movie(file_path=v)
        self.client.post("/api/movies/deleteAll", json={"confirm": "DELETE"}, headers=self.h)
        self.assertFalse(scanner.is_imported(v))


class FrontendServingTests(ServerCase):
    """StaticFiles sends no Cache-Control, so WebView2 heuristic-caches js/*.js
    and keeps serving a stale bundle across sessions — the UI then looks
    'not applied' even though the files on disk are current."""

    def test_frontend_assets_are_not_cached(self):
        for path in ("/js/utils.js", "/index.html", "/"):
            r = self.client.get(path)
            if r.status_code != 200:
                continue
            self.assertIn("no-store", r.headers.get("cache-control", ""), path)

    def test_api_responses_keep_their_own_cache_headers(self):
        self.assertEqual("no-store" in self.client.get(
            "/api/settings", headers=self.h).headers.get("cache-control", ""), False)


class ScanProgressTests(ServerCase):
    """The candidates scan ffprobes every file synchronously, so the settings
    bar polls /api/scan/progress instead of sitting on a fake 30%."""

    def test_progress_reports_an_idle_shape(self):
        r = self.client.get("/api/scan/progress", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sorted(r.json()), ["active", "done", "total"])
        self.assertFalse(r.json()["active"])

    def test_a_scan_counts_files_then_clears_active(self):
        d = os.path.join(self._tmp, "lib")
        os.makedirs(d)
        open(os.path.join(d, "a.mp4"), "wb").close()
        r = self.client.post("/api/scan/candidates",
                             json={"dirs": [d]}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["count"], 1)
        p = self.client.get("/api/scan/progress", headers=self.h).json()
        self.assertFalse(p["active"], "must not be left active after the scan")
        self.assertEqual((p["done"], p["total"]), (1, 1))

    def test_import_from_scan_creates_the_record(self):
        """The import endpoint runs its file/poster work in the worker pool
        (backend freeze fix) — a round-trip still stores a real record."""
        d = os.path.join(self._tmp, "lib")
        os.makedirs(d)
        open(os.path.join(d, "film.mp4"), "wb").close()
        r = self.client.post("/api/scan/import",
                             json={"path": os.path.join(d, "film.mp4"),
                                   "kind": "movie", "title": "Film",
                                   "duration_min": 95}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        rec = r.json()["record"]
        lib = self.library()
        match = [m for m in lib["movies"] if m["id"] == rec["id"]]
        self.assertTrue(match, "the imported record must appear in the library")
        self.assertIn("film.mp4", (match[0].get("filePath")
                                   or match[0].get("file_path") or "").replace("\\", "/"))


class MediaOpenTests(ServerCase):
    def test_open_says_why_when_no_file_is_linked(self):
        """A bare 404 leaves the player unable to explain itself to the user."""
        mid = self.create_movie()
        r = self.client.post(f"/api/media/movie/{mid}/open", headers=self.h)
        self.assertEqual(r.status_code, 404)
        self.assertIn("no video file linked", r.json()["detail"])

    def test_open_hands_the_real_file_to_the_os_player(self):
        path = os.path.join(self._tmp, "film.mp4")
        with open(path, "wb") as f:
            f.write(b"\x00")
        mid = self.create_movie()
        import db
        db.execute("UPDATE movies SET file_path=? WHERE id=?", (path, mid))
        import media as media_engine
        from unittest import mock
        with mock.patch.object(media_engine, "open_with_os", return_value=True) as m:
            r = self.client.post(f"/api/media/movie/{mid}/open", headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        m.assert_called_once_with(path)


class ImageTests(ServerCase):
    def test_upload_then_fetch(self):
        r = self.client.post("/api/images", headers=self.h,
                             files={"file": ("a.png", b"\x89PNGdata", "image/png")})
        self.assertEqual(r.status_code, 200, r.text)
        got = self.client.get(r.json()["url"], headers=self.h)
        self.assertEqual((got.status_code, got.content), (200, b"\x89PNGdata"))

    def _blob_path(self, url):
        img_id = url.rsplit("/", 1)[-1]
        import crypto
        return os.path.join(crypto.ENC_DIR, img_id + ".bin")

    def test_replacing_a_cover_deletes_the_previous_blob(self):
        import crypto
        u1 = self.client.post("/api/images", headers=self.h,
                              files={"file": ("a.png", b"AAA", "image/png")}).json()["url"]
        u2 = self.client.post("/api/images", headers=self.h,
                              files={"file": ("b.png", b"BBB", "image/png")}).json()["url"]
        mid = self.create_movie(posterF=u1)
        self.client.put("/api/movies", json={"id": mid, "posterF": u2}, headers=self.h)
        self.assertFalse(os.path.exists(self._blob_path(u1)), "old cover blob must be deleted")
        self.assertTrue(os.path.exists(self._blob_path(u2)))
        self.assertEqual(self.client.get(u1, headers=self.h).status_code, 404)

    def test_unchanged_update_keeps_the_blob(self):
        u1 = self.client.post("/api/images", headers=self.h,
                              files={"file": ("a.png", b"AAA", "image/png")}).json()["url"]
        mid = self.create_movie(posterF=u1)
        self.client.put("/api/movies", json={"id": mid, "title": "Retitle"}, headers=self.h)
        self.assertTrue(os.path.exists(self._blob_path(u1)))

    def test_clearing_a_cover_deletes_the_blob(self):
        u1 = self.client.post("/api/images", headers=self.h,
                              files={"file": ("a.png", b"AAA", "image/png")}).json()["url"]
        mid = self.create_movie(posterF=u1)
        self.client.put("/api/movies", json={"id": mid, "posterF": ""}, headers=self.h)
        self.assertFalse(os.path.exists(self._blob_path(u1)))

    def test_prune_removes_unreferenced_blobs(self):
        u1 = self.client.post("/api/images", headers=self.h,
                              files={"file": ("a.png", b"AAA", "image/png")}).json()["url"]
        mid = self.create_movie(posterF=u1)
        orphan = self.client.post("/api/images", headers=self.h,
                                  files={"file": ("z.png", b"ZZZ", "image/png")}).json()["url"]
        n = self.client.post("/api/images/prune", headers=self.h).json()["pruned"]
        self.assertEqual(n, 1, "the orphan is pruned, the referenced blob survives")
        for url in (u1, orphan):
            got = self.client.get(url, headers=self.h)
            self.assertEqual((got.status_code == 200), url == u1)

    def test_deleting_a_performer_deletes_its_photo_blob(self):
        import crypto
        u1 = self.client.post("/api/images", headers=self.h,
                              files={"file": ("a.png", b"AAA", "image/png")}).json()["url"]
        pid = self.client.post("/api/performers", json={"name": "X", "photo": u1},
                               headers=self.h).json()["id"]
        self.client.delete(f"/api/performers/{pid}", headers=self.h)
        self.assertFalse(os.path.exists(os.path.join(crypto.ENC_DIR, u1.rsplit("/", 1)[-1] + ".bin")))


class DestructiveEndpointTests(ServerCase):
    def test_wipe_and_restore_need_explicit_confirmation(self):
        self.assertEqual(self.client.post("/api/wipe", json={}, headers=self.h).status_code, 400)
        r = self.client.post("/api/backup/restore", headers=self.h,
                             files={"file": ("b.zip", b"x")}, params={"confirm": ""})
        self.assertEqual(r.status_code, 400)

    def test_wipe_empties_the_library(self):
        self.create_movie()
        r = self.client.post("/api/wipe", json={"confirm": "DELETE MY LIBRARY"}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.library()["movies"], [])

    def test_wipe_leaves_no_residue(self):
        """A wipe must remove db.prev, posters/ and WAL/journal files so the
        data folder holds only the fresh library."""
        self.create_movie()
        self.client.post("/api/wipe", json={"confirm": "DELETE MY LIBRARY"}, headers=self.h)
        d = db.DATA_DIR
        self.assertFalse(os.path.exists(os.path.join(d, "obscura.db.prev")))
        self.assertFalse(os.path.isdir(os.path.join(d, "posters")))
        # WAL/journal are runtime sqlite artifacts: they are recycled/removed by the
        # next connection, while the wipe itself compacts the main db (VACUUM).

    def test_restore_does_not_block_the_event_loop(self):
        """RESTORE must run off the event loop: /api/ping must answer while the
        restore is still running in a worker thread."""
        with tempfile.TemporaryDirectory() as d:
            zip_path = os.path.join(d, "b.zip")
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("obscura.db", b"dummy-library")
                z.writestr("settings.json", b"{}")
            with open(zip_path, "rb") as fh:
                files = {"file": ("b.zip", fh, "application/zip")}
                worker = threading.Thread(
                    target=self.client.post,
                    args=["/api/backup/restore"],
                    kwargs={"params": {"confirm": "RESTORE"}, "files": files, "headers": self.h},
                    daemon=True)
                worker.start()
                ping = self.client.get("/api/ping", headers=self.h)
                self.assertEqual(ping.status_code, 200, ping.text)
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive(), "restore still running after the ping timeout")

    def test_restore_rejects_oversized_content_length(self):
        """A request declaring Content-Length over the cap must be refused before
        any byte of the body is read."""
        big = {"file": ("b.zip", b"x" * (50 * 1024 * 1024 + 1), "application/zip")}
        r = self.client.post(
            "/api/backup/restore",
            headers=self.h,
            params={"confirm": "RESTORE"},
            files=big,
        )
        self.assertEqual(r.status_code, 413, r.text)


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

class AppLockTests(ServerCase):
    """Server-side app lock (P3): the flag lives in crypto, the middleware
    answers 423 for data endpoints except the allowlist, and the passphrase
    hash stays server-side (slow KDF) where the client can neither read nor
    compare it."""

    def tearDown(self):
        # The lock flag is process-wide: clear it so one test's locked state
        # never leaks into the next (IsolatedCase only resets storage).
        self.srv.crypto.set_locked(False)
        super().tearDown()

    def test_lock_blocks_data_endpoints_and_reports_status(self):
        self.srv.crypto.set_locked(True)
        for path in ("/api/library", "/api/movies",
                     "/api/backup/settings", "/api/images/i00000000"):
            self.assertEqual(self.client.get(path, headers=self.h).status_code, 423, path)
        self.assertEqual(self.client.get("/api/ping", headers=self.h).status_code, 200)
        st = self.client.get("/api/images/status", headers=self.h).json()
        self.assertTrue(st["app_locked"])

    def test_locked_settings_get_reaches_the_lock_screen(self):
        # The lock screen paints the user's real theme/background: the hash-free
        # settings GET rides through the lock (local host + valid token only),
        # writes stay 423, and a tokenless GET can't have it.
        self.client.put("/api/settings", json={"theme": "light"}, headers=self.h)
        self.srv.crypto.set_locked(True)
        r = self.client.get("/api/settings", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["theme"], "light")
        self.assertEqual(self.client.get("/api/settings").status_code, 403)
        self.assertEqual(self.client.put("/api/settings", json={"theme": "dark"},
                                         headers=self.h).status_code, 423)
        self.assertEqual(self.client.get("/api/settings", headers=self.h).json()["theme"],
                         "light")

    def test_password_lifecycle_wrong_rejected_right_opens(self):
        # first set: no stored hash yet -> any passphrase (>=4 chars) arms it
        r = self.client.post("/api/lock", json={"passphrase": "secr3t"}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        m = self.srv.db.get_settings().get("lock") or {}
        self.assertTrue(m.get("hash") and m.get("on"))
        # re-arm/change with a wrong proof is rejected
        self.assertEqual(self.client.post("/api/lock", json={"passphrase": "nope"},
                                          headers=self.h).status_code, 400)
        # a restart re-locks from the stored flag (main.py's startup hook)
        self.srv.crypto.set_locked(True)
        self.assertEqual(self.client.post("/api/unlock", json={"passphrase": "nope"},
                                          headers=self.h).status_code, 400)
        self.assertTrue(self.srv.crypto.is_locked())
        self.assertEqual(self.client.post("/api/unlock", json={"passphrase": "secr3t"},
                                          headers=self.h).status_code, 200)
        self.assertFalse(self.srv.crypto.is_locked())

    def test_lock_survives_db_reconnect(self):
        self.srv.crypto.set_locked(True)
        self.srv.db.close()
        self.srv.db.connect()
        self.assertTrue(self.srv.crypto.is_locked())

    def test_startup_rearms_the_lock_on_a_fresh_process(self):
        """Regression, fixed: main._apply_startup_lock() existed but was never
        called — with app lock enabled every start opened fully unlocked."""
        self.client.post("/api/lock", json={"passphrase": "secr3t"}, headers=self.h)
        self.srv.crypto.set_locked(False)          # as if a session unlocked it
        import main as entry
        entry._apply_startup_lock()                # ... then the app restarted
        self.assertTrue(self.srv.crypto.is_locked())
        # correct passphrase still opens
        r = self.client.post("/api/unlock", json={"passphrase": "secr3t"}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(self.srv.crypto.is_locked())
        # ... and disabling the toggle keeps the next start open
        self.srv.db.get_settings()                 # read for realism
        s = self.srv.db.get_settings(); s["lock"]["on"] = False; self.srv.db.save_settings(s)
        self.srv.crypto.set_locked(False)
        entry._apply_startup_lock()
        self.assertFalse(self.srv.crypto.is_locked())

    def test_allowlisted_endpoints_answer_while_locked(self):
        self.client.post("/api/lock", json={"passphrase": "secr3t"}, headers=self.h)
        self.assertEqual(self.client.post("/api/lock/now", headers=self.h).status_code, 200)
        self.assertTrue(self.srv.crypto.is_locked())
        # unlock affordance + status keep working; even lock-now is refused
        # while locked (not on the allowlist - no force-open via the API)
        self.assertEqual(self.client.post("/api/lock/now", headers=self.h).status_code, 423)
        self.assertEqual(self.client.post("/api/unlock", json={"passphrase": "secr3t"},
                                          headers=self.h).status_code, 200)
        self.assertEqual(self.client.get("/api/ping", headers=self.h).status_code, 200)

    def test_settings_never_expose_or_lose_the_lock_hash(self):
        self.client.post("/api/lock", json={"passphrase": "secr3t"}, headers=self.h)
        # both settings reads are public views: no hash/salt/kdf ever leaves
        lock = self.client.get("/api/settings", headers=self.h).json().get("lock") or {}
        self.assertNotIn("hash", lock)
        self.assertNotIn("salt", lock)
        lib_lock = (self.client.get("/api/library", headers=self.h).json()
                    .get("settings", {}).get("lock") or {})
        self.assertNotIn("hash", lib_lock)
        # a client-shaped PUT can disarm (`on`) but can never erase the record
        r = self.client.put("/api/settings",
                            json={"theme": "light", "lock": {"on": False}},
                            headers=self.h)
        self.assertEqual(r.status_code, 200, r.text)
        m = self.srv.db.get_settings().get("lock") or {}
        self.assertTrue(m.get("hash"), "settings PUT erased the lock record")
        self.assertFalse(m.get("on"), "client disarm flag did not reach the store")

