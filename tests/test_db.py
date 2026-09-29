import os
import sqlite3
import threading
import unittest

import db
from .helpers import IsolatedCase, known_bug


class SchemaTests(IsolatedCase):
    def test_fresh_database_is_at_current_schema_version(self):
        db.connect()
        self.assertEqual(db.query("PRAGMA user_version")[0]["user_version"],
                         db.SCHEMA_VERSION)
        tables = {r["name"] for r in
                  db.query("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"movies", "scenes", "performers", "studios",
                         "categories", "positions", "settings"} <= tables)


class MigrationTests(IsolatedCase):
    auto_connect = False

    def test_old_unversioned_database_is_migrated_and_keeps_its_data(self):
        con = sqlite3.connect(db.DB_PATH)
        con.executescript("""
            CREATE TABLE studios(id TEXT PRIMARY KEY, name TEXT NOT NULL,
              url TEXT DEFAULT '', country TEXT DEFAULT '', desc TEXT DEFAULT '');
            CREATE TABLE performers(id TEXT PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE scenes(id TEXT PRIMARY KEY, title TEXT NOT NULL, date TEXT,
              studio_id TEXT, movie_id TEXT, duration_min INTEGER DEFAULT 0,
              director TEXT DEFAULT '', desc TEXT DEFAULT '', cover_a TEXT DEFAULT '',
              cover_b TEXT DEFAULT '', thumb INTEGER DEFAULT 0, fav INTEGER DEFAULT 0,
              file_path TEXT DEFAULT '', created_at TEXT,
              actor_ids TEXT DEFAULT '[]', category_ids TEXT DEFAULT '[]');
            INSERT INTO studios(id,name) VALUES('st-1','Old Studio');
        """)
        con.commit()
        con.close()

        db.connect()
        cols = lambda t: {r["name"] for r in db.query(f"PRAGMA table_info({t})")}
        self.assertTrue({"logo", "twitter", "instagram", "parent_id"} <= cols("studios"))
        self.assertIn("nationality", cols("performers"))
        self.assertIn("gallery", cols("scenes"))
        self.assertEqual(db.one("SELECT name FROM studios WHERE id='st-1'")["name"],
                         "Old Studio")

    def test_migrating_twice_is_harmless(self):
        db.connect()
        db.close()
        db.connect()
        self.assertEqual(db.query("PRAGMA user_version")[0]["user_version"],
                         db.SCHEMA_VERSION)


class SettingsTests(IsolatedCase):
    def test_settings_round_trip_and_replace(self):
        self.assertEqual(db.get_settings(), {})
        db.save_settings({"theme": "dark", "dirs": ["/x"]})
        self.assertEqual(db.get_settings()["dirs"], ["/x"])
        db.save_settings({"theme": "light"})          # whole-object replace
        self.assertEqual(db.get_settings(), {"theme": "light"})

    def test_scraper_sites_add_and_delete(self):
        db.add_scraper_site("movie", "s1", "a.example")
        db.add_scraper_site("movie", "s2", "b.example")
        self.assertEqual(len(db.get_scraper_sites()["movie"]), 2)
        db.del_scraper_site("movie", 0)
        self.assertEqual(db.get_scraper_sites()["movie"][0]["scraper_id"], "s2")
        db.del_scraper_site("movie", 0)
        self.assertEqual(db.get_scraper_sites(), {})

    def test_new_id_has_prefix_and_is_unique(self):
        ids = {db.new_id("mv") for _ in range(200)}
        self.assertEqual(len(ids), 200)
        self.assertTrue(all(i.startswith("mv-") for i in ids))


class KnownBugTests(IsolatedCase):
    @known_bug
    def test_query_after_close_reconnects_instead_of_deadlocking(self):
        """BUG (analysis #1, Phase 3): query() holds _lock, then connect() tries to
        take the same non-reentrant lock when the connection was closed."""
        db.connect()
        db.close()
        result = []
        t = threading.Thread(target=lambda: result.append(db.query("SELECT 1 AS x")),
                             daemon=True)
        t.start()
        t.join(3)
        self.assertFalse(t.is_alive(), "db.query deadlocked after db.close()")
