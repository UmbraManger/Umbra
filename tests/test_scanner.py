import json
import os

import crypto
import db
import scanner
from .helpers import IsolatedCase


class TitleGuessTests(IsolatedCase):
    def test_dots_underscores_and_years_are_cleaned(self):
        self.assertEqual(scanner.guess_title("/x/The.Movie.2019.mkv"), "The Movie")
        self.assertEqual(scanner.guess_title("/x/my_cool video.mp4"), "My Cool Video")

    def test_extension_only_file_is_untitled(self):
        self.assertEqual(scanner.guess_title("/x/.mp4"), "Untitled")

    def test_apostrophes_are_not_capitalised(self):
        """Regression (analysis D4, fixed): per-word capitalize() keeps "Don't"."""
        self.assertEqual(scanner.guess_title("/x/don't.stop.mkv"), "Don't Stop")


class WalkTests(IsolatedCase):
    def test_walk_finds_only_videos_recursively_and_ignores_missing_dirs(self):
        a = self.tmpfile("lib/a.mp4")
        b = self.tmpfile("lib/sub/B.MKV")
        self.tmpfile("lib/notes.txt")
        root = os.path.dirname(a)
        found = {f["path"] for f in scanner.walk([root, os.path.join(root, "nope")])}
        self.assertEqual(found, {a, b})

    def test_walk_with_no_dirs_is_empty(self):
        self.assertEqual(scanner.walk([]), [])

    def test_overlapping_configured_dirs_scan_each_file_once(self):
        """Regression: C:\lib and C:\lib\sub both configured used to list every
        sub file twice in the Import From Scan dialog."""
        v = self.tmpfile("lib/sub/film.mp4")
        root = os.path.dirname(os.path.dirname(v))
        found = [f["path"] for f in scanner.walk([root, os.path.dirname(v)])]
        self.assertEqual(found, [v])


class KindGuessTests(IsolatedCase):
    def test_duration_is_the_strongest_signal(self):
        self.assertEqual(scanner.guess_kind("/x/a.mp4", duration_min=50), "movie")
        self.assertEqual(scanner.guess_kind("/x/a.mp4", duration_min=49), "scene")

    def test_probe_duration_of_a_missing_file_is_none(self):
        self.assertIsNone(scanner.probe_duration(os.path.join(self._tmp, "nope.mp4")))


class PosterTests(IsolatedCase):
    def test_posters_matching_the_video_stem_are_found(self):
        v = self.tmpfile("m/film.mp4")
        self.tmpfile("m/film.jpg")
        self.tmpfile("m/unrelated.jpg")
        names = [os.path.basename(p) for p in scanner.find_posters(v)]
        self.assertEqual(names, ["film.jpg"])

    def test_front_cover_comes_before_back_cover(self):
        """Regression (analysis D3, fixed): find_posters ranks front-ish names
        before back/rear artwork."""
        v = self.tmpfile("m/clip.mp4")
        self.tmpfile("m/front.jpg")
        self.tmpfile("m/back.jpg")
        names = [os.path.basename(p) for p in scanner.find_posters(v)]
        self.assertEqual(names, ["front.jpg", "back.jpg"])


class ResumeStateTests(IsolatedCase):
    def test_mark_check_and_remove_done(self):
        self.assertFalse(scanner.is_imported("/x/a.mp4"))
        scanner.mark_done("/x/a.mp4")
        scanner.mark_done("/x/a.mp4")                # idempotent
        self.assertTrue(scanner.is_imported("/x/a.mp4"))
        with open(scanner.RESUME, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["done"], ["/x/a.mp4"])
        scanner.remove_done("/x/a.mp4")
        self.assertFalse(scanner.is_imported("/x/a.mp4"))

    def test_corrupt_state_file_falls_back_to_empty(self):
        with open(scanner.RESUME, "w") as f:
            f.write("{not json")
        self.assertFalse(scanner.is_imported("/x/a.mp4"))


class ImportTests(IsolatedCase):
    def test_import_movie_creates_row_stores_posters_and_marks_done(self):
        v = self.tmpfile("m/film.mp4", b"video")
        self.tmpfile("m/film.jpg", b"\xff\xd8front")
        rec = scanner.import_file(v, "movie", "Film", year=2001, duration_min=95,
                                  actor_ids=["p-1"], category_ids=["c-1"])
        row = db.one("SELECT * FROM movies WHERE id=?", (rec["id"],))
        self.assertEqual((row["title"], row["year"], row["duration_min"]),
                         ("Film", 2001, 95))
        self.assertEqual(json.loads(row["actor_ids"]), ["p-1"])
        self.assertTrue(row["poster_f"].startswith("/api/images/i"))
        img_id = row["poster_f"].rsplit("/", 1)[1]
        self.assertEqual(crypto.load_image(img_id)[0], b"\xff\xd8front")
        self.assertTrue(scanner.is_imported(v))

    def test_import_scene_links_to_movie_and_uses_cover_columns(self):
        v = self.tmpfile("s/scene.mp4")
        self.tmpfile("s/scene.png", b"\x89PNGcover")
        rec = scanner.import_file(v, "scene", "", date="2020-01-02", movie_id="mv-9")
        row = db.one("SELECT * FROM scenes WHERE id=?", (rec["id"],))
        self.assertEqual((row["title"], row["date"], row["movie_id"]),
                         ("Scene", "2020-01-02", "mv-9"))
        self.assertTrue(row["cover_a"].startswith("/api/images/i"))
        self.assertEqual(row["cover_b"], "")


class NoConsoleWindowTests(IsolatedCase):
    def test_ffprobe_is_spawned_without_a_console_window(self):
        """Regression (bug report): Windows popped one black CMD window per
        scanned file, because ffprobe was spawned without CREATE_NO_WINDOW."""
        from unittest import mock
        seen = {}

        def fake(*args, **kw):
            seen.update(kw)
            raise RuntimeError("no ffprobe in tests")

        with mock.patch.object(scanner.subprocess, "run", fake):
            self.assertIsNone(scanner.probe_duration("/x/a.mp4"))
        self.assertIn("creationflags", seen)              # the kwarg is passed
        self.assertEqual(seen["creationflags"], scanner._NO_WIN)
