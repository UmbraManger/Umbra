"""Erotik.com scraper — Obscura-compatible.

Supports: movie-by-url, movie-by-name
API: https://api.erotik.com/content/movies
Search: https://api.erotik.com/autocomplete
"""

import re
import requests
from bs4 import BeautifulSoup

_session = requests.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                         "Accept-Language": "en-US,en;q=0.5"})


def _dig(obj, *keys):
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k)
        else:
            return None
    return obj


def _dur(seconds):
    if not seconds:
        return ""
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h}:{m:02d}:{s:02d}"


def _get_movie_by_url(url):
    """Fetch movie page, extract meta ID, then call API."""
    try:
        body = _session.get(url, timeout=15).text
    except Exception:
        return None
    m = re.search(r'<meta\s+name="id"\s+content="([\w\d]+)"', body)
    if not m:
        return None
    return _get_movie_by_id(m.group(1), url)


def _get_movie_by_id(movie_id, source_url=""):
    """Call API with movie ID and return flat result."""
    r = _session.get(f"https://api.erotik.com/content/movies?idList[]={movie_id}", timeout=15)
    if r.status_code != 200:
        return None
    data = r.json()
    if not data:
        return None
    d = data[0]

    desc = _dig(d, "description", "en") or ""
    if desc:
        desc = BeautifulSoup(desc, "html.parser").get_text(strip=True)

    directors = _dig(d, "directors") or []
    director = ", ".join(_dig(x, "name") for x in directors if _dig(x, "name"))

    tags_data = _dig(d, "categories") or []
    tags = [_dig(t, "name", "en") for t in tags_data
            if _dig(t, "name", "en") and t.get("sortOrder", 0) >= 0]

    result = {
        "title": _dig(d, "name", "en") or "",
        "desc": desc,
        "studio": _dig(d, "studio", "name") or "",
        "poster_f": _dig(d, "boxCover", "default") or _dig(d, "image", "default") or "",
        "director": director,
        "duration_min": _dur(_dig(d, "durationSeconds")),
        "year": str(_dig(d, "releaseYear") or ""),
        "url": source_url,
    }
    if tags:
        result["categories"] = tags

    # Performers
    performers = [p.get("name", "") for p in (d.get("performers") or []) if p.get("name")]
    if performers:
        result["performers"] = performers

    # Scene count from childItemNumbers
    children = d.get("childItemNumbers") or []
    if children:
        result["scenes"] = len(children)

    # Use the English URL from the API
    url_en = _dig(d, "url", "en")
    if url_en:
        result["url"] = url_en
    else:
        urls = list((_dig(d, "url") or {}).values())
        if urls:
            result["url"] = urls[0]

    return result


def _search(query):
    """Search via autocomplete API and return best match."""
    r = _session.get(f"https://api.erotik.com/autocomplete?q={requests.utils.quote(query)}", timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    results = data.get("results", [])

    query_lower = query.lower().strip()

    # Filter to movies only and rank by relevance
    movies = [r for r in results if "(Movie)" in r.get("displayName", "")]
    if not movies:
        movies = results  # fallback to all results

    # Score: exact title match > contains > partial
    def _score(item):
        name = item.get("displayName", "").lower().replace("(movie)", "").strip()
        if name == query_lower:
            return 0
        if query_lower in name:
            return 1
        # Check word overlap
        qwords = set(query_lower.split())
        nwords = set(name.split())
        return 10 - len(qwords & nwords)

    movies.sort(key=_score)

    # Try the best match
    for movie in movies:
        url = movie.get("url", "")
        if not url:
            continue
        full_url = f"https://erotik.com{url}"
        result = _get_movie_by_url(full_url)
        if result:
            return result

    return None


def scrape(title="", url="", html="", **kwargs):
    """Obscura scraper entry point."""
    if url:
        result = _get_movie_by_url(url)
        if result:
            return result

    if title:
        result = _search(title)
        if result:
            return result

    return {}
