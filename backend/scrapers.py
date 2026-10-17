"""Runs external scrapers.
Python contract:  the file must define  scrape(title="", url="", html="") -> dict
                  (an optional kind="" parameter is also passed through when the
                  scraper's signature accepts it, or via **kwargs)
YAML contract:    selectors mapping — see example at the bottom."""
import os, json, uuid, re, inspect, threading
from urllib.parse import urlparse, quote
import importlib.util
import requests, yaml
from bs4 import BeautifulSoup
import db
import net_guard

# Every meta.json mutation is a read-modify-write; bursting several scrapers
# (deleting many rows in one go, install_bundled racing a toggle) must not let
# last-writer-wins undo the others — so all mutators serialize on this lock.
_META_LOCK = threading.RLock()

def _locked(fn):
    def wrapper(*a, **k):
        with _META_LOCK:
            return fn(*a, **k)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper

META = os.path.join(db.SCRAPER_DIR, "meta.json")
# Tombstone for deliberately deleted bundled scrapers: their files ship inside
# the frozen bundle, so install_bundled() would reinstall one on every boot
# unless the fact the user removed it is recorded here. User-uploaded scrapers
# (uuid names) never come back on their own and need no tombstone.
REMOVED = os.path.join(db.SCRAPER_DIR, "removed.json")

def _removed() -> set:
    try:
        with open(REMOVED, encoding="utf-8") as f:
            v = json.load(f)
        return {x for x in v if isinstance(x, str)}
    except Exception:
        return set()

def _mark_removed(filename: str) -> None:
    try:
        os.makedirs(db.SCRAPER_DIR, exist_ok=True)
        # merge BEFORE open("w") truncates the very file being read back
        merged = sorted(_removed() | {filename})
        with open(REMOVED, "w", encoding="utf-8") as f:
            json.dump(merged, f)
    except OSError:
        pass

def _meta() -> list:
    try:
        with open(META, encoding="utf-8") as f:
            return json.load(f)
    except Exception: return []

def _save_meta(m):
    with open(META, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2)

def list_all():
    out = []
    for s in _meta():
        p = _scraper_path(s)
        out.append({**s, "exists": bool(p and os.path.exists(p)),
                    "size": (os.path.getsize(p) if p and os.path.exists(p) else 0)})
    return out


def _scraper_path(s: dict) -> str | None:
    """Validated absolute path of a scraper file, or None when meta.json's
    'file' entry is crafted (traverses out, is nested, absolute, '.' or '..').
    meta.json can arrive via a restored backup, so it is never trusted (bug #4)."""
    fn = s.get("file") or ""
    if not fn or fn != os.path.basename(fn.replace("\\", "/")):
        return None
    p = os.path.realpath(os.path.join(db.SCRAPER_DIR, fn))
    root = os.path.realpath(db.SCRAPER_DIR)
    return p if os.path.dirname(p) == root else None

