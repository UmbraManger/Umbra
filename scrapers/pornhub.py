"""Pornhub scraper - Umbra-compatible.

Supports: scene/movie by-url, scene/movie by-name
Sites: pornhub.com and its country mirrors (cn.pornhub.com, etc.)

Parses the public pages only: JSON-LD VideoObject for title/duration/upload
date/thumbnail/channel, the performerCard list for performers, and the
under-player tag row for categories. Search-ranked by word overlap, exact
title first, then the best candidate's detail page is fetched.
"""

import re
import requests
from bs4 import BeautifulSoup

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})

_BASE = "https://www.pornhub.com"


def _clean(text):
    return re.sub(r"\s+", " ", text).strip() if text else ""


def _duration_min(raw):
    """PT00H12M26S -> 12."""
    m = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(raw or ""), re.I)
    if not m or not any(m.groups()):
        return None
    h, mn, s = (int(g) if g else 0 for g in m.groups())
    return h * 60 + mn + round(s / 60)


def _get(url):
    r = _session.get(url, timeout=20, allow_redirects=True)
    if r.status_code != 200 or "view_video" not in url and r.url != url:
        pass  # redirects and dust are fine; content checks happen downstream
    r.raise_for_status()
    return r.text


def _json_ld(soup):
    for el in soup.select('script[type="application/ld+json"]'):
        try:
            d = __import__("json").loads(el.get_text())
        except Exception:
            continue
        if isinstance(d, list):
            d = next((x for x in d if isinstance(x, dict) and x.get("@type") == "VideoObject"), None)
        if isinstance(d, dict) and d.get("@type") == "VideoObject":
            return d
    return {}


def _performers(soup):
    names, seen = [], set()
    for el in soup.select("a[data-label='pornstar']"):
        name = _clean(el.get_text())
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


def _categories(soup):
    """Under-player chips: Categories row first, Tags row fills in. Site-nav
    dropdowns use other markup, so these data-label buttons stay video-level."""
    tags, seen = [], set()
    for sel in ("a[data-label='category']", "a[data-label='tag']"):
        for el in soup.select(sel):
            t = _clean(el.get_text())
            if t and t.lower() not in seen:
                seen.add(t.lower())
                tags.append(t)
    return tags


def _scrape_page(url):
    soup = BeautifulSoup(_get(url), "html.parser")
    ld = _json_ld(soup)
    out = {}
    title = _clean(ld.get("name") or "")
    if title:
        out["title"] = out["originaltitle"] = title
    if ld.get("duration"):
        out["durationMin"] = _duration_min(ld["duration"])
    date = ld.get("uploadDate") or ld.get("datePublished")
    if date:
        out["date"] = str(date)[:10]
    author = ld.get("author")
    if isinstance(author, dict):
        author = author.get("name")
    if author:
        out["studioName"] = _clean(author)
    thumb = ld.get("thumbnailUrl")
    if isinstance(thumb, list):
        thumb = thumb[0] if thumb else None
    if thumb:
        out["posterF"] = thumb
        out["covers"] = [thumb]
    performers = _performers(soup)
    if performers:
        out["performers"] = performers
    cats = _categories(soup)
    if cats:
        out["categories"] = out["catNames"] = cats
    if url:
        out["url"] = url
    return out


def _norm(text):
    return re.sub(r"[^0-9a-z]+", " ", text.lower()).strip()


def _match_score(query, title):
    """Ranking tuple: lower = better. Exact 0; title containing the query 1;
    otherwise 2 ranked by word overlap. Compares normalized (punctuation-
    collapsed) strings so '! Help Me' still matches 'Help Me'."""
    q, t = _norm(query), _norm(title)
    if t == q:
        return (0, 0)
    ov = len(set(q.split()) & set(t.split()))
    if q in t:
        return (1, -ov)
    return (2, -ov)


def _search(query):
    # punctuation in the path (apostrophes, "!") 404s on their matcher
    q = re.sub(r"[^0-9A-Za-z ]+", " ", query)
    q = re.sub(r"\s+", " ", q).strip()
    soup = BeautifulSoup(_get(_BASE + "/video/search?search=" + requests.utils.quote(q)),
                         "html.parser")
    results, seen = [], set()
    for a in soup.select('a[href*="view_video.php"]'):
        img = a.select_one("img")
        title = _clean((img and (img.get("alt") or img.get("title"))) or "")
        if not title:
            continue
        href = a.get("href") or ""
        if href in seen:
            continue
        seen.add(href)
        results.append({"title": _clean(title), "url": _BASE + href})
    results.sort(key=lambda r: _match_score(query, r["title"]))
    return results


def scene(title="", url="", html="", **kwargs):
    return _scrape(url, title)


def movie(title="", url="", html="", **kwargs):
    return _scrape(url, title)


def scrape(title="", url="", html="", kind="", domain="", **kwargs):
    # kind is irrelevant here: a pornhub video page describes both shapes alike
    return _scrape(url, title)


def _scrape(url, title):
    if url:
        result = _scrape_page(url)
        if result:
            return result
    if title:
        results = _search(title)
        if results:
            return _scrape_page(results[0]["url"])
    return {}
