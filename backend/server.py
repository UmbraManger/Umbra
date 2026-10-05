"""Obscura API — all routes under /api. Frontend is served at /."""
import os, sys, json, re, time, secrets, hmac, logging, threading
from typing import Optional
from urllib.parse import urlparse, urljoin
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body, Request
from fastapi.responses import Response, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import requests
import cloudscraper

import db, crypto, keystore, backup as backup_engine

# cloudscraper session for downloading images from Cloudflare-protected sites
_cf_scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
import scrapers as scraper_engine
import scanner
import media as media_engine

db.connect()
# (schema incl. positions + column migrations lives in db._migrate)
log = logging.getLogger("obscura")

app = FastAPI(title="Obscura", version="0.9")

# ---- security: per-run token + Host/Origin enforcement ----
# Everything under /api/ requires the per-run token (header X-Obscura-Token or
# ?t=). The only exception is a plain GET of /api/images/* and /api/media/*
# (img/video tags cannot set headers): those are authorized with a short-lived
# signed cookie handed out when the real token is presented — client-controlled
# headers (Sec-Fetch-Site) are NOT trusted. Host must be loopback and Origin,
# when sent, must match it: together these block DNS rebinding and drive-by
# calls made by other web pages open in the browser. CORS is deliberately NOT
# enabled — the frontend is same-origin.
API_TOKEN = secrets.token_hex(32)
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_ASSET_PREFIXES = ("/api/images/", "/api/media/")
_TOKEN_HDR = "x-obscura-token"
_ASSET_COOKIE = "obscura_asset"
_ASSET_COOKIE_TTL = 8 * 3600  # seconds — short-lived, refreshed on every token-authed call


def _asset_cookie_val() -> str:
    """Signed, expiring cookie value for tag-driven asset GETs."""
    exp = int(time.time()) + _ASSET_COOKIE_TTL
    sig = hmac.new(API_TOKEN.encode(), f"asset:{exp}".encode(), "sha256").hexdigest()
    return f"{exp}.{sig}"


def _asset_cookie_ok(val) -> bool:
    try:
        exp_s, sig = str(val or "").split(".", 1)
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < time.time():
        return False
    return hmac.compare_digest(
        sig, hmac.new(API_TOKEN.encode(), f"asset:{exp}".encode(), "sha256").hexdigest())


def _grant_asset_cookie(resp):
    """Token was presented: hand out the cookie that <img>/<video>/… GETs use
    instead of trusting client-controlled headers (Sec-Fetch-Site)."""
    resp.set_cookie(_ASSET_COOKIE, _asset_cookie_val(), max_age=_ASSET_COOKIE_TTL,
                    path="/", httponly=True, samesite="lax")
    return resp


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            resp = await call_next(request)
            t = request.query_params.get("t") or ""
            if t and hmac.compare_digest(str(t), API_TOKEN):
                # App shell loaded with ?t= → grant the asset cookie up front so
                # the very first <img>/<video> loads are already authorized.
                _grant_asset_cookie(resp)
            return resp
        host_hdr = (request.headers.get("host") or "").lower()
        if host_hdr.split(":")[0].strip("[]") not in _LOCAL_HOSTS:
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc.lower() != host_hdr:
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        sent = request.headers.get(_TOKEN_HDR) or request.query_params.get("t") or ""
        if sent and hmac.compare_digest(str(sent), API_TOKEN):
            return _grant_asset_cookie(await call_next(request))
        if request.method == "GET" and path.startswith(_ASSET_PREFIXES) \
                and _asset_cookie_ok(request.cookies.get(_ASSET_COOKIE)):
            # tag-driven GET (img/video/track): authorized by the signed cookie
            # handed out at token time — token auth stays the enforced default
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
def ping(): return {"ok": True, "app": "Obscura", "version": "0.9"}

