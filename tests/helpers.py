"""Shared test plumbing.

Every test that touches storage runs against a throw-away temp folder: the
module-level paths in db / crypto / scanner / scrapers are re-pointed before the
test and restored afterwards, so the real ``data/`` folder is never opened.
"""
import faulthandler
import os
import shutil
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Safety net: several known bugs are deadlocks. If the run ever hangs, dump every
# thread's stack and exit instead of freezing the terminal forever.
faulthandler.dump_traceback_later(240, exit=True)


def _find_backend() -> str:
    for cand in (os.path.join(ROOT, "backend"), os.path.join(ROOT, "src"), ROOT):
        if os.path.isfile(os.path.join(cand, "db.py")) and \
                os.path.isfile(os.path.join(cand, "crypto.py")):
            return cand
    raise RuntimeError("Could not find the backend folder (db.py / crypto.py). "
                       "Expected ./backend, ./src or the project root.")


BACKEND = _find_backend()
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# Importing these only defines constants; nothing here opens a database.
import db        # noqa: E402
import crypto    # noqa: E402
import scanner   # noqa: E402
import scrapers  # noqa: E402

def known_bug(fn):
    """Mark a test that documents a bug from the code analysis.

    Normally this is unittest.expectedFailure: the suite stays green while the bug
    exists, and turns RED ("unexpected success") the moment someone fixes it, which is
    the reminder to delete the decorator. Set OBSCURA_SHOW_BUGS=1 to run these tests
    as ordinary tests and see the real failure output."""
    if os.environ.get("OBSCURA_SHOW_BUGS"):
        return fn
    return unittest.expectedFailure(fn)


FAST_KDF = {"type": "pbkdf2", "iterations": 1000}


class IsolatedCase(unittest.TestCase):
    """Base class: fresh temp data folder + reset module state for each test."""

    fast_kdf = True       # set False on a class to exercise the real KDF choice
    auto_connect = True   # the real app connects at import (server.py); mimic that.
    # NOTE: db.query/one/execute deadlock if called before db.connect() (known bug),
    # so tests that need a pre-built database file set auto_connect = False.

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="obscura_test_")
        self.data = os.path.join(self._tmp, "data")
        self._saved = {
            "db": {k: getattr(db, k) for k in
                   ("DATA_DIR", "POSTER_DIR", "SCRAPER_DIR", "DB_PATH")},
            "crypto": {k: getattr(crypto, k) for k in ("ENC_DIR", "META", "_best_kdf")},
            "scanner": scanner.RESUME,
            "scrapers": scrapers.META,
        }
        db.close()
        # A test that deadlocks db leaves the old lock held forever; start clean.
        db._lock = threading.Lock()
        db.DATA_DIR = self.data
        db.POSTER_DIR = os.path.join(self.data, "posters")
        db.SCRAPER_DIR = os.path.join(self.data, "scrapers")
        db.DB_PATH = os.path.join(self.data, "obscura.db")
        crypto.ENC_DIR = os.path.join(self.data, "encrypted")
        crypto.META = os.path.join(self.data, "imgprot.json")
        crypto._state["key"] = None
        if self.fast_kdf:
            crypto._best_kdf = lambda: dict(FAST_KDF)
        scanner.RESUME = os.path.join(self.data, "scanstate.json")
        scrapers.META = os.path.join(db.SCRAPER_DIR, "meta.json")
        db.ensure_dirs()
        if self.auto_connect:
            db.connect()

    def tearDown(self):
        db.close()
        crypto._state["key"] = None
        for k, v in self._saved["db"].items():
            setattr(db, k, v)
        for k, v in self._saved["crypto"].items():
            setattr(crypto, k, v)
        scanner.RESUME = self._saved["scanner"]
        scrapers.META = self._saved["scrapers"]
        shutil.rmtree(self._tmp, ignore_errors=True)

    # small conveniences ------------------------------------------------
    def tmpfile(self, relpath: str, content: bytes = b"x") -> str:
        p = os.path.join(self._tmp, "files", relpath)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(content)
        return p
