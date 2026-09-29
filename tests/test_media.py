import os

import db
import media
from .helpers import IsolatedCase, known_bug


class RangeParsingTests(IsolatedCase):
    def test_no_or_malformed_header_means_whole_file(self):
        self.assertIsNone(media.parse_range(None, 100))
        self.assertIsNone(media.parse_range("", 100))
        self.assertIsNone(media.parse_range("bytes=abc", 100))
        self.assertIsNone(media.parse_range("bytes=-", 100))

    def test_closed_open_ended_and_suffix_ranges(self):
        self.assertEqual(media.parse_range("bytes=0-9", 100), (0, 9))
        self.assertEqual(media.parse_range("bytes=90-", 100), (90, 99))
        self.assertEqual(media.parse_range("bytes=-10", 100), (90, 99))
        self.assertEqual(media.parse_range("bytes=-500", 100), (0, 99))
        self.assertEqual(media.parse_range("bytes=50-5000", 100), (50, 99))

    def test_unsatisfiable_ranges_raise(self):
        for hdr, size in (("bytes=100-", 100), ("bytes=50-10", 100),
                          ("bytes=-0", 100), ("bytes=0-1", 0)):
            with self.subTest(hdr=hdr, size=size):
                with self.assertRaises(media.RangeNotSatisfiable):
                    media.parse_range(hdr, size)


class StreamingTests(IsolatedCase):
    def test_iter_file_whole_slice_and_tail(self):
        data = bytes(range(256)) * 5000                # > one 512 KB chunk
        p = self.tmpfile("v.mp4", data)
        self.assertEqual(b"".join(media.iter_file(p)), data)
        self.assertEqual(b"".join(media.iter_file(p, 10, 100)), data[10:110])
        self.assertEqual(b"".join(media.iter_file(p, 1000)), data[1000:])


class MimeTests(IsolatedCase):
    def test_known_video_types(self):
        self.assertEqual(media.mime_for("a.MKV"), "video/x-matroska")
        self.assertEqual(media.mime_for("a.mp4"), "video/mp4")

    @known_bug
    def test_non_video_files_are_never_served_as_html(self):
        """BUG (analysis, Phase 2): unknown extensions fall back to mimetypes, so an
        imported .html file is served as text/html from the app's own origin."""
        self.assertFalse(media.mime_for("evil.html").startswith("text/"))


class SubtitleTests(IsolatedCase):
    def test_sidecar_subs_match_the_video_stem(self):
        v = self.tmpfile("v/movie.mp4")
        self.tmpfile("v/movie.srt")
        self.tmpfile("v/movie.en.srt")
        self.tmpfile("v/other.srt")
        names = sorted(s["name"] for s in media.sidecar_subs(v))
        self.assertEqual(names, ["movie.en.srt", "movie.srt"])

    def test_srt_becomes_webvtt(self):
        p = self.tmpfile("s.srt", "\ufeff1\n00:00:01,500 --> 00:00:02,000\nHi\n".encode())
        out = media.srt_to_vtt(p).decode()
        self.assertTrue(out.startswith("WEBVTT\n\n"))
        self.assertIn("00:00:01.500 --> 00:00:02.000", out)

    @known_bug
    def test_short_video_stem_does_not_match_unrelated_subtitles(self):
        """BUG (analysis, Phase 4): `stem in filename` is a substring test, so a
        video named a.mp4 picks up banana.srt."""
        v = self.tmpfile("v/a.mp4")
        self.tmpfile("v/banana.srt")
        self.assertEqual(media.sidecar_subs(v), [])

    @known_bug
    def test_vtt_input_does_not_get_a_second_header(self):
        """BUG (analysis, Phase 4): .vtt files are wrapped in another WEBVTT header."""
        p = self.tmpfile("s.vtt", b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n")
        self.assertEqual(media.srt_to_vtt(p).decode().count("WEBVTT"), 1)


class PathLookupTests(IsolatedCase):
    def _movie(self, path):
        db.execute("INSERT INTO movies(id,title,file_path) VALUES('mv-1','T',?)", (path,))

    def test_get_path_returns_only_existing_files_of_known_kinds(self):
        p = self.tmpfile("v.mp4")
        self._movie(p)
        self.assertEqual(media.get_path("movie", "mv-1"), p)
        self.assertIsNone(media.get_path("bogus", "mv-1"))
        self.assertIsNone(media.get_path("movie", "missing"))
        db.execute("UPDATE movies SET file_path=? WHERE id='mv-1'",
                   (os.path.join(self._tmp, "gone.mp4"),))
        self.assertIsNone(media.get_path("movie", "mv-1"))

    @known_bug
    def test_files_outside_the_scan_folders_are_not_served(self):
        """BUG (analysis #1, Phase 2): any path stored in file_path can be streamed,
        e.g. imgprot.json or the database itself."""
        inside = os.path.join(self._tmp, "library")
        os.makedirs(inside)
        db.save_settings({"dirs": [inside]})
        outside = self.tmpfile("secret/notes.mp4")
        self._movie(outside)
        self.assertIsNone(media.get_path("movie", "mv-1"))
