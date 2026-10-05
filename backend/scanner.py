"""Scan directories → candidate files → import as movies/scenes with metadata + images."""
import os, json, subprocess
import db

RESUME = os.path.join(db.DATA_DIR, "scanstate.json")

VIDEO_EXT = {".mp4", ".mkv", ".avi", ".webm", ".mov", ".m4v", ".wmv", ".mpg", ".mpeg"}
IMG_EXT   = (".jpg", ".jpeg", ".png", ".webp")

def _state() -> dict:
    try: return json.load(open(RESUME, encoding="utf-8"))
    except Exception: return {"done": []}

def _save_state(s: dict) -> None:
    json.dump(s, open(RESUME, "w", encoding="utf-8"))

def walk(dirs: list) -> list[dict]:
    found = []
    for d in dirs:
        if not os.path.isdir(d): continue
        for root, _, files in os.walk(d):
            for f in files:
                if os.path.splitext(f)[1].lower() in VIDEO_EXT:
                    # normpath: a configured folder like "D:/video" would otherwise
                    # yield mixed separators, and the exact-string compare in
                    # is_imported() would then miss the already-imported copy.
                    p = os.path.normpath(os.path.join(root, f))
                    try: size = os.path.getsize(p)
                    except OSError: size = 0
                    found.append({"path": p, "name": f, "size": size, "dir": root})
    return found

def _re_year(w: str) -> bool:
    return len(w) == 4 and w.isdigit() and 1900 <= int(w) <= 2100

def guess_title(path: str) -> str:
    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    if not ext and stem.startswith("."):
        stem = ""  # splitext gotcha: '.mp4' parses as a dotfile with no extension
    base = stem.replace(".", " ").replace("_", " ").replace("-", " ")
    base = " ".join(w for w in base.split() if not _re_year(w))
    # Per-word capitalize(): title() would turn "don't" into "Don'T" (bug D4).
    return " ".join(w.capitalize() for w in base.split()) or "Untitled"

def probe_duration(path: str) -> int | None:
    """Duration in minutes (int) via ffprobe, or None if unavailable."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, timeout=15)
        if r.returncode != 0: return None
        j = json.loads(r.stdout.decode("utf-8", "ignore"))
        dur = float(j.get("format", {}).get("duration", 0) or 0)
        return int(dur / 60) if dur else None
    except Exception:
        return None

def guess_kind(path: str, duration_min: int | None = None) -> str:
    """Duration is the strongest signal (>=50 min = movie), then name keywords, then size."""
    p = path.lower()
    size_mb = 0
    try: size_mb = os.path.getsize(path) / 1048576   # real path: p is lowercased (bug D2)
    except OSError: pass
    if duration_min:
        return "movie" if duration_min >= 50 else "scene"
    if "movie" in p or "film" in p: return "movie"
    if any(k in p for k in ("scene", "ep", "s0", "clip")): return "scene"
    if size_mb >= 900: return "movie"
    if size_mb and size_mb < 350: return "scene"
    return "scene"

def _poster_rank(name: str) -> int:
    """Sort key so the front cover wins: back artwork ('back', 'rear') sorts last,
    front-ish names ('front', 'cover', 'poster', 'folder') first (bug D3)."""
    low = name.lower()
    if "back" in low or "rear" in low:
        return 2
    if any(k in low for k in ("front", "cover", "poster", "folder")):
        return 0
    return 1


def find_posters(path: str) -> list[str]:
    d, base = os.path.split(path)
    stem = os.path.splitext(base)[0].lower()
    out = []
    try:
        for f in sorted(os.listdir(d), key=lambda n: (_poster_rank(n), n.lower())):
            low = f.lower()
            if not low.endswith(IMG_EXT): continue
            if (stem and stem in low) or any(k in low for k in ("cover", "front", "poster", "back", "thumb")):
                out.append(os.path.join(d, f))
    except OSError:
        pass
    return out

def _norm_path(path: str) -> str:
    """Case/separator-insensitive path key: the same file reached via 'D:/video'
    and 'D:\\video' (or different case on Windows) must compare equal (bug D1)."""
    return os.path.normcase(os.path.normpath(path))


def is_imported(path: str) -> bool:
    p = _norm_path(path)
    return p in {_norm_path(x) for x in _state().get("done", [])}

def mark_done(path: str) -> None:
    s = _state()
    done = s.setdefault("done", [])
    p = _norm_path(path)
    if not any(_norm_path(x) == p for x in done):
        done.append(path)              # stored as given (stable file format)
        _save_state(s)

def remove_done(path: str) -> None:
    s = _state()
    done = s.get("done", [])
    p = _norm_path(path)
    kept = [x for x in done if _norm_path(x) != p]
    if kept != done:
        s["done"] = kept
        _save_state(s)

def _img_ref(path: str) -> str:
    from crypto import store_image
    import mimetypes
    with open(path, "rb") as f:
        data = f.read()
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    return "/api/images/" + store_image(data, mime)

def import_file(path: str, kind: str, title: str, year: int | None = None,
                date: str | None = None, studio_id: str | None = None,
                movie_id: str | None = None, duration_min: int = 0, director: str = "",
                desc: str = "", actor_ids: list | None = None,
                category_ids: list | None = None, fav: bool = False,
                copy_posters: bool = True) -> dict:
    rec = {
        "id": db.new_id("mv" if kind == "movie" else "sc"),
        "title": title or guess_title(path),
        "file_path": path,
        "fav": 1 if fav else 0,
    }
    if kind == "movie":
        rec.update({"year": year, "studio_id": studio_id, "duration_min": duration_min,
                    "scenes": 0, "director": director or "", "desc": desc or "",
                    "actor_ids": json.dumps(actor_ids or []),
                    "category_ids": json.dumps(category_ids or [])})
        posters = find_posters(path) if copy_posters else []
        if len(posters) > 0: rec["poster_f"] = _img_ref(posters[0])
        if len(posters) > 1: rec["poster_b"] = _img_ref(posters[1])
        cols = list(rec); qs = ",".join("?" * len(rec))
        db.execute(f"INSERT INTO movies ({','.join(cols)}) VALUES ({qs})", list(rec.values()))
    else:
        rec.update({"date": date, "studio_id": studio_id, "movie_id": movie_id,
                    "duration_min": duration_min, "director": director or "", "desc": desc or "",
                    "cover_a": "", "cover_b": "", "thumb": 0,
                    "actor_ids": json.dumps(actor_ids or []),
                    "category_ids": json.dumps(category_ids or [])})
        covers = find_posters(path) if copy_posters else []
        if len(covers) > 0: rec["cover_a"] = _img_ref(covers[0])
        if len(covers) > 1: rec["cover_b"] = _img_ref(covers[1])
        cols = list(rec); qs = ",".join("?" * len(rec))
        db.execute(f"INSERT INTO scenes ({','.join(cols)}) VALUES ({qs})", list(rec.values()))
    mark_done(path)
    return rec