@app.get("/api/library")
def library():
    lib = {}
    for kind, table in TABLES.items():
        rows = db.query(f"SELECT * FROM {table} ORDER BY {ORDER[kind]}")
        lib[kind] = [_from_db(kind, r) for r in rows]
    lib["settings"] = db.get_settings()
    return lib

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
    sets = ",".join(f"{c}=?" for c in rec)
    db.execute(f"UPDATE {table} SET {sets} WHERE id=?", list(rec.values()) + [rid])
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
        real = None
        if file and path:
            if confirm != "DELETE":
                raise HTTPException(400, 'refusing to delete the video file without confirm="DELETE"')
            try:
                # mandatory, fail-closed containment: also refuses when no scan
                # folders are configured at all (was: check silently skipped)
                real = media_engine.safe_path(path)
            except media_engine.PathNotAllowed as e:
                raise HTTPException(403, str(e))
        if kind in ("movies", "scenes"):
            img_cols = {"movies": ["poster_f", "poster_b"],
                        "scenes": ["cover_a", "cover_b"]}.get(kind, [])
            row2 = db.one(f"SELECT {','.join(img_cols)} FROM {TABLES[kind]} WHERE id=?", (rid,))
            if row2:
                for c in img_cols:
                    m = re.match(r"/api/images/(i[0-9a-f]{8})$", row2[c] or "")
                    if m: crypto.remove_image(m.group(1))
        if kind == "movies":
            db.execute("UPDATE scenes SET movie_id=NULL WHERE movie_id=?", (rid,))
        db.execute("DELETE FROM positions WHERE media_id=?", (kind[:-1] + ":" + rid,))
        db.execute(f"DELETE FROM {TABLES[kind]} WHERE id=?", (rid,))
        file_removed = False
        if file and real and os.path.isfile(real):
            try:
                os.remove(real); file_removed = True  # delete the resolved path (no symlink TOCTOU)
            except OSError: pass
        return {"ok": True, "file_removed": file_removed}
    app.post(f"/api/{kind}")(create)
    app.put(f"/api/{kind}")(update)
    app.delete(f"/api/{kind}/{{rid}}")(delete)

for _kind in TABLES:
    _register_crud(_kind)

# ---- settings ----
@app.get("/api/settings")
def get_settings(): return db.get_settings()

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
    except Exception as e:
        # Non-validation failures (e.g. IO errors during the phase-2 re-key)
        # must surface with detail instead of a bare 500 or a silent success.
        # NOTE: full atomic rollback of a partial re-key needs crypto.py changes
        # (see FIXES-D-server-media.md) — originals are kept in .rekey-backup.
        log.exception("[images] passphrase change failed")
        raise HTTPException(500, f"passphrase change failed — if blobs were "
                                 f"mid-rewrite, originals are kept in "
                                 f"data/encrypted/.rekey-backup: {e}")

@app.post("/api/images/enabled")
def img_enabled(body: dict = Body(...)):
    return crypto.set_enabled(bool(body.get("on")))

@app.post("/api/images/unlock")
def img_unlock(b: PassBody):
    if not crypto.unlock(b.passphrase): raise HTTPException(400, "wrong passphrase")
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
    hdr = {"User-Agent": "Obscura/0.9 (self-hosted media library)"}

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
def _safe_dirs(dirs) -> list:
    """Confine requested scan folders to settings.dirs (fail closed when empty)."""
    out = []
    for d in dirs or []:
        try:
            out.append(media_engine.safe_path(d))
        except media_engine.PathNotAllowed as e:
            raise HTTPException(403, str(e))
    return out


@app.post("/api/scan")
def scan(body: dict = Body(...)):
    files = scanner.walk(_safe_dirs(body.get("dirs", [])))
    return {"found": files, "count": len(files)}

