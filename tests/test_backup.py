import io
import json
import os
import sqlite3
import zipfile

import backup
import crypto
import db
import scrapers
from .helpers import IsolatedCase, known_bug

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(200))


def make_zip(files: dict, dirs=()) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
        for d in dirs:
            z.writestr(zipfile.ZipInfo(d), b"")
    return buf.getvalue()


def unzip(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


class BackupCase(IsolatedCase):
    def seed(self):
        db.execute("INSERT INTO movies(id,title,year) VALUES(?,?,?)", ("mv-1", "Alpha", 2020))
        db.save_settings({"theme": "dark"})
        self.img_id = crypto.store_image(PNG, "image/png")
        self.scraper_id = scrapers.add("site.yml", b"fields: {}", "movie")

    def titles(self):
        return [r["title"] for r in db.query("SELECT title FROM movies")]


class RoundTripTests(BackupCase):
    def test_export_then_restore_brings_everything_back(self):
        self.seed()
        data = backup.export_zip()
        db.execute("DELETE FROM movies")
        crypto.remove_image(self.img_id)
        scrapers.remove(self.scraper_id)
        self.assertEqual(self.titles(), [])

        backup.restore_zip(data)

        self.assertEqual(self.titles(), ["Alpha"])
        self.assertEqual(crypto.load_image(self.img_id)[0], PNG)
        self.assertEqual([s["id"] for s in scrapers.list_all()], [self.scraper_id])
        self.assertEqual(db.get_settings()["theme"], "dark")

    def test_restore_keeps_previous_library_as_prev(self):
        self.seed()
        data = backup.export_zip()
        db.execute("INSERT INTO movies(id,title) VALUES('mv-2','Beta')")
        backup.restore_zip(data)
        prev = sqlite3.connect(db.DB_PATH + ".prev")
        try:
            got = [r[0] for r in prev.execute("SELECT title FROM movies ORDER BY title")]
        finally:
            prev.close()
        self.assertEqual(got, ["Alpha", "Beta"])

    def test_export_blanks_the_ai_key_in_settings_json(self):
        self.seed()
        db.save_settings({"ai": {"on": True, "key": "sk-secret"}})
        files = unzip(backup.export_zip())
        self.assertEqual(json.loads(files["settings.json"])["ai"]["key"], "")


class RejectionTests(BackupCase):
    def setUp(self):
        super().setUp()
        self.seed()

    def assert_rejected_and_untouched(self, data, exc=ValueError):
        with self.assertRaises(exc):
            backup.restore_zip(data)
        self.assertEqual(self.titles(), ["Alpha"])                 # live DB untouched
        self.assertFalse(os.path.exists(db.DB_PATH + ".incoming"))

    def test_zip_slip_entries_are_rejected(self):
        for name in ("../evil.txt", "/abs.txt", "sub/../../evil.txt", "unknown/file.txt"):
            with self.subTest(name=name):
                self.assert_rejected_and_untouched(make_zip({name: b"x"}))
        self.assertFalse(os.path.exists(os.path.join(self._tmp, "evil.txt")))

    def test_backup_without_a_database_is_rejected(self):
        self.assert_rejected_and_untouched(make_zip({"settings.json": b"{}"}))

    def test_corrupt_database_is_rejected_and_live_data_survives(self):
        self.assert_rejected_and_untouched(make_zip({"obscura.db": b"not a database"}),
                                           exc=Exception)

    def test_foreign_sqlite_file_is_rejected(self):
        p = os.path.join(self._tmp, "foreign.db")
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE other(x)")
        con.commit()
        con.close()
        with open(p, "rb") as f:
            self.assert_rejected_and_untouched(make_zip({"obscura.db": f.read()}))


class KnownBugTests(BackupCase):
    def _rezip(self, data, **replace):
        files = unzip(data)
        files.update({k.replace("_", "."): v for k, v in replace.items()})
        return make_zip(files)

    @known_bug
    def test_backup_database_copy_must_not_contain_the_ai_key(self):
        """BUG (analysis #5, Phase 2): settings.json is scrubbed but obscura.db is
        copied verbatim, so a fallback-stored API key travels inside the zip."""
        self.seed()
        db.save_settings({"ai": {"on": True, "key": "sk-secret"}})
        raw = unzip(backup.export_zip())["obscura.db"]
        self.assertNotIn(b"sk-secret", raw)

    @known_bug
    def test_restore_locks_the_vault_again(self):
        """BUG (analysis #3, Phase 3): crypto._state['key'] survives a restore, so the
        vault claims to be unlocked with a key that may not match the restored data."""
        crypto.set_passphrase("pw12")
        self.seed()
        data = backup.export_zip()
        backup.restore_zip(data)
        self.assertFalse(crypto.status()["unlocked"])

    @known_bug
    def test_restore_tolerates_directory_entries_in_the_zip(self):
        """BUG (analysis #3, Phase 3): a directory entry ('encrypted/') crashes the
        restore AFTER the live database has already been replaced."""
        self.seed()
        db_bytes = unzip(backup.export_zip())["obscura.db"]
        backup.restore_zip(make_zip({"obscura.db": db_bytes}, dirs=["encrypted/"]))

    @known_bug
    def test_restore_never_enables_python_scrapers(self):
        """BUG (analysis #4, Phase 2): restored settings can switch on pyScrapers, so
        restoring someone else's backup becomes a code-execution path."""
        self.seed()
        data = self._rezip(backup.export_zip(), settings_json=b'{"pyScrapers": true}')
        backup.restore_zip(data)
        self.assertFalse(db.get_settings().get("pyScrapers"))