@_locked
def add(filename: str, content: bytes, kind) -> tuple:
    """Install an uploaded scraper. Returns (meta_id, kinds). kind accepts a
    single kind or a multi-assignment list (movie/scene/performer checkboxes).
    Python sources are sanity-checked against what the bytes actually implement:
    assignment kinds are kept, and evidence-backed kinds the caller missed are
    corrected in by merging detect_kinds' findings (display-only labels)."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("py", "yml", "yaml"):
        raise ValueError("only .py / .yml / .yaml")
    kinds = [k for k in (kind if isinstance(kind, (list, tuple, set)) else ([kind] if kind else []))
             if k in ("movie", "scene", "performer")]
    if ext == "py":
        have = set(kinds) | set(detect_kinds(content.decode("utf-8", "replace")))
        kinds = [k for k in ("movie", "scene", "performer") if k in have] or ["scene"]
    fid = uuid.uuid4().hex[:10]
    fname = f"{fid}.{ext}"
    with open(os.path.join(db.SCRAPER_DIR, fname), "wb") as f:
        f.write(content)
    meta = _meta()
    meta.append({"id": fid, "name": filename, "file": fname,
                 "type": "python" if ext == "py" else "yaml",
                 "kind": kinds or ["movie"], "enabled": True, "structure": None})
    _save_meta(meta)
    return fid, kinds

@_locked
def remove(sid):
    for s in _meta():
        if s["id"] == sid:
            p = _scraper_path(s)          # never delete outside the scraper folder
            if p:
                try: os.remove(p)
                except OSError: pass
            if str(sid).startswith("bundled-") and s.get("file"):
                _mark_removed(s["file"])
    _save_meta([s for s in _meta() if s["id"] != sid])

@_locked
def toggle(sid):
    meta = _meta()
    for s in meta:
        if s["id"] == sid: s["enabled"] = not s.get("enabled", True)
    _save_meta(meta)

@_locked
def set_structure(sid, structure: dict):
    meta = _meta()
    for s in meta:
        if s["id"] == sid: s["structure"] = structure
    _save_meta(meta)

# ---- kind auto-detection -------------------------------------------------
# Bundled and uploaded python scrapers are classified by what they actually
# implement, so the Settings list stops saying "movie" for every scraper.
_KDEF = {"performer": re.compile(r"(?m)^\s*def\s+\w*(performer|pornstar|actor)\w*", re.I),
         "scene": re.compile(r"(?m)^\s*def\s+\w*(scene|clip|gallery)\w*", re.I),
         "movie": re.compile(r"(?m)^\s*def\s+\w*movie\w*", re.I)}
# lookbehind instead of \b so tokens like search_scenes count ("_" isn't a letter)
_KWORD = {"performer": re.compile(r"(?<![A-Za-z])(performer|pornstar|actor)", re.I),
          "scene": re.compile(r"(?<![A-Za-z])(scene|clip|gallery)", re.I),
          "movie": re.compile(r"(?<![A-Za-z])(movie|film)", re.I)}
# dispatch evidence: calling a kind-named function (bundled shims reach scenes
# through p1api.scene_by_url(...) with no local defs) qualifies a kind too
_KCALL = {"performer": re.compile(r"(?<![A-Za-z])(?:performers?|pornstars?|actors?)\w*\s*\(", re.I),
          "scene": re.compile(r"(?<![A-Za-z])(?:scenes?|clips?|galleries?)\w*\s*\(", re.I),
          "movie": re.compile(r"(?<![A-Za-z])(?:movies?|films?)\w*\s*\(", re.I)}

def detect_kinds(src: str) -> list:
    """All kinds a python scraper evidences: defining kind functions and/or
    calling kind-named dispatchers (define OR call). Ordered best-evidence
    first (def names 10x wording). Files with no evidence at all fall back to
    the single most-mentioned marker word, then 'movie'. The label is
    display/default only — run_by_id always passes the caller's kind through."""
    h = {k: len(r.findall(src)) for k, r in _KDEF.items()}
    c = {k: len(r.findall(src)) for k, r in _KCALL.items()}
    out = sorted((k for k in h if h[k] or c[k]),
                 key=lambda k: (h[k] * 10 + c[k], k == "scene"), reverse=True)
    if out:
        return out
    w = {k: len(r.findall(src)) for k, r in _KWORD.items()}
    best = max(w, key=lambda k: (w[k], k == "scene"))
    return [best] if w[best] else ["movie"]

def detect_kind(src: str) -> str:
    return detect_kinds(src)[0]

def run_python(path: str, payload: dict) -> dict:
    # Execution gate: Python scrapers are arbitrary local code — off by default.
    if not db.get_settings().get("pyScrapers"):
        raise ValueError("Python scrapers are disabled — enable "
                         "Settings › External Scrapers › Python Scrapers "
                         "(they execute as local code)")
    spec = importlib.util.spec_from_file_location("umbra_scraper_" + uuid.uuid4().hex, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "scrape"):
        raise ValueError("python scraper must define scrape(title='', url='', html='')")
    # Only pass keys the scraper's scrape() actually accepts (or all of them if it
    # takes **kwargs) — keeps older scrapers without a kind= param working unchanged.
    try:
        params = inspect.signature(mod.scrape).parameters
        if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            payload = {k: v for k, v in payload.items() if k in params}
    except (TypeError, ValueError):
        pass
    return mod.scrape(**payload) or {}

def _sel(soup, selector, attr):
    el = soup.select_one(selector) if selector else None
    if el is None: return None
    if attr and attr.startswith("ld:"):
        # dotted path into a JSON-LD block: ld:name, ld:thumbnailUrl.0 — pages
        # that only expose schema.org VideoObject data are still scrapable
        try:
            import json as _json
            v = _json.loads(el.get_text())
        except Exception:
            return None
        if isinstance(v, list):
            v = next((d for d in v if isinstance(d, dict)), None)
        for part in attr[3:].split("."):
            if isinstance(v, dict):
                v = v.get(part)
            elif isinstance(v, list):
                if part.isdigit():                    # ld:thumbnailUrl.0 → index
                    v = v[int(part)] if int(part) < len(v) else None
                else:                                 # ld:actor → first object
                    v = next((d for d in v if isinstance(d, dict)), None)
            else:
                break
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):                       # e.g. thumbnailUrl: [str, ...]
            return next((s for s in v if isinstance(s, str)), None)
        return v if isinstance(v, str) and v.strip() else None
    if not attr or attr == "text": return el.get_text(" ", strip=True)
    return el.get(attr)

