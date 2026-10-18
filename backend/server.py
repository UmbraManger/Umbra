"""Umbra API — all routes under /api. Frontend is served at /."""
import os, sys, json, re, time, secrets, hmac, logging
from typing import List, Optional
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Body, Request
from fastapi.responses import Response, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import requests
import cloudscraper

import db, crypto, keystore, backup as backup_engine
from crypto import set_locked, is_locked   # app-lock state (P3)
from net_guard import safe_image_url, safe_get

# cloudscraper session for downloading images from Cloudflare-protected sites
_cf_scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
import scrapers as scraper_engine
import scanner
import media as media_engine

db.connect()
# (schema incl. positions + column migrations lives in db._migrate)
log = logging.getLogger("umbra")

app = FastAPI(title="Umbra", version="1.1")

# ---- security: per-run token + Host/Origin enforcement ----
# Everything under /api/ requires the per-run token (header X-Umbra-Token or
# ?t=). The only exception is a plain GET of /api/images/* and /api/media/*
# (img/video tags cannot set headers) — those additionally require a
# same-origin/no Sec-Fetch-Site. Host must be loopback and Origin, when sent,
# must match it: together these block DNS rebinding and drive-by calls made by
# other web pages open in the browser. CORS is deliberately NOT enabled — the
# frontend is same-origin.
API_TOKEN = secrets.token_hex(32)
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_ASSET_PREFIXES = ("/api/images/", "/api/media/")
_TOKEN_HDR = "x-umbra-token"


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        # The app lock is enforced server-side: when the vault is locked, every
        # data endpoint answers 423 Locked except the allowlist below (the
        # unlock affordance, status and set/unset endpoints must keep working
        # so the dialog can open and the frontend can never force-open itself).
        if is_locked():
            if path in ("/api/ping", "/api/images/unlock", "/api/images/status",
                        "/api/lock", "/api/unlock"):
                return await call_next(request)
            return JSONResponse({"detail": "locked — unlock with the passphrase in Settings"},
                                status_code=423)
        host_hdr = (request.headers.get("host") or "").lower()
        if host_hdr.split(":")[0].strip("[]") not in _LOCAL_HOSTS:
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc.lower() != host_hdr:
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        sent = request.headers.get(_TOKEN_HDR) or request.query_params.get("t") or ""
        if sent and hmac.compare_digest(str(sent), API_TOKEN):
            return await call_next(request)
        if request.method == "GET" and path.startswith(_ASSET_PREFIXES):
            if request.headers.get("sec-fetch-site", "") in ("", "same-origin", "none"):
                return await call_next(request)
        return JSONResponse({"detail": "missing or invalid token"}, status_code=403)


app.add_middleware(SecurityMiddleware)

TABLES = {"movies": "movies", "scenes": "scenes", "performers": "performers",
          "studios": "studios", "categories": "categories"}

MAPS = {
 "movies": {"id":"id","title":"title","year":"year","studioId":"studio_id",
            "durationMin":"duration_min","scenes":"scenes","director":"director",
            "desc":"desc","posterF":"poster_f","posterB":"poster_b","fav":"fav",
            "filePath":"file_path","actorIds":"actor_ids","categoryIds":"category_ids"},
 "scenes": {"id":"id","title":"title","date":"date","studioId":"studio_id",
            "siteId":"studio_id",
            "movieId":"movie_id","durationMin":"duration_min","director":"director",
            "desc":"desc","coverA":"cover_a","coverB":"cover_b","thumb":"thumb",
            "fav":"fav","filePath":"file_path","actorIds":"actor_ids","categoryIds":"category_ids",
            "gallery":"gallery"},
 "performers": {"id":"id","name":"name","gender":"gender","aliases":"aliases",
            "birth":"birth","ethnicity":"ethnicity","nationality":"nationality","height":"height","weight":"weight",
            "hair":"hair","eyes":"eyes","measurements":"measurements","boobs":"boobs",
            "piercings":"piercings","tattoos":"tattoos","careerStart":"career_start","photo":"photo",
            "twitter":"twitter","instagram":"instagram","onlyfans":"onlyfans","urls":"urls"},
 "studios": {"id":"id","name":"name","url":"url","country":"country","desc":"desc",
            "logo":"logo","twitter":"twitter","instagram":"instagram",
            "parentId":"parent_id"},
 "categories": {"id":"id","name":"name","icon":"icon","desc":"desc"},
}
JSON_COLS = {"actor_ids", "category_ids", "urls", "gallery"}
ORDER = {"movies": "year DESC, title COLLATE NOCASE",
         "scenes": "date DESC, title COLLATE NOCASE",
         "performers": "name COLLATE NOCASE",
         "studios": "name COLLATE NOCASE",
         "categories": "name COLLATE NOCASE"}

def _from_db(kind, row):
    inv = {c: k for k, c in MAPS[kind].items()}
    out = {}
    for col, v in row.items():
        k = inv.get(col, col)
        if col in JSON_COLS:
            try: v = json.loads(v) if v else []
            except Exception: v = []
        out[k] = v
    if kind == "scenes":
        covers = [out.pop("coverA", None) or out.pop("cover_a", None),
                  out.pop("coverB", None) or out.pop("cover_b", None)]
        covers = [c for c in covers if c]
        if len(covers) == 2 and covers[0] == covers[1]:
            covers = [covers[0]]
        out["covers"] = covers if covers else []
        out.pop("coverA", None); out.pop("cover_a", None)
        out.pop("coverB", None); out.pop("cover_b", None)
    return out

