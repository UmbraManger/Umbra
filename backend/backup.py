"""Backup / restore — one .zip containing the database snapshot, encrypted
images, installed scrapers, image-protection and scan state, and settings
(API key excluded — it lives in the keyring)."""
import os, io, json, shutil, zipfile, sqlite3
import db

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
        s = db.get_settings()
        if isinstance(s, dict) and isinstance(s.get("ai"), dict):
            s = dict(s); s["ai"] = dict(s["ai"]); s["ai"]["key"] = ""
        z.writestr(NAME_SET, json.dumps(s, indent=2))
    return buf.getvalue()

def restore_zip(data: bytes) -> int:
    zf = zipfile.ZipFile(io.BytesIO(data))
    bad = _safe_members(zf)
    if bad: raise ValueError("unsafe entries in backup: " + ", ".join(bad[:3]))
    if NAME_DB not in zf.namelist():
        raise ValueError("backup does not contain obscura.db")
    db.ensure_dirs()
    # Stage and validate the incoming DB BEFORE it replaces the live one.
    staged = db.DB_PATH + ".incoming"
    with zf.open(NAME_DB) as src, open(staged, "wb") as out:
        out.write(src.read())
    try:
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
    except Exception:
        try: os.remove(staged)
        except OSError: pass
        raise
    db.close()
    for suffix in ("-wal", "-shm"):
        try: os.remove(db.DB_PATH + suffix)
        except OSError: pass
    # Keep the previous library as obscura.db.prev (manual rollback point).
    if os.path.exists(db.DB_PATH):
        shutil.copy2(db.DB_PATH, db.DB_PATH + ".prev")
    os.replace(staged, db.DB_PATH)
    for name in zf.namelist():
        if name == NAME_DB: continue
        if name in (NAME_IMG, NAME_SCAN, NAME_SET) or \
           name.startswith("encrypted/") or name.startswith("scrapers/"):
            dest = os.path.join(db.DATA_DIR, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(name) as src, open(dest, "wb") as out:
                out.write(src.read())
    db.connect()
    if NAME_SET in zf.namelist():
        try:
            s = json.loads(zf.read(NAME_SET).decode("utf-8"))
            if isinstance(s, dict): db.save_settings(s)
        except Exception: pass
    return len(zf.namelist())
