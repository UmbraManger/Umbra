"""SQLite storage — everything lives in data/ next to the executable (portable).

Schema changes are versioned via PRAGMA user_version (see SCHEMA_VERSION /
_MIGRATIONS) so `migrate()` is ordered and idempotent instead of a pile of
try/except ALTERs. Existing pre-versioning databases start at 0; every
migration step is idempotent (ADD COLUMN failures for columns that already
exist are ignored) so they converge safely.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import uuid
from typing import Any, Sequence

SCHEMA_VERSION = 2


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


DATA_DIR: str = os.path.join(app_dir(), "data")
POSTER_DIR: str = os.path.join(DATA_DIR, "posters")
SCRAPER_DIR: str = os.path.join(DATA_DIR, "scrapers")
DB_PATH: str = os.path.join(DATA_DIR, "obscura.db")


def ensure_dirs() -> None:
    for d in (DATA_DIR, POSTER_DIR, SCRAPER_DIR):
        os.makedirs(d, exist_ok=True)


_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                ensure_dirs()
                _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                _conn.row_factory = sqlite3.Row
                _conn.execute("PRAGMA journal_mode=WAL")
                _migrate()
    return _conn


def close() -> None:
    """Close the shared connection (used by backup/restore)."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS studios(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT DEFAULT '',
  country TEXT DEFAULT '', desc TEXT DEFAULT '', created_at TEXT,
  logo TEXT DEFAULT '', twitter TEXT DEFAULT '', instagram TEXT DEFAULT '',
  parent_id TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS categories(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT DEFAULT 'tag', desc TEXT DEFAULT '',
  created_at TEXT);
CREATE TABLE IF NOT EXISTS performers(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, gender TEXT DEFAULT 'f',
  aliases TEXT DEFAULT '', birth TEXT, ethnicity TEXT DEFAULT '',
  height INTEGER, weight INTEGER, hair TEXT DEFAULT '', eyes TEXT DEFAULT '',
  measurements TEXT, boobs TEXT, piercings TEXT DEFAULT '', tattoos TEXT DEFAULT '',
  career_start INTEGER, photo TEXT DEFAULT '', created_at TEXT,
  twitter TEXT DEFAULT '', instagram TEXT DEFAULT '', onlyfans TEXT DEFAULT '',
  urls TEXT DEFAULT '', nationality TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS movies(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, year INTEGER, studio_id TEXT,
  duration_min INTEGER DEFAULT 0, scenes INTEGER DEFAULT 0, director TEXT DEFAULT '',
  desc TEXT DEFAULT '', poster_f TEXT DEFAULT '', poster_b TEXT DEFAULT '',
  fav INTEGER DEFAULT 0, file_path TEXT DEFAULT '', created_at TEXT,
  actor_ids TEXT DEFAULT '[]', category_ids TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS scenes(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, date TEXT, studio_id TEXT, movie_id TEXT,
  duration_min INTEGER DEFAULT 0, director TEXT DEFAULT '', desc TEXT DEFAULT '',
  cover_a TEXT DEFAULT '', cover_b TEXT DEFAULT '', thumb INTEGER DEFAULT 0,
  fav INTEGER DEFAULT 0, file_path TEXT DEFAULT '', created_at TEXT,
  actor_ids TEXT DEFAULT '[]', category_ids TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS positions(
  media_id TEXT PRIMARY KEY, position REAL NOT NULL DEFAULT 0, updated_at TEXT);
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# Ordered column migrations: version -> [(table, "column TYPE DEFAULT ..."), ...]
# Every step is idempotent: ADD COLUMN on an existing column raises
# OperationalError, which is expected and ignored (pre-versioning DBs may
# already carry columns from any step).
_MIGRATIONS: dict[int, list[tuple[str, str]]] = {
    1: [
        ("studios", "created_at TEXT"),
        ("categories", "created_at TEXT"),
        ("studios", "logo TEXT DEFAULT ''"),
        ("studios", "twitter TEXT DEFAULT ''"),
        ("studios", "instagram TEXT DEFAULT ''"),
        ("studios", "parent_id TEXT DEFAULT ''"),
        ("performers", "twitter TEXT DEFAULT ''"),
        ("performers", "instagram TEXT DEFAULT ''"),
        ("performers", "onlyfans TEXT DEFAULT ''"),
        ("performers", "urls TEXT DEFAULT ''"),
        ("performers", "nationality TEXT DEFAULT ''"),
    ],
    2: [
        ("scenes", "gallery TEXT DEFAULT '[]'"),
    ],
}


def _migrate() -> None:
    c = connect()
    c.executescript(SCHEMA)
    ver: int = c.execute("PRAGMA user_version").fetchone()[0]
    for version in range(ver + 1, SCHEMA_VERSION + 1):
        for table, column_def in _MIGRATIONS.get(version, []):
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
            except sqlite3.OperationalError:
                pass  # column already exists
    if ver != SCHEMA_VERSION:
        c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    c.commit()


def query(sql: str, params: Sequence[Any] = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in connect().execute(sql, params).fetchall()]


def one(sql: str, params: Sequence[Any] = ()) -> dict | None:
    with _lock:
        rows = [dict(r) for r in connect().execute(sql, params).fetchall()]
        return rows[0] if rows else None


def execute(sql: str, params: Sequence[Any] = ()) -> None:
    with _lock:
        c = connect()
        c.execute(sql, params)
        c.commit()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def get_settings() -> dict:
    row = one("SELECT value FROM settings WHERE key='app'")
    if row:
        try:
            return json.loads(row["value"])
        except Exception:
            pass
    return {}


def save_settings(s: dict) -> None:
    execute("INSERT INTO settings(key,value) VALUES('app',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(s),))


def get_scraper_sites() -> dict:
    s = get_settings()
    return s.get("scraperSites", {})


def add_scraper_site(kind: str, scraper_id: str, domain: str) -> None:
    s = get_settings()
    s.setdefault("scraperSites", {})
    s["scraperSites"].setdefault(kind, [])
    s["scraperSites"][kind].append({"scraper_id": scraper_id, "domain": domain})
    save_settings(s)


def del_scraper_site(kind: str, idx: int) -> None:
    s = get_settings()
    if "scraperSites" in s and kind in s["scraperSites"]:
        s["scraperSites"][kind].pop(idx)
        if not s["scraperSites"][kind]:
            del s["scraperSites"][kind]
        if not s["scraperSites"]:
            del s["scraperSites"]
    save_settings(s)