def _to_db(kind, data, create=False):
    m = MAPS[kind]
    # Also build reverse map: snake_case column -> column (for scraper compatibility)
    valid_cols = set(m.values())
    rec = {}
    if create:
        rec["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    for k, v in data.items():
        # Try camelCase key first, then snake_case key directly
        col = m.get(k)
        if not col:
            # Scraper returned snake_case key (e.g. poster_f) — pass through if valid column
            if k in valid_cols and k != "id":
                col = k
        if not col or col == "id": continue
        if col in JSON_COLS: v = json.dumps(v if isinstance(v, list) else [])
        if col == "fav": v = 1 if v else 0
        rec[col] = v
    if kind == "scenes" and "covers" in data:
        covers = data["covers"] if isinstance(data["covers"], list) else []
        rec["cover_a"] = covers[0] if len(covers) > 0 else ""
        rec["cover_b"] = covers[1] if len(covers) > 1 else ""
        rec.pop("covers", None)
    return rec

@app.get("/api/ping")
def ping(): return {"ok": True, "app": "Umbra", "version": "1.1"}

@app.get("/api/library")
def library():
    lib = {}
    for kind, table in TABLES.items():
        rows = db.query(f"SELECT * FROM {table} ORDER BY {ORDER[kind]}")
        lib[kind] = [_from_db(kind, r) for r in rows]
    lib["settings"] = _public_settings()
    return lib

IMG_URL_RE = re.compile(r"/api/images/(i[0-9a-f]{8})")
# Columns whose value is an image reference (poster/logo/photo) plus the JSON
# gallery list. Anything an update replaces with a new reference means the old
# blob would never be reaped otherwise.
_IMG_COLS = {"movies": ["poster_f", "poster_b"],
             "scenes": ["cover_a", "cover_b", "thumb", "gallery"],
             "performers": ["photo"],
             "studios": ["logo"]}

def _img_refs(img_id: str) -> int:
    """How many current library references point at /api/images/<img_id>."""
    like = f"%{img_id}%"
    return sum(db.one(f"SELECT COUNT(*) AS n FROM {t} WHERE {c} LIKE ?", (like,))["n"]
               for t, cols in _IMG_COLS.items() for c in cols)


def _prune_record_images(kind: str, old_row: dict, keep=frozenset()) -> None:
    """Post-DELETE/UPDATE sweep: delete blobs the library no longer references.
    Called after the row change so reference counts reflect the new state; ids
    in `keep` are still present in the updated row."""
    for col in _IMG_COLS.get(kind, []):
        for old_id in set(IMG_URL_RE.findall(str(old_row.get(col) or ""))):
            if old_id not in keep and _img_refs(old_id) == 0:
                crypto.remove_image(old_id)


def _prune_replaced_images(kind: str, old_row: dict, rec: dict) -> None:
    keep = set()
    for col in _IMG_COLS.get(kind, []):
        if col in rec:
            keep |= set(IMG_URL_RE.findall(rec[col] if isinstance(rec[col], str) else ""))
    _prune_record_images(kind, old_row, keep)


def _save_one(kind: str, data: dict, create: bool) -> str:
    table = TABLES[kind]
    rec = _to_db(kind, data, create=create)
    if create:
        rid = data.get("id") or db.new_id(kind[:2])
        rec["id"] = rid
        names = ",".join(rec); qs = ",".join("?" * len(rec))
        db.execute(f"INSERT INTO {table} ({names}) VALUES ({qs})", list(rec.values()))
        return rid
    rid = data.get("id")
    if not rid or not db.one(f"SELECT id FROM {table} WHERE id=?", (rid,)):
        raise HTTPException(404, "not found")
    if "file_path" in rec:
        # The frontend sends whole items on update, so filePath must be IGNORED
        # rather than rejected — but it may only ever be repointed to a file
        # inside the configured scan folders. With no folders configured every
        # repoint is dropped (bug #1): otherwise PUT + GET /api/media would
        # stream arbitrary files.
        new = rec["file_path"]
        if new:
            stored = db.one(f"SELECT file_path FROM {table} WHERE id=?", (rid,)) or {}
            if (stored.get("file_path") or "") != new:
                roots = media_engine.scan_roots()
                if not roots or not media_engine.inside_roots(new, roots):
                    rec.pop("file_path")
    if not rec:
        return rid            # everything in the body was ignored — nothing to update
    sets = ",".join(f"{c}=?" for c in rec)
    old_row = db.one(f"SELECT * FROM {table} WHERE id=?", (rid,)) or {}
    db.execute(f"UPDATE {table} SET {sets} WHERE id=?", list(rec.values()) + [rid])
    _prune_replaced_images(kind, old_row, rec)
    return rid

def _register_crud(kind):
    def create(body: dict = Body(...)):
        return {"id": _save_one(kind, body, True)}
    def update(body: dict = Body(...)):
        return {"id": _save_one(kind, body, False)}
    def delete(rid: str, file: int = 0, confirm: str = ""):
        path = None
        if kind in ("movies", "scenes"):
            row = db.one(f"SELECT file_path FROM {TABLES[kind]} WHERE id=?", (rid,))
            if row: path = row["file_path"]
        # Validate the destructive part BEFORE touching any row.
        if file and path:
            if confirm != "DELETE":
                raise HTTPException(400, 'refusing to delete the video file without confirm="DELETE"')
            real = os.path.realpath(path)
            roots = media_engine.scan_roots()
            if not roots:
                # Fail CLOSED: with no scan folders configured we cannot prove the
                # file belongs to the library, so never delete it (bug #7).
                raise HTTPException(403, "no scan folders configured — refusing to delete the file from disk")
            if not media_engine.inside_roots(real, roots):
                raise HTTPException(403, "file is outside the configured scan folders — refusing to delete it")
        old_row = db.one(f"SELECT * FROM {TABLES[kind]} WHERE id=?", (rid,))
        if kind == "movies":
            db.execute("UPDATE scenes SET movie_id=NULL WHERE movie_id=?", (rid,))
        db.execute("DELETE FROM positions WHERE media_id=?", (kind[:-1] + ":" + rid,))
        db.execute(f"DELETE FROM {TABLES[kind]} WHERE id=?", (rid,))
        if old_row and kind in _IMG_COLS:
            _prune_record_images(kind, old_row)
        file_removed = False
        if file and path and os.path.isfile(path):
            try:
                os.remove(path); file_removed = True
            except OSError: pass
        return {"ok": True, "file_removed": file_removed}
    def delete_all(body: dict = Body(default={})):
        if (body or {}).get("confirm") != "DELETE":
            raise HTTPException(400, 'confirmation required: send {"confirm":"DELETE"}')
        # Mirror the single-row delete: drop this kind's image blobs and
        # watch positions, orphan the movie links scenes point at, then clear
        # the table. Cross-kind references are left stale on purpose (the UI
        # confirm says so).
        old_rows = db.query(f"SELECT * FROM {TABLES[kind]}") if kind in _IMG_COLS else []
        if kind == "movies":
            db.execute("UPDATE scenes SET movie_id=NULL WHERE movie_id IS NOT NULL")
        db.execute("DELETE FROM positions WHERE media_id LIKE ?", (kind[:-1] + ":%",))
        db.execute(f"DELETE FROM {TABLES[kind]}")
        for row in old_rows:
            _prune_record_images(kind, row)
        return {"ok": True}
    app.post(f"/api/{kind}")(create)
    app.put(f"/api/{kind}")(update)
    app.delete(f"/api/{kind}/{{rid}}")(delete)
    app.post(f"/api/{kind}/deleteAll")(delete_all)

for _kind in TABLES:
    _register_crud(_kind)

# ---- settings ----
def _public_settings() -> dict:
    """Settings as the client may see them: the app-lock hash/salt/kdf never
    leave the server — the client must not hold or compare them."""
    s = db.get_settings()
    lock = s.get("lock")
    if isinstance(lock, dict) and (lock.get("hash") or lock.get("salt")):
        s = dict(s)
        s["lock"] = {k: v for k, v in lock.items()
                     if k not in ("hash", "salt", "kdf")}
    return s


@app.get("/api/settings")
def get_settings(): return _public_settings()

@app.put("/api/settings")
def put_settings(body: dict = Body(...)):
    body = dict(body or {})
    ai = body.get("ai")
    if isinstance(ai, dict):
        incoming_key = (ai.get("key") or "").strip()
        if incoming_key:
            if keystore.set_key(incoming_key):
                ai = dict(ai); ai["key"] = ""
                body["ai"] = ai
        else:
            s = db.get_settings()
            existing_key = ((s.get("ai") or {}).get("key") or "").strip()
            if existing_key:
                ai = dict(ai); ai["key"] = existing_key
                body["ai"] = ai
    # The app-lock record's secrets belong to the server: a client-shaped PUT
    # may flip `on` (the settings toggle disarms that way) but can never carry
    # or erase hash/salt/kdf/pass_set.
    stored_lock = (db.get_settings().get("lock") or {})
    if stored_lock.get("hash"):
        body["lock"] = {**(body.get("lock") or {}),
                        **{k: stored_lock[k]
                           for k in ("hash", "salt", "kdf", "pass_set")
                           if k in stored_lock}}
    db.save_settings(body)
    return {"ok": True}

# ---- AI key management ----
@app.get("/api/ai/key")
def ai_key_status():
    k = keystore.get_key() or ""
    s = db.get_settings()
    skey = (s.get("ai") or {}).get("key") or ""
    return {"keyring": keystore.available(), "stored": bool(k or skey)}

@app.post("/api/ai/key")
def ai_key_set(body: dict = Body(...)):
    k = (body.get("key") or "").strip()
    if keystore.set_key(k): return {"stored": "keyring"}
    s = db.get_settings(); s.setdefault("ai", {})["key"] = k; db.save_settings(s)
    return {"stored": "settings"}

# ---- image protection + image serving ----
class PassBody(BaseModel):
    passphrase: str
    current: Optional[str] = None

@app.get("/api/images/status")
def img_status(): return crypto.status()

@app.post("/api/images/passphrase")
def img_pass(b: PassBody):
    try: return crypto.set_passphrase(b.passphrase, b.current)
    except ValueError as e: raise HTTPException(400, str(e))

@app.post("/api/images/enabled")
def img_enabled(body: dict = Body(...)):
    try:
        return crypto.set_enabled(bool(body.get("on")))
    except crypto.Locked:
        raise HTTPException(423, "image protection is locked — unlock with the passphrase first")

@app.post("/api/images/unlock")
def img_unlock(b: PassBody):
    if not crypto.unlock(b.passphrase): raise HTTPException(400, "wrong passphrase")
    return {"unlocked": True}


# ---- app lock (server-side) ----

@app.post("/api/lock")
def lock_app(b: PassBody):
    """Arm the app lock and store its passphrase hash server-side (salt + slow
    KDF params + derived key — never a fast hash, never client-held). When a
    hash already exists the request must prove knowledge of it: `current`
    (password change) or a `passphrase` equal to the stored one (re-arm)."""
    if len(b.passphrase) < 4:
        raise HTTPException(400, "passphrase must be at least 4 characters")
    s = db.get_settings()
    m = s.get("lock") or {}
    if m.get("hash"):
        probe = b.current if b.current is not None else b.passphrase
        salt = bytes.fromhex(m.get("salt") or "")
        key = crypto._derive(probe, salt, m.get("kdf") or crypto._best_kdf())
        if key != bytes.fromhex(m["hash"]):
            raise HTTPException(400, "wrong passphrase")
    new_salt = os.urandom(16).hex()
    kdf = crypto._best_kdf()
    new_hash = crypto._derive(b.passphrase, bytes.fromhex(new_salt), kdf).hex()
    s["lock"] = {**m, "hash": new_hash, "salt": new_salt, "kdf": kdf,
                 "pass_set": True, "on": True}
    db.save_settings(s)          # read-modify-write: keep every other setting
    return {"armed": True}


@app.post("/api/lock/now")
def lock_now():
    """Lock this session immediately (no passphrase: the caller is already
    inside the unlocked app; this only raises the in-memory flag)."""
    if not (db.get_settings().get("lock") or {}).get("hash"):
        raise HTTPException(400, "set a password first")
    set_locked(True)
    return {"locked": True}


@app.post("/api/unlock")
def unlock_app(b: PassBody):
    """Unlock this session. The passphrase is verified against the stored
    derived hash - the client can no longer hold or compare the hash itself.
    The record stays armed for the next start (disarm via the settings PUT)."""
    m = db.get_settings().get("lock") or {}
    if not m.get("hash"):
        return JSONResponse({"locked": True}, status_code=200)
    salt = bytes.fromhex(m.get("salt") or "")
    key = crypto._derive(b.passphrase, salt, m.get("kdf") or crypto._best_kdf())
    if key != bytes.fromhex(m["hash"]):
        raise HTTPException(400, "wrong passphrase")
    set_locked(False)
    return {"unlocked": True}




@app.post("/api/images")
async def image_upload(file: UploadFile = File(...)):
    data = await file.read()
    try:
        img_id = crypto.store_image(data, file.content_type or "image/jpeg")
    except crypto.Locked as e:
        raise HTTPException(423, str(e) or "image protection is locked — unlock in Settings")
    return {"id": img_id, "url": f"/api/images/{img_id}"}

@app.post("/api/images/encrypt-all")
def img_encrypt_all():
    """Encrypt any blobs stored as plaintext (added while protection was off/locked)."""
    try:
        n = crypto.encrypt_plaintext()
    except crypto.Locked:
        raise HTTPException(423, "image protection is locked — unlock in Settings")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"encrypted": n}