@app.post("/api/scan/candidates")
def scan_candidates(body: dict = Body(...)):
    files = scanner.walk(_safe_dirs(body.get("dirs", [])))
    for f in files:
        f["imported"] = scanner.is_imported(f["path"])
        f["guess_title"] = scanner.guess_title(f["path"])
        dur = scanner.probe_duration(f["path"])
        f["duration_min"] = dur
        f["guess_kind"] = scanner.guess_kind(f["path"], duration_min=dur)
        f["posters"] = [os.path.basename(p) for p in scanner.find_posters(f["path"])]
    files.sort(key=lambda x: (x["imported"], x["dir"], x["name"]))
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
def scan_import(b: ImportBody):
    try:
        path = media_engine.safe_path(b.path)
    except media_engine.PathNotAllowed as e:
        raise HTTPException(403, str(e))
    try:
        rec = scanner.import_file(
            path, b.kind, b.title, year=b.year, date=b.date,
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

_PY_MARKERS = re.compile(
    r"(?m)^\s*(?:import\s|from\s+\S+\s+import\s|def\s|class\s|lambda\b)"
    r"|__\w+__|\b(?:eval|exec|compile|open|getattr|setattr|globals|locals|vars|breakpoint)\s*\(")


def _scraper_needs_confirm(content: bytes) -> bool:
    """Decide "this is executable Python" from CONTENT, not the filename — an
    extension-less upload (or a file literally named `py`) used to skip the
    consent gate while the engine still executed it as Python. Fail closed:
    anything that is not plainly declarative YAML/JSON data counts as Python."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return True
    if _PY_MARKERS.search(text):
        return True
    try:
        import yaml
        data = yaml.safe_load(text)
    except Exception:
        return True
    return not isinstance(data, (dict, list))


@app.post("/api/scrapers/file")
async def scraper_upload(file: UploadFile = File(...), kind: str = Form("movie"),
                         confirm: str = Form("")):
    content = await file.read()
    if _scraper_needs_confirm(content) and \
            confirm != "I UNDERSTAND PYTHON SCRAPERS RUN AS LOCAL CODE":
        raise HTTPException(400, "Python scrapers execute as local code — send "
                                'confirm="I UNDERSTAND PYTHON SCRAPERS RUN AS LOCAL CODE"')
    try:
        sid = scraper_engine.add(file.filename, content, kind)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": sid}

@app.post("/api/scrapers/{sid}/toggle")
def scraper_toggle(sid: str):
    scraper_engine.toggle(sid); return {"ok": True}

@app.delete("/api/scrapers/{sid}")
def scraper_delete(sid: str):
    scraper_engine.remove(sid); return {"ok": True}

@app.post("/api/scrapers/{sid}/structure")
def scraper_structure(sid: str, body: dict = Body(...)):
    scraper_engine.set_structure(sid, body); return {"ok": True}

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


def _safe_image_url(url: str) -> bool:
    """SSRF guard: public http(s) endpoints only.

    Rejects non-http schemes and hosts that resolve to loopback / private /
    link-local / reserved / multicast addresses, so a scraper result can't
    make the server fetch internal services (127.0.0.1, 169.254.169.254, …)."""
    import socket, ipaddress
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        infos = socket.getaddrinfo(p.hostname, p.port or
                                   (443 if p.scheme == "https" else 80))
    except Exception:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False
    return True


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


def _fetch_image(url: str, get) -> "requests.Response":
    """GET `url` via `get`, re-validating every redirect hop.

    `requests` follows redirects by default, which let a hostile first hop 302
    straight past _safe_image_url to loopback/LAN/cloud-metadata. Redirects are
    disabled at the call sites and each Location is re-checked here (max 3 hops)."""
    for _ in range(3):
        r = get(url)
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            url = urljoin(url, r.headers["location"])
            if not _safe_image_url(url):
                raise ValueError(f"redirect target blocked by SSRF guard: {url[:80]}")
            continue
        return r
    raise ValueError("too many redirects")


def _download_image(url: str) -> str:
    """Download image from URL, store locally, return /api/images/ path."""
    if not url or not url.startswith("http"):
        return url
    if not _safe_image_url(url):
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
                    r = _fetch_image(url, lambda u: iafd_scraper.iafd_session.get(
                        u, timeout=15, allow_redirects=False))
                    return _store_response_image(r)
                except Exception as e:
                    log.warning("[download-image] iafd session failed: %s — %s", url[:80], e)
                    return url
        # Use cloudscraper for other Cloudflare-protected sites,
        # fall back to plain requests for others.
        try:
            r = _fetch_image(url, lambda u: _cf_scraper.get(
                u, timeout=15, allow_redirects=False, **extra))
        except Exception:
            r = _fetch_image(url, lambda u: requests.get(
                u, timeout=15, allow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0", **extra.get('headers', {})}))
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
    if not path: raise HTTPException(404)
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

# ---- maintenance lock: serializes wipe/restore against each other ----
_MAINT_LOCK = threading.Lock()
MAX_RESTORE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB cap on restore uploads

# ---- wipe ----
@app.post("/api/wipe")
def wipe_all(body: dict = Body(default={})):
    if (body or {}).get("confirm") != "DELETE MY LIBRARY":
        raise HTTPException(400, 'confirmation required: send {"confirm":"DELETE MY LIBRARY"}')
    if not _MAINT_LOCK.acquire(blocking=False):
        raise HTTPException(409, "another maintenance operation (wipe/restore) is already running — try again shortly")
    try:
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
    finally:
        _MAINT_LOCK.release()
    return {"ok": True}

# ---- backup / restore ----
@app.get("/api/backup/export")
def backup_export():
    data = backup_engine.export_zip()
    stamp = time.strftime("%Y%m%d-%H%M")
    return Response(content=data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="Obscura-Backup-{stamp}.zip"'})

@app.post("/api/backup/restore")
async def backup_restore(file: UploadFile = File(...), confirm: str = Form("")):
    if confirm != "RESTORE":
        raise HTTPException(400, 'confirmation required: send form field confirm="RESTORE"')
    # stream the upload with a cap instead of an unbounded read()
    chunks, total = [], 0
    while True:
        chunk = await file.read(1 << 20)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_RESTORE_BYTES:
            raise HTTPException(413, "backup archive exceeds the 2 GB restore cap")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not _MAINT_LOCK.acquire(blocking=False):
        raise HTTPException(409, "another maintenance operation (wipe/restore) is already running — try again shortly")
    try:
        try: n = backup_engine.restore_zip(data)
        except ValueError as e: raise HTTPException(400, str(e))
        except Exception as e: raise HTTPException(500, f"restore failed: {e}")
    finally:
        _MAINT_LOCK.release()
    return {"ok": True, "entries": n}

# ---- serve the frontend (mount LAST so /api routes win) ----
def frontend_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", ""), "frontend")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

FRONTEND = frontend_dir()
if os.path.isdir(FRONTEND):
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
