"""Backup / restore — one .zip containing the database snapshot, encrypted
images, installed scrapers, image-protection and scan state, and settings
(AI API key blanked — in settings.json AND in the database snapshot)."""
import os, io, json, shutil, zipfile, sqlite3
import db

NAME_DB, NAME_SET, NAME_IMG, NAME_SCAN = "obscura.db", "settings.json", "imgprot.json", "scanstate.json"

def _scrub_ai_key(s: dict) -> dict:
    """Copy of a settings dict with the AI API key blanked (C1)."""
    s = dict(s)
    if isinstance(s.get("ai"), dict):
        s["ai"] = dict(s["ai"]); s["ai"]["key"] = ""
    return s

def _member_ok(n: str) -> bool:
    """The exact layout export_zip writes: the four top-level files plus one
    level of files under encrypted/ and scrapers/. Anything else — including
    bare "encrypted"/"scrapers" entries that would collide with the live
    directories — is rejected (single validation shared by check & extract)."""
    parts = n.replace("\\", "/").split("/")
    if n.startswith("/") or ".." in parts:
        return False
    if parts[0] in (NAME_DB, NAME_SET, NAME_IMG, NAME_SCAN):
        return len(parts) == 1
    return parts[0] in ("encrypted", "scrapers") and len(parts) == 2 and bool(parts[1])

def _safe_members(zf: zipfile.ZipFile) -> list[str]:
    bad = []
    for n in zf.namelist():
        if n.endswith("/"):
            continue  # directory entry: nothing to extract, ignored
        if not _member_ok(n):
            bad.append(n)
    return bad

def export_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        tmp = db.DB_PATH + ".bak"
        dst = sqlite3.connect(tmp)
        try:
            with db._lock:   # snapshot the shared connection without racing writes
                with dst:
                    db.connect().backup(dst)
            # C1: the AI key also lives in the settings row *inside* the DB
            # snapshot — scrub it there too, not just in settings.json.
            row = dst.execute("SELECT value FROM settings WHERE key='app'").fetchone()
            if row is not None:
                try:
                    s2 = json.loads(row[0])
                    if not isinstance(s2, dict):
                        raise ValueError("not a JSON object")
                    dst.execute("UPDATE settings SET value=? WHERE key='app'",
                                (json.dumps(_scrub_ai_key(s2)),))
                except Exception:
                    # unparseable row: drop it rather than risk exporting a key
                    dst.execute("DELETE FROM settings WHERE key='app'")
                dst.commit()
            z.write(tmp, NAME_DB)
        finally:
            dst.close()
            try: os.remove(tmp)
            except OSError: pass
        for folder, arc in ((os.path.join(db.DATA_DIR, "encrypted"), "encrypted"),
                            (db.SCRAPER_DIR, "scrapers")):
            if os.path.isdir(folder):
                for fn in os.listdir(folder):
                    p = os.path.join(folder, fn)
                    if os.path.isfile(p):
                        z.write(p, arc + "/" + fn)
        for src_path, arc in ((os.path.join(db.DATA_DIR, NAME_IMG), NAME_IMG),
                              (os.path.join(db.DATA_DIR, NAME_SCAN), NAME_SCAN)):
            if os.path.isfile(src_path):
                z.write(src_path, arc)
        try:
            s = db.get_settings()
        except Exception:
            s = {}   # corrupt live row — never export a possibly-live key
        z.writestr(NAME_SET, json.dumps(_scrub_ai_key(s), indent=2))
    return buf.getvalue()

def restore_zip(data: bytes) -> int:
    zf = zipfile.ZipFile(io.BytesIO(data))
    bad = _safe_members(zf)
    if bad: raise ValueError("unsafe entries in backup: " + ", ".join(bad[:3]))
    names = zf.namelist()
    if NAME_DB not in names:
        raise ValueError("backup does not contain obscura.db")
    db.ensure_dirs()
    # ---- stage & validate EVERYTHING before touching any live data ----
    stage = os.path.join(db.DATA_DIR, ".restore-stage")
    shutil.rmtree(stage, ignore_errors=True)
    staged = os.path.join(stage, NAME_DB)
    try:
        os.makedirs(stage)
        bad_crc = zf.testzip()   # reads + CRC-checks every member up front
        if bad_crc:
            raise ValueError(
                f"backup archive is corrupt (bad CRC on {bad_crc}) — restore aborted")
        for name in names:
            if name.endswith("/"):
                continue
            dest = os.path.join(stage, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(name) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)   # disk-full/short-read hits here
        if not os.path.isfile(staged):
            raise ValueError("backup does not contain obscura.db")
        con = sqlite3.connect(staged)
        try:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            tables = {r[0] for r in
                      con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
        if integrity != "ok":
            raise ValueError("backup database failed the integrity check — restore aborted")
        if not {"settings", "movies", "scenes"}.issubset(tables):
            raise ValueError("backup database is not an Obscura library — restore aborted")
        # ---- commit: swap files + DB; the undo journal makes this all-or-nothing ----
        db.close()
        done = []   # (dest, held|None): applied moves, reversed on failure
        try:
            for name in names:
                if name == NAME_DB or name.endswith("/"):
                    continue
                src = os.path.join(stage, name.replace("/", os.sep))
                dest = os.path.join(db.DATA_DIR, name.replace("/", os.sep))
                if os.path.isdir(dest):
                    raise ValueError(f"backup entry {name} collides with a directory")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                held = None
                if os.path.exists(dest):
                    held = os.path.join(stage, ".displaced", name.replace("/", os.sep))
                    os.makedirs(os.path.dirname(held), exist_ok=True)
                    os.replace(dest, held)   # keep the old file for rollback
                os.replace(src, dest)
                done.append((dest, held))
            for suffix in ("-wal", "-shm"):
                try: os.remove(db.DB_PATH + suffix)
                except OSError: pass
            # Keep the previous library as obscura.db.prev (manual rollback point).
            if os.path.exists(db.DB_PATH):
                shutil.copy2(db.DB_PATH, db.DB_PATH + ".prev")
            os.replace(staged, db.DB_PATH)   # DB swapped last, only after files
        except Exception:
            for dest, held in reversed(done):   # leave existing data untouched
                try:
                    if held is None: os.remove(dest)
                    else: os.replace(held, dest)
                except OSError:
                    pass
            raise
        finally:
            db.connect()   # never leave the DB closed (H2 window)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    if NAME_SET in names:
        try:
            s = json.loads(zf.read(NAME_SET).decode("utf-8"))
            if isinstance(s, dict): db.save_settings(s)
        except Exception: pass
    return len(names)
