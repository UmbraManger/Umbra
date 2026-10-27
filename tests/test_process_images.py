"""Offline check: every image field a scraper result can carry gets
downloaded server-side and replaced with a local /api/images/<id> path."""

import unittest
from unittest import mock

import server


class FakeResp:
    content = b"jpg-bytes"
    headers = {"content-type": "image/jpeg"}
    status_code = 200

    def raise_for_status(self):
        pass


class ProcessImagesTests(unittest.TestCase):
    def _result(self):
        return {"posterF": "https://img.example/a.jpg",
                "posterB": "https://img.example/b.jpg",
                "thumbnail": "https://img.example/a.jpg",
                "covers": ["https://img.example/a.jpg", "https://img.example/b.jpg"],
                "photo": "https://img.example/p.jpg",
                "gallery": ["https://img.example/g1.jpg", "https://img.example/g2.jpg"]}

    def test_all_fields_local_and_deduped(self):
        ids = []
        def fake_store(data, mime):
            ids.append(1)
            return f"i{len(ids):08d}"

        with mock.patch.object(server.crypto, "store_image", side_effect=fake_store) as m_store, \
             mock.patch.object(server, "safe_get", return_value=FakeResp()) as m_get, \
             mock.patch.object(server, "safe_image_url", return_value=True):
            out = server._process_images(self._result())

            fields = [out["posterF"], out["posterB"], out["thumbnail"],
                      out["covers"][0], out["covers"][1], out["photo"],
                      out["gallery"][0], out["gallery"][1]]
            for p in fields:
                self.assertTrue(str(p).startswith("/api/images/"), p)
            # posterF/thumbnail/covers[0] share one download, posterB/covers[1] another
            self.assertEqual(out["posterF"], out["thumbnail"])
            self.assertEqual(out["posterF"], out["covers"][0])
            self.assertEqual(out["posterB"], out["covers"][1])
            # a, b, p, g1, g2 -> exactly 5 fetches, no per-key re-download
            self.assertEqual(m_get.call_count, 5)
            self.assertEqual(m_store.call_count, 5)

    def test_unsafe_url_kept_as_remote_link(self):
        with mock.patch.object(server, "safe_image_url", return_value=False):
            out = server._process_images({"posterF": "http://127.0.0.1/x.jpg"})
        self.assertEqual(out["posterF"], "http://127.0.0.1/x.jpg")

    def test_failed_download_kept_as_remote_link(self):
        with mock.patch.object(server, "safe_image_url", return_value=True), \
             mock.patch.object(server, "safe_get", side_effect=OSError("boom")):
            out = server._process_images({"posterF": "https://img.example/a.jpg"})
        self.assertEqual(out["posterF"], "https://img.example/a.jpg")

    def test_non_image_content_refused_keeps_remote_link(self):
        with mock.patch.object(FakeResp, "headers", {"content-type": "text/html"}), \
             mock.patch.object(server, "safe_get", return_value=FakeResp()), \
             mock.patch.object(server, "safe_image_url", return_value=True):
            out = server._process_images({"posterF": "https://img.example/h.html"})
        self.assertEqual(out["posterF"], "https://img.example/h.html")


if __name__ == "__main__":
    unittest.main()