def _duration_min(raw):
    """'12:34' / '1:02:12' / 'PT12M34S' / '75' → minutes as int; None on miss."""
    v = str(raw).strip()
    m = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", v, re.I)
    if m and any(m.groups()):
        h, mn, s = (int(g) if g else 0 for g in m.groups())
        return h * 60 + mn + round(s / 60)
    if ":" in v:
        nums = [int(n) for n in re.findall(r"\d+", v)][-3:]
        while len(nums) < 3:
            nums.insert(0, 0)
        h, mn, s = nums
        return h * 60 + mn + round(s / 60)
    m = re.search(r"\d+", v)
    return int(m.group()) if m else None

_LIST_KEYS = {"catNames", "performers", "covers"}

def run_yaml(path: str, title: str = "", url: str = "") -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    target = url
    if not target:
        tpl = (cfg.get("search") or {}).get("url", "")
        if tpl and title: target = tpl.replace("{title}", quote(title))
    if not target: raise ValueError(
        "no url in the request and no search template in the yaml — "
        'add "search: {url: ...{title}}" to the scraper or fetch by page URL')
    if not net_guard.safe_image_url(target):
        raise ValueError("blocked unsafe scraper target URL (private/loopback address)")
    # safe_get re-validates every redirect hop (P2: Gap 2, blind redirects).
    r = net_guard.safe_get(requests, target, timeout=25,
                           headers={"User-Agent": "Mozilla/5.0 (Umbra)"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = {}
    for key, rule in (cfg.get("fields") or {}).items():
        if not isinstance(rule, dict): continue
        attr = rule.get("attr", "text")
        if rule.get("multi"):
            # select_all — cast/category/cover listings collect into the array
            # fields the fetch flow consumes (catNames/performers/covers)
            vals = []
            for el in soup.select(rule.get("selector") or ""):
                v = el.get_text(" ", strip=True) if (not attr or attr == "text") else el.get(attr)
                if v: vals.append(v.strip())
            val = vals or None
        else:
            val = _sel(soup, rule.get("selector", ""), attr)
        if val in (None, ""): continue
        t = (rule.get("transform") or "").lower()
        if t == "int":
            m = re.search(r"\d+", str(val)); val = int(m.group()) if m else None
        elif t == "duration":
            val = _duration_min(val)
        elif t == "lower": val = str(val).lower()
        elif t == "title": val = str(val).title()
        if val in (None, ""): continue
        if key in _LIST_KEYS and isinstance(val, str):   # comma list → array
            val = [x.strip() for x in val.split(",") if x.strip()]
            if not val: continue
        out[key] = val
    return out

@_locked
def install_bundled() -> None:
    """Frozen build: copy the scraper library shipped inside the bundle
    (_MEIPASS/scrapers) into data/scrapers and register it in meta.json, so the
    bundled scrapers work in the portable app without the user uploading them.

    Bundled files keep their original names and get a deterministic id, while
    user-installed scrapers are uuid-named (see add()), so the two never collide;
    an existing file of the same name is left alone. Registered disabled: python
    scrapers execute as local code, and the run_python gate stays the user's
    explicit choice to flip."""
    import sys as _sys
    src = os.path.join(getattr(_sys, "_MEIPASS", ""), "scrapers")
    if not getattr(_sys, "frozen", False) or not os.path.isdir(src):
        return
    os.makedirs(db.SCRAPER_DIR, exist_ok=True)
    meta = _meta()
    removed = _removed()
    known = {s.get("file") for s in meta}
    changed = False
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".py"):
            continue
        if fn in removed:      # deleted by the user — stays deleted (#no-resurrect)
            continue
        with open(os.path.join(src, fn), "rb") as f:
            content = f.read()
        dst = os.path.join(db.SCRAPER_DIR, fn)
        # refresh a file we installed before (the id marks it as ours); never touch
        # a file whose id isn't a bundled one.
        sid = "bundled-" + fn[:-3]
        ours = next((s for s in meta if s.get("id") == sid), None)
        kinds = detect_kinds(content.decode("utf-8", "replace"))
        if ours and ours.get("file") == fn:
            with open(dst, "wb") as f:
                f.write(content)
            # migrate single-kind-era installs: re-classify and bump the entry
            if ours.get("kind") != kinds and ours.get("type") == "python":
                ours["kind"] = kinds
                changed = True
            continue
        if fn in known or os.path.exists(dst):
            continue
        with open(dst, "wb") as f:
            f.write(content)
        meta.append({"id": sid, "name": fn[:-3], "file": fn, "type": "python",
                     "kind": kinds, "enabled": False, "structure": None})
        known.add(fn)
        changed = True
    if changed:
        _save_meta(meta)


def _default_kind(caller_kind: str, meta_kind) -> str:
    """Scrapers receive a single kind: the caller's, or (legacy meta) the
    scraper's first classification when the entry stores a list."""
    if caller_kind:
        return caller_kind
    if isinstance(meta_kind, list):
        return meta_kind[0] if meta_kind else ""
    return meta_kind or ""

def run_by_id(sid: str, title: str = "", url: str = "", kind: str = "", domain: str = "") -> dict:
    s = next((s for s in _meta() if s["id"] == sid), None)
    if not s: raise ValueError("scraper not found")
    if not s.get("enabled", True): raise ValueError("scraper is disabled")
    path = _scraper_path(s)
    if not path: raise ValueError("scraper file entry in meta.json is invalid")
    payload = {"title": title or "", "url": url or "",
               "kind": _default_kind(kind, s.get("kind")), "domain": domain or ""}
    if s["type"] == "python": return run_python(path, payload)
    return run_yaml(path, title=title, url=url)

def _host_matches(candidate: str, host: str) -> bool:
    """True when `candidate` — a domain, a URL, or an uploaded filename such as
    'shop.example.py' — designates `host` or a subdomain of it. Dot-boundary
    only: 'apex.com' must never match the host 'ex.com' (bug D6)."""
    c = (candidate or "").strip().lower()
    if not c:
        return False
    if "://" in c:
        c = (urlparse(c).hostname or "")
    c = c.split("/")[0].split(":")[0]
    for ext in (".py", ".yml", ".yaml"):
        if c.endswith(ext):
            c = c[:-len(ext)]
    c = c[4:] if c.startswith("www.") else c
    host = host[4:] if host.startswith("www.") else host
    if not c or not host:
        return False
    if host == c:
        return True
    return "." in c and host.endswith("." + c)


def run_for_site(src, title: str = "", url: str = "", kind: str = "") -> dict:
    raw = url or (src.get("url") if isinstance(src, dict) else str(src))
    host = (urlparse(raw).hostname or "").replace("www.", "")
    # Check scraper meta (name/structure). When a kind is requested, a scraper
    # classified for that kind beats the first host match (a scene-only HTML
    # mapping shouldn't serve a /pornstar/ URL just because it was added first).
    matched = [s for s in _meta()
               if s.get("enabled", True) and (_host_matches(s.get("name"), host) or
                   _host_matches((s.get("structure") or {}).get("source"), host))]
    if matched:
        fit = next((s for s in matched
                    if kind and kind in (s.get("kind") if isinstance(s.get("kind"), list) else [s.get("kind")])),
                   None)
        s = fit or matched[0]
        return run_by_id(s["id"], title=title, url=url, kind=kind, domain=host)
    # Check assigned scraper sites from settings
    sites = db.get_scraper_sites()
    for kind_sites in sites.values():
        for entry in kind_sites:
            if _host_matches(entry.get("domain"), host):
                scraper = next((s for s in _meta() if s["id"] == entry.get("scraper_id")), None)
                if scraper and scraper.get("enabled", True):
                    return run_by_id(scraper["id"], title=title, url=url, kind=kind, domain=host)
    raise ValueError(f"no scraper installed for {host or 'this site'} — add one in Settings › External Scrapers, or use AI")

# ---- example YAML scraper (save as data/scrapers/example.yml) ----
# kind: movie
# name: example-site.com
# search:
#   url: "https://example-site.com/search?q={title}"
# fields:
#   title:    { selector: "h1.title",   attr: text }
#   year:     { selector: "span.year",  attr: text, transform: int }
#   poster_f: { selector: "img.poster", attr: src }
#   desc:     { selector: "div.synopsis", attr: text }
