"""Backup / restore — one .zip containing the database snapshot, encrypted
images, installed scrapers, image-protection and scan state, and settings
(API key excluded — it lives in the keyring)."""
import os, io, json, shutil, zipfile, sqlite3
import db
import crypto

NAME_DB, NAME_SET, NAME_IMG, NAME_SCAN = "obscura.db", "settings.json", "imgprot.json", "scanstate.json"

def _safe_members(zf: zipfile.ZipFile) -> list[str]:
    bad = []
    for n in zf.namelist():
        parts = n.replace("\\", "/").split("/")
        if n.startswith("/") or ".." in parts or parts[0] not in (
                NAME_DB, NAME_SET, NAME_IMG, NAME_SCAN, "encrypted", "scrapers"):
            bad.append(n)
    return bad

def export_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        tmp = db.DB_PATH + ".bak"
        dst = sqlite3.connect(tmp)
        try:
            with dst:
                db.connect().backup(dst)
            # The copy inherits the source's WAL header, so without this switch a
            # later UPDATE would go to a '.bak-wal' sidecar and the main file
            # written into the zip would keep the OLD bytes. Rollback-journal mode
            # makes the scrub land in the file we actually ship.
            dst.execute("PRAGMA journal_mode=DELETE")
            # The settings.json entry below is scrubbed, but the DB *copy* would
            # otherwise carry a fallback-stored API key verbatim. Blank it and
            # VACUUM so the old bytes are gone from the file, not just unlinked
            # (bug #5: a key must never travel inside the backup).
            _scrub_ai_key(dst)
            z.write(tmp, NAME_DB)
        finally:
            dst.close()
            for suffix in ("", "-wal", "-shm"):
                try: os.remove(tmp + suffix)
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
        s = db.get_settings()
        if isinstance(s, dict) and isinstance(s.get("ai"), dict):
            s = dict(s); s["ai"] = dict(s["ai"]); s["ai"]["key"] = ""
        z.writestr(NAME_SET, json.dumps(s, indent=2))
    return buf.getvalue()


def _scrub_ai_key(con: sqlite3.Connection) -> None:
    """Blank the fallback-stored AI key inside a DB snapshot, then VACUUM so it
    is physically gone from the file (an UPDATE alone would leave the old value
    in freed pages, still readable in the raw bytes)."""
    try:
        row = con.execute("SELECT value FROM settings WHERE key='app'").fetchone()
        if not row or not row[0]:
            return
        s = json.loads(row[0])
        if not (isinstance(s, dict) and isinstance(s.get("ai"), dict)
                and s["ai"].get("key")):
            return
        s["ai"] = dict(s["ai"]); s["ai"]["key"] = ""
        with con:
            con.execute("UPDATE settings SET value=? WHERE key='app'", (json.dumps(s),))
        con.execute("VACUUM")
    except Exception:
        pass          # never fail an export over scrubbing; best effort only

def restore_zip(data: bytes) -> int:
    zf = zipfile.ZipFile(io.BytesIO(data))
    bad = _safe_members(zf)
    if bad: raise ValueError("unsafe entries in backup: " + ", ".join(bad[:3]))
    if NAME_DB not in zf.namelist():
        raise ValueError("backup does not contain obscura.db")
    db.ensure_dirs()

    # Stage the payload BEFORE the live DB is replaced: directory entries
    # ('encrypted/') only record a folder to recreate, file entries are read
    # into a staging dir here (CRC-checked). A corrupt member or structural
    # problem therefore aborts while the old library is still fully in place —
    # never with the database already swapped in (half-restored state).
    stage = os.path.join(db.DATA_DIR, ".restore-stage")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    file_entries = []            # (staged path, final dest)
    dir_entries = []             # final dirs to recreate
    try:
        for name in zf.namelist():
            if name == NAME_DB: continue
            if not (name in (NAME_IMG, NAME_SCAN, NAME_SET) or
                    name.startswith("encrypted/") or name.startswith("scrapers/")):
                continue
            if name.endswith("/"):
                dir_entries.append(os.path.join(
                    db.DATA_DIR, name.rstrip("/").replace("/", os.sep)))
                continue
            dest = os.path.join(db.DATA_DIR, name.replace("/", os.sep))
            sp = os.path.join(stage, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            with zf.open(name) as src, open(sp, "wb") as out:
                shutil.copyfileobj(src, out)   # raises on corrupt member
            file_entries.append((sp, dest))
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    # Stage and validate the incoming DB BEFORE it replaces the live one.
    staged = db.DB_PATH + ".incoming"
    try:
        with zf.open(NAME_DB) as src, open(staged, "wb") as out:
            shutil.copyfileobj(src, out)     # raises on corrupt member
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
            raise ValueError("backup database is not an Umbra library — restore aborted")
    except Exception:
        try: os.remove(staged)
        except OSError: pass
        shutil.rmtree(stage, ignore_errors=True)
        raise
    db.close()
    for suffix in ("-wal", "-shm"):
        try: os.remove(db.DB_PATH + suffix)
        except OSError: pass
    # Keep the previous library as obscura.db.prev (manual rollback point).
    if os.path.exists(db.DB_PATH):
        shutil.copy2(db.DB_PATH, db.DB_PATH + ".prev")
    os.replace(staged, db.DB_PATH)
    # Both sides are already verified: only renames remain. If one fails the
    # staging dir is kept for manual recovery.
    for d in dir_entries:
        os.makedirs(d, exist_ok=True)
    for sp, dest in file_entries:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        os.replace(sp, dest)
    shutil.rmtree(stage, ignore_errors=True)
    db.connect()
    # A restored vault must never claim to be unlocked: the key in memory was
    # derived for the OLD library, so lock it and let the user unlock again
    # (bug #B5).
    crypto.lock()
    if NAME_SET in zf.namelist():
        try:
            s = json.loads(zf.read(NAME_SET).decode("utf-8"))
            if isinstance(s, dict):
                s["pyScrapers"] = False        # never enable code execution (bug #B4)
                db.save_settings(s)
        except Exception: pass
    # Belt-and-braces: a zip without settings.json still carries a settings ROW
    # inside its DB copy — force the code-execution gate back off either way.
    cur = db.get_settings()
    if cur.get("pyScrapers"):
        cur["pyScrapers"] = False
        db.save_settings(cur)
    return len(zf.namelist())
