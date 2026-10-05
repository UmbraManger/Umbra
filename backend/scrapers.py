"""Runs external scrapers.
Python contract:  the file must define  scrape(title="", url="", html="") -> dict
                  (an optional kind="" parameter is also passed through when the
                  scraper's signature accepts it, or via **kwargs)
YAML contract:    selectors mapping — see example at the bottom."""
import os, json, uuid, re, inspect
from urllib.parse import urlparse, quote
import importlib.util
import requests, yaml
from bs4 import BeautifulSoup
import db
import net_guard

META = os.path.join(db.SCRAPER_DIR, "meta.json")

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

def add(filename: str, content: bytes, kind: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("py", "yml", "yaml"):
        raise ValueError("only .py / .yml / .yaml")
    fid = uuid.uuid4().hex[:10]
    fname = f"{fid}.{ext}"
    with open(os.path.join(db.SCRAPER_DIR, fname), "wb") as f:
        f.write(content)
    meta = _meta()
    meta.append({"id": fid, "name": filename, "file": fname,
                 "type": "python" if ext == "py" else "yaml",
                 "kind": kind, "enabled": True, "structure": None})
    _save_meta(meta)
    return fid

def remove(sid):
    for s in _meta():
        if s["id"] == sid:
            p = _scraper_path(s)          # never delete outside the scraper folder
            if p:
                try: os.remove(p)
                except OSError: pass
    _save_meta([s for s in _meta() if s["id"] != sid])

def toggle(sid):
    meta = _meta()
    for s in meta:
        if s["id"] == sid: s["enabled"] = not s.get("enabled", True)
    _save_meta(meta)

def set_structure(sid, structure: dict):
    meta = _meta()
    for s in meta:
        if s["id"] == sid: s["structure"] = structure
    _save_meta(meta)

def run_python(path: str, payload: dict) -> dict:
    # Execution gate: Python scrapers are arbitrary local code — off by default.
    if not db.get_settings().get("pyScrapers"):
        raise ValueError("Python scrapers are disabled — enable "
                         "Settings › External Scrapers › Python Scrapers "
                         "(they execute as local code)")
    spec = importlib.util.spec_from_file_location("obscura_scraper_" + uuid.uuid4().hex, path)
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
    if not attr or attr == "text": return el.get_text(" ", strip=True)
    return el.get(attr)

def run_yaml(path: str, title: str = "", url: str = "") -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    target = url
    if not target:
        tpl = (cfg.get("search") or {}).get("url", "")
        if tpl and title: target = tpl.replace("{title}", quote(title))
    if not target: raise ValueError("no url and no search template in yaml")
    if not net_guard.safe_image_url(target):
        raise ValueError("blocked unsafe scraper target URL (private/loopback address)")
    r = requests.get(target, timeout=25, headers={"User-Agent": "Mozilla/5.0 (Obscura)"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = {}
    for key, rule in (cfg.get("fields") or {}).items():
        if not isinstance(rule, dict): continue
        val = _sel(soup, rule.get("selector", ""), rule.get("attr", "text"))
        if val in (None, ""): continue
        t = (rule.get("transform") or "").lower()
        if t == "int":
            m = re.search(r"\d+", str(val)); val = int(m.group()) if m else None
        elif t == "lower": val = str(val).lower()
        elif t == "title": val = str(val).title()
        if val not in (None, ""): out[key] = val
    return out

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
    known = {s.get("file") for s in meta}
    changed = False
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(src, fn), "rb") as f:
            content = f.read()
        dst = os.path.join(db.SCRAPER_DIR, fn)
        # refresh a file we installed before (the id marks it as ours); never touch
        # a file whose id isn't a bundled one.
        sid = "bundled-" + fn[:-3]
        ours = next((s for s in meta if s.get("id") == sid), None)
        if ours and ours.get("file") == fn:
            with open(dst, "wb") as f:
                f.write(content)
            continue
        if fn in known or os.path.exists(dst):
            continue
        with open(dst, "wb") as f:
            f.write(content)
        meta.append({"id": sid, "name": fn[:-3], "file": fn, "type": "python",
                     "kind": "movie", "enabled": False, "structure": None})
        known.add(fn)
        changed = True
    if changed:
        _save_meta(meta)


def run_by_id(sid: str, title: str = "", url: str = "", kind: str = "", domain: str = "") -> dict:
    s = next((s for s in _meta() if s["id"] == sid), None)
    if not s: raise ValueError("scraper not found")
    if not s.get("enabled", True): raise ValueError("scraper is disabled")
    path = _scraper_path(s)
    if not path: raise ValueError("scraper file entry in meta.json is invalid")
    payload = {"title": title or "", "url": url or "", "kind": kind or s.get("kind") or "", "domain": domain or ""}
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
    # Check scraper meta (name/structure)
    for s in _meta():
        if not s.get("enabled", True): continue
        if _host_matches(s.get("name"), host) or \
                _host_matches((s.get("structure") or {}).get("source"), host):
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