@app.post("/api/images/prune")
def images_prune():
    """Delete stored blobs that no library record references (replaced covers,
    failed imports). Explicit user action from Clear Image Cache; scans blob
    files in data/encrypted and drops the ones with zero references."""
    n = 0
    if os.path.isdir(crypto.ENC_DIR):
        for fn in sorted(os.listdir(crypto.ENC_DIR)):
            m = re.fullmatch(r"(i[0-9a-f]{8})\.bin", fn)
            if not m or _img_refs(m.group(1)):
                continue
            crypto.remove_image(m.group(1))
            n += 1
    return {"pruned": n}

@app.get("/api/images/{img_id}")
def image_get(img_id: str):
    if not re.fullmatch(r"i[0-9a-f]{8}", img_id or ""):
        raise HTTPException(404, "not found")
    try:
        res = crypto.load_image(img_id)
    except crypto.Locked:
        raise HTTPException(423, "image protection is locked — unlock in Settings")
    if res is None: raise HTTPException(404, "not found")
    data, mime = res
    return Response(content=data, media_type=mime)

# ---- wikipedia lookup (fill descriptions) ----
@app.get("/api/wikipedia")
def wikipedia(q: str):
    hdr = {"User-Agent": "Umbra/1.0 (self-hosted media library)"}

    def api(params):
        return requests.get("https://en.wikipedia.org/w/api.php", params=params,
                            timeout=10, headers=hdr).json()

    try:
        hits = []
        try:
            r = requests.get("https://en.wikipedia.org/w/rest.php/v1/search/page",
                             params={"q": q, "limit": 5}, timeout=10, headers=hdr)
            if r.ok:
                hits = [p.get("title") for p in (r.json().get("pages") or []) if p.get("title")]
        except Exception:
            pass
        if not hits:
            s = api({"action": "query", "list": "search", "srsearch": q,
                     "srlimit": 5, "format": "json"})
            hits = [h.get("title") for h in (((s.get("query") or {}).get("search")) or [])
                    if h.get("title")]
        for title in hits[:4]:
            e = api({"action": "query", "prop": "extracts", "explaintext": 1,
                     "exintro": 1, "redirects": 1, "titles": title, "format": "json"})
            pages = ((e.get("query") or {}).get("pages")) or {}
            pg = next(iter(pages.values()), {}) or {}
            ext = (pg.get("extract") or "").strip()
            if ext and "may refer to" not in ext.split("\n")[0].lower():
                return {"title": title, "extract": ext,
                        "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")}
        return {"title": None, "extract": "", "url": ""}
    except Exception:
        raise HTTPException(502, "wikipedia lookup failed")

# ---- native dialogs ----
@app.post("/api/dialog/folder")
def dialog_folder():
    import tkinter as tk
    from tkinter import filedialog
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(parent=root, title="Select Folder")
        root.destroy()
        return {"path": path or ""}
    except Exception:
        return {"path": ""}

@app.post("/api/dialog/file")
def dialog_file():
    import tkinter as tk
    from tkinter import filedialog
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            parent=root,
            title="Select Video File",
            filetypes=[("Video Files", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.ts *.mpg *.mpeg *.3gp"), ("All Files", "*")])
        root.destroy()
        return {"path": path or ""}
    except Exception:
        return {"path": ""}

# ---- scanner ----
@app.post("/api/scan")
async def scan(body: dict = Body(...)):
    files = await run_in_threadpool(scanner.walk, body.get("dirs", []))
    return {"found": files, "count": len(files)}

# Progress for the candidates scan below: it ffprobes every file synchronously
# and can take a while, so the UI polls this to show a count instead of looking
# hung. ponytail: one shared slot (a second scan would overwrite the first) —
# this is a single-user desktop app, a job queue would be far more machinery.
_SCAN = {"active": False, "done": 0, "total": 0}

@app.get("/api/scan/progress")
def scan_progress() -> dict:
    return dict(_SCAN)

def _scan_candidates(dirs: list) -> list:
    files = scanner.walk(dirs)
    _SCAN.update(active=True, done=0, total=len(files))
    try:
        for i, f in enumerate(files, 1):
            f["imported"] = scanner.is_imported(f["path"])
            f["guess_title"] = scanner.guess_title(f["path"])
            dur = scanner.probe_duration(f["path"])
            f["duration_min"] = dur
            f["guess_kind"] = scanner.guess_kind(f["path"], duration_min=dur)
            f["posters"] = [os.path.basename(p) for p in scanner.find_posters(f["path"])]
            _SCAN["done"] = i
    finally:
        _SCAN["active"] = False
    files.sort(key=lambda x: (x["imported"], x["dir"], x["name"]))
    return files

# Heavy scan work stays off the event loop (same pattern as backup/restore):
# ffprobe per candidate and poster imports would otherwise stall every other
# request — including /api/scan/progress the UI is polling — for the whole run.
@app.post("/api/scan/candidates")
async def scan_candidates(body: dict = Body(...)):
    files = await run_in_threadpool(_scan_candidates, body.get("dirs", []))
    return {"candidates": files, "count": len(files)}

class ImportBody(BaseModel):
    path: str
    kind: str
    title: str
    year: Optional[int] = None
    date: Optional[str] = None
    studio_id: Optional[str] = None
    movie_id: Optional[str] = None
    duration_min: int = 0
    director: str = ""
    desc: str = ""
    actor_ids: list = []
    category_ids: list = []
    fav: bool = False

@app.post("/api/scan/import")
async def scan_import(b: ImportBody):
    try:
        rec = await run_in_threadpool(
            scanner.import_file, b.path, b.kind, b.title, year=b.year, date=b.date,
            studio_id=b.studio_id, movie_id=b.movie_id,
            duration_min=b.duration_min, director=b.director, desc=b.desc,
            actor_ids=b.actor_ids, category_ids=b.category_ids, fav=b.fav)
        return {"record": rec}
    except Exception as e:
        raise HTTPException(500, f"import failed: {e}")

@app.post("/api/scan/markdone")
def scan_markdone(body: dict = Body(...)):
    scanner.mark_done(body.get("path", "")); return {"ok": True}

@app.post("/api/scan/undone")
def scan_undone(body: dict = Body(...)):
    scanner.remove_done(body.get("path", "")); return {"ok": True}

# ---- external scrapers ----
@app.get("/api/scrapers")
def scrapers_list(): return scraper_engine.list_all()

@app.post("/api/scrapers/file")
async def scraper_upload(file: UploadFile = File(...),
                         # multi-classification comes as repeated ?kind= params —
                         # Form fields next to UploadFile break multipart parsing
                         # on this fastapi/starlette combo (even a single one)
                         confirm: str = Query(""),
                         kinds: List[str] = Query(None, alias="kind")):
    content = await file.read()
    if (file.filename or "").lower().endswith(".py") and \
            confirm != "I UNDERSTAND PYTHON SCRAPERS RUN AS LOCAL CODE":
        raise HTTPException(400, "Python scrapers execute as local code — send "
                                'confirm="I UNDERSTAND PYTHON SCRAPERS RUN AS LOCAL CODE"')
    try:
        sid, asg = scraper_engine.add(file.filename, content, kinds or ["movie"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": sid, "kinds": asg}

@app.post("/api/scrapers/{sid}/toggle")
def scraper_toggle(sid: str):
    scraper_engine.toggle(sid); return {"ok": True}

@app.delete("/api/scrapers/{sid}")
def scraper_delete(sid: str):
    scraper_engine.remove(sid); return {"ok": True}

@app.get("/api/scrapers/sites")
def list_scraper_sites():
    return db.get_scraper_sites()

@app.post("/api/scrapers/sites")
def add_scraper_site(body: dict = Body(...)):
    kind = body.get("kind")
    scraper_id = body.get("scraper_id")
    domain = body.get("domain", "").strip().lower()
    if not kind or not scraper_id or not domain:
        raise HTTPException(400, "kind, scraper_id, domain required")
    db.add_scraper_site(kind, scraper_id, domain)
    return {"ok": True}

@app.delete("/api/scrapers/sites/{kind}/{idx}")
def del_scraper_site(kind: str, idx: int):
    db.del_scraper_site(kind, idx)
    return {"ok": True}

MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _store_response_image(r) -> str:
    """Validate a fetched response and store it; raises on non-image/oversized."""
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ctype and not ctype.startswith("image/"):
        raise ValueError(f"refusing to store non-image content-type {ctype!r}")
    if len(r.content) > MAX_IMAGE_BYTES:
        raise ValueError("image exceeds the 15 MB cap")
    mime = ctype or "image/jpeg"
    img_id = crypto.store_image(r.content, mime)
    return f"/api/images/{img_id}"


def _download_image(url: str) -> str:
    """Download image from URL, store locally, return /api/images/ path."""
    if not url or not url.startswith("http"):
        return url
    if not safe_image_url(url):
        log.warning("[download-image] blocked unsafe image URL: %s", url[:80])
        return url
    try:
        # Vixen/Gamma CDN needs a Referer header
        extra = {}
        if 'cdn.' in url or 'images' in url:
            extra['headers'] = {'Referer': 'https://www.vixen.com/'}
        # For IAFD/LetsDoeIt URLs, use their scraper's warmed-up session
        # (bypasses Cloudflare) — only when that optional module is installed.
        if 'iafd.com' in url:
            try:
                import iafd_scraper
            except ImportError:
                iafd_scraper = None
            if iafd_scraper is not None:
                try:
                    # iafd_session shares the redirect exposure — same guard.
                    r = safe_get(iafd_scraper.iafd_session, url, timeout=15)
                    return _store_response_image(r)
                except Exception as e:
                    log.warning("[download-image] iafd session failed: %s — %s", url[:80], e)
                    return url
        # Use cloudscraper for other Cloudflare-protected sites,
        # fall back to plain requests for others.
        try:
            r = safe_get(_cf_scraper, url, timeout=15, **extra)
        except Exception:
            r = safe_get(requests, url, timeout=15, headers={"User-Agent": "Mozilla/5.0", **extra.get('headers', {})})
        return _store_response_image(r)
    except Exception as e:
        log.warning("[download-image] failed: %s — %s", url[:80], e)
        return url


def _process_images(result: dict) -> dict:
    """Download remote image URLs in scraper result and replace with local paths.

    Many scrapers set several keys (thumbnail/cardThumbnail/image/cover_a/cover_b/
    etc.) to the exact same remote URL. Without caching, each key triggered its own
    independent download+store, meaning a single thumbnail could get fetched and
    saved as up to 5 separate local files. This downloads each distinct URL only
    once per call and reuses the same local path for every key that shared it.
    """
    if not isinstance(result, dict):
        return result

    downloaded = {}  # remote URL -> local path, cached for the life of this call

    def dl(url):
        if not url or not isinstance(url, str) or not url.startswith("http"):
            return url
        if url not in downloaded:
            downloaded[url] = _download_image(url)
        return downloaded[url]

    # Scene/movie image fields — check both camelCase (frontend) and snake_case (scrapers)
    for key in ("thumbnail", "cardThumbnail", "posterUrl",
                "posterF", "posterB", "poster_f", "poster_b",
                "image", "coverA", "coverB", "cover_a", "cover_b"):
        if result.get(key):
            result[key] = dl(result[key])
    # covers array
    if isinstance(result.get("covers"), list):
        result["covers"] = [dl(c) for c in result["covers"]]
        c = result["covers"]
        if len(c) == 2 and c[0] == c[1]:
            result["covers"] = [c[0]]
    # Performer photo
    if result.get("photo"):
        result["photo"] = dl(result["photo"])
    # Gallery images array
    if isinstance(result.get("gallery"), list):
        result["gallery"] = [dl(u) for u in result["gallery"] if isinstance(u, str)]
    return result


@app.post("/api/scrape")
def run_scrape(body: dict = Body(...)):
    import logging
    kind = body.get("kind", "movie")
    title = body.get("title", "")
    url = body.get("url", "")
    mode = body.get("mode", "scraper")
    # metadata only — never log the full request body
    logging.info("[scrape] kind=%s mode=%s sid=%s has_url=%s", kind, mode,
                 body.get("scraper_id"), bool(url))
    try:
        if mode == "ai":      result = ai_lookup(kind, title, body.get("extra", ""))
        elif mode == "scraper":
            sid = body.get("scraper_id")
            # Prefer domain from request body, fall back to site assignment
            domain = body.get("domain", "")
            if not domain:
                sites = db.get_scraper_sites()
                for kind_sites in sites.values():
                    for entry in kind_sites:
                        if entry.get("scraper_id") == sid:
                            domain = entry.get("domain", "")
                            break
            gallery_count = body.get("gallery_count", 0)
            try:
                result = scraper_engine.run_by_id(sid, title=title, url=url, kind=kind, domain=domain, gallery_count=gallery_count)
            except TypeError:
                result = scraper_engine.run_by_id(sid, title=title, url=url, kind=kind, domain=domain)
        elif mode == "site":    result = scraper_engine.run_for_site(body.get("source"), title=title, url=url, kind=kind)
        else: raise HTTPException(400, "unknown mode")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"lookup failed: {e}")
    return _process_images(result)

# ---- AI (OpenAI-compatible endpoint, key stays server-side / in keyring) ----
AI_FIELDS = {
 "movie": "title, year, studio, duration_min, scenes, director, categories (array), description",
 "scene": "title, date (YYYY-MM-DD), studio, duration_min, director, categories (array), description",
 "performer": "name, gender ('f'/'m'), birth (YYYY-MM-DD), ethnicity, height (cm), weight (kg), hair, eyes, measurements, boobs ('Natural'/'Enhanced'), piercings, tattoos, career_start",
}

def ai_lookup(kind: str, title: str, extra: str = "") -> dict:
    s = db.get_settings(); ai = s.get("ai") or {}
    if not ai.get("on"): raise HTTPException(400, "AI is disabled in Settings")
    ep = (ai.get("endpoint") or "https://api.openai.com/v1").rstrip("/")
    model = ai.get("model") or "gpt-4o-mini"
    key = (keystore.get_key() or "") if keystore.available() else ""
    if not key: key = ai.get("key") or ""
    prompt = (f"You are a metadata assistant for a private media manager. "
              f"Find information about the {kind} \"{title}\". "
              f"Return ONLY a JSON object with these fields (null for unknown): {AI_FIELDS[kind]}. "
              + (f"Additional instructions: {extra}" if extra else ""))
    headers = {"Content-Type": "application/json"}
    if key: headers["Authorization"] = f"Bearer {key}"
    r = requests.post(f"{ep}/chat/completions", headers=headers, timeout=90, json={
        "model": model,
        "messages": [{"role": "system", "content": "You output only valid JSON. No markdown."},
                     {"role": "user", "content": prompt}],
        "temperature": 0.2})
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    if not m: raise HTTPException(502, "AI did not return JSON")
    try: return json.loads(m.group())
    except Exception as e: raise HTTPException(502, f"bad JSON from AI: {e}")

# ---- real media playback ----
@app.get("/api/media/{kind}/{rid}")
def media_stream(kind: str, rid: str, request: Request):
    path = media_engine.get_path(kind, rid)
    if not path: raise HTTPException(404, "no video file linked to this record")
    size = os.path.getsize(path)
    mime = media_engine.mime_for(path)
    try:
        rng = media_engine.parse_range(request.headers.get("range"), size)
    except media_engine.RangeNotSatisfiable:
        return Response(status_code=416,
                        headers={"Content-Range": f"bytes */{size}",
                                 "Accept-Ranges": "bytes"})
    if rng:
        start, end = rng
        headers = {"Content-Range": f"bytes {start}-{end}/{size}",
                   "Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)}
        return StreamingResponse(media_engine.iter_file(path, start, end - start + 1),
                                 status_code=206, media_type=mime, headers=headers)
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(size)}
    return StreamingResponse(media_engine.iter_file(path, 0), media_type=mime, headers=headers)

@app.get("/api/media/{kind}/{rid}/info")
def media_info_ep(kind: str, rid: str):
    path = media_engine.get_path(kind, rid)
    if not path: raise HTTPException(404, "no file")
    info = media_engine.probe(path)
    subs = media_engine.sidecar_subs(path)
    for i, s in enumerate(subs):
        s["url"] = f"/api/media/{kind}/{rid}/subs/{i}"
    info["subs"] = subs
    info["path"] = path
    return info

@app.get("/api/media/{kind}/{rid}/subs/{idx}")
def media_sub(kind: str, rid: str, idx: int):
    path = media_engine.get_path(kind, rid)
    if not path: raise HTTPException(404)
    subs = media_engine.sidecar_subs(path)
    if idx < 0 or idx >= len(subs): raise HTTPException(404, "subtitle not found")
    return Response(content=media_engine.srt_to_vtt(subs[idx]["file"]), media_type="text/vtt")

@app.post("/api/media/{kind}/{rid}/open")
def media_open(kind: str, rid: str):
    path = media_engine.get_path(kind, rid)
    # same detail as the stream route: a bare 404 leaves the player with no
    # idea whether the file is missing, moved, or outside the scan folders.
    if not path: raise HTTPException(404, "no video file linked to this record")
    if not media_engine.open_with_os(path): raise HTTPException(500, "could not open with OS player")
    return {"ok": True}

@app.post("/api/media/{kind}/{rid}/reveal")
def media_reveal(kind: str, rid: str):
    path = media_engine.get_path(kind, rid)
    if not path: raise HTTPException(404)
    if not media_engine.reveal_in_os(path): raise HTTPException(500, "could not open file explorer")
    return {"ok": True, "path": path}

# ---- watch positions ----
@app.get("/api/positions")
def positions_all():
    rows = db.query("SELECT media_id, position FROM positions WHERE position > 0")
    return {r["media_id"]: r["position"] for r in rows}

@app.put("/api/media/{kind}/{rid}/position")
def position_put(kind: str, rid: str, body: dict = Body(...)):
    try: pos = float(body.get("position", 0))
    except Exception: pos = 0.0
    if pos < 0: pos = 0.0
    db.execute("INSERT INTO positions(media_id,position,updated_at) VALUES(?,?,?) "
               "ON CONFLICT(media_id) DO UPDATE SET position=excluded.position, updated_at=excluded.updated_at",
               (f"{kind}:{rid}", pos, time.strftime("%Y-%m-%d %H:%M:%S")))
    return {"ok": True}

@app.delete("/api/media/{kind}/{rid}/position")
def position_del(kind: str, rid: str):
    db.execute("DELETE FROM positions WHERE media_id=?", (f"{kind}:{rid}",))
    return {"ok": True}

@app.delete("/api/positions")
def positions_clear():
    db.execute("DELETE FROM positions")
    return {"ok": True}

# ---- maintenance ----
@app.post("/api/tools/duplicates")
def duplicates():
    sections = []
    for kind, label in (("movies","Movies"),("scenes","Scenes"),
                        ("performers","Performers"),("studios","Studios"),("categories","Categories")):
        col = "name" if kind in ("performers","studios","categories") else "title"
        seen = {}
        for r in db.query(f"SELECT id, {col} FROM {TABLES[kind]}"):
            k = (r[col] or "").strip().lower()
            if k: seen.setdefault(k, []).append(r["id"])
        dups = [v for v in seen.values() if len(v) > 1]
        if dups: sections.append({"kind": kind, "label": label, "groups": dups})
    return {"sections": sections}

@app.post("/api/tools/titlecase")
def titlecase_all():
    def _cap(w: re.Match) -> str:
        s = w.group()
        if len(s) > 1 and s.isupper():
            return s  # keep acronyms (BBC, XXX, …) intact
        return s[0].upper() + s[1:].lower()
    n = 0
    for table in ("movies", "scenes"):
        for r in db.query(f"SELECT id, title FROM {table}"):
            t2 = re.sub(r"\w[\w'’\-]*", _cap, r["title"])
            if t2 != r["title"]:
                db.execute(f"UPDATE {table} SET title=? WHERE id=?", (t2, r["id"])); n += 1
    return {"changed": n}

# ---- wipe ----
@app.post("/api/wipe")
def wipe_all(body: dict = Body(default={})):
    if (body or {}).get("confirm") != "DELETE MY LIBRARY":
        raise HTTPException(400, 'confirmation required: send {"confirm":"DELETE MY LIBRARY"}')
    import shutil
    # Clear all tables
    for table in TABLES:
        db.execute(f"DELETE FROM {table}")
    db.execute("DELETE FROM positions")
    db.execute("DELETE FROM settings")
    # Remove encrypted images and scrapers
    enc_dir = os.path.join(db.DATA_DIR, "encrypted")
    scraper_dir = db.SCRAPER_DIR
    for d in (enc_dir, scraper_dir):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d, exist_ok=True)
    # Remove scan state and imgprot
    for f in ("scanstate.json", "imgprot.json"):
        p = os.path.join(db.DATA_DIR, f)
        try: os.remove(p)
        except OSError: pass
    # Wipe must leave no residue: drop the old-library backup (db.prev),
    # the posters cache and any WAL/journal files, then compact the database
    # so freed pages disappear.
    try: os.remove(os.path.join(db.DATA_DIR, "obscura.db.prev"))
    except OSError: pass
    try: shutil.rmtree(os.path.join(db.DATA_DIR, "posters"), ignore_errors=True)
    except OSError: pass
    for f in ("obscura.db-wal", "obscura.db-shm", "obscura.db-journal"):
        p = os.path.join(db.DATA_DIR, f)
        try: os.remove(p)
        except OSError: pass
    try: db.execute("VACUUM")
    except Exception: pass
    return {"ok": True}

# ---- backup / restore ----
@app.get("/api/backup/export")
def backup_export():
    # Intentionally sync / threadpooled: the export is an O(n) file-archive
    # walk over the library. Offloading to a thread would only add a thread
    # hop with no benefit — never change this back to a blocking async def.
    data = backup_engine.export_zip()
    stamp = time.strftime("%Y%m%d-%H%M")
    return Response(content=data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="Umbra-Backup-{stamp}.zip"'})

@app.post("/api/backup/restore")
async def backup_restore(request: Request, file: UploadFile = File(...),
                         # query, not Form: Form fields next to UploadFile break
                         # multipart parsing on this fastapi/starlette combo
                         confirm: str = Query("")):
    if confirm != "RESTORE":
        raise HTTPException(400, 'confirmation required: send query param confirm="RESTORE"')
    # 413 on oversized archives before we read a single byte.
    if int(request.headers.get("content-length") or 0) > 50 * 1024 * 1024:
        raise HTTPException(413, "restore archive limited to 50 MB")
    data = await file.read()
    try: n = await run_in_threadpool(backup_engine.restore_zip, data)
    except ValueError as e: raise HTTPException(400, str(e))
    except Exception as e: raise HTTPException(500, f"restore failed: {e}")
    return {"ok": True, "entries": n}

# ---- serve the frontend (mount LAST so /api routes win) ----
def frontend_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", ""), "frontend")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

FRONTEND = frontend_dir()
if os.path.isdir(FRONTEND):
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")

    @app.middleware("http")
    async def _no_store_frontend(request, call_next):
        # StaticFiles sends no Cache-Control, so WebView2 applies heuristic
        # caching and keeps serving a stale js/*.js across sessions — the UI
        # then looks "not applied" even though the bundle on disk is new.
        # index.html escapes this via its ?t= cache-buster; force every asset
        # to revalidate so a fresh launch always loads the current frontend.
        resp = await call_next(request)
        if not request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
        return resp
