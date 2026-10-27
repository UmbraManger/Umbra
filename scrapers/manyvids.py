"""ManyVids scraper - Umbra-compatible.

Supports: scene/movie by-url (Video/<id>/<slug>), scene/movie by-name
Sites: manyvids.com

Search is /Vids?keywords=...; result cards carry aria-label "Title by
Creator on ManyVids." Detail pages expose a JSON-LD VideoObject with
title, description, duration, upload date, thumbnail and the profile
as creator (a ManyVids video is authored by its performer's store, so
that name fills both performers and studio), plus the /Vids/<slug>
tag row. ponytail ceiling: ManyVids' full search is client-side (SPA)
and the server wall only front-loads a few rows, so by-name finds only
what that wall shows - upgrade path is the SPA's session API. By-URL
always returns the complete record.
"""

import json
import re

import requests
from bs4 import BeautifulSoup

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})

_BASE = "https://www.manyvids.com"


def _clean(text):
    return re.sub(r"\s+", " ", text).strip() if text else ""


def _duration_min(raw):
    m = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(raw or ""), re.I)
    if not m or not any(m.groups()):
        return None
    h, mn, s = (int(g) if g else 0 for g in m.groups())
    return h * 60 + mn + round(s / 60)


def _get(url):
    r = _session.get(url, timeout=25)
    r.raise_for_status()
    return r.text


def _json_ld(soup):
    for el in soup.select('script[type="application/ld+json"]'):
        try:
            d = json.loads(el.get_text())
        except Exception:
            continue
        if isinstance(d, dict) and d.get("@type") == "VideoObject":
            return d
    return {}


def _tags(soup):
    """Detail-page tag row: <a ... data-event-category="Engagements"
    data-event-label="BigAss" href="/Vids/bigass">#BigAss</a>. Select by the
    stable data attributes, not the hashed CSS class."""
    tags, seen = [], set()
    for el in soup.select("a[data-event-category='Engagements']"):
        href = el.get("href") or ""
        if not href.startswith("/Vids/"):
            continue
        t = _clean(el.get("data-event-label") or el.get_text()).lstrip("#")
        if not t:
            continue
        t = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)  # BigAss -> Big Ass
        # the slug must agree with the label; drops UI chips like #GUEST
        if t.lower().replace(" ", "") != href[len("/Vids/"):].rstrip("/").lower():
            continue
        if t.lower() not in seen:
            seen.add(t.lower())
            tags.append(t)
    return tags


def _norm(text):
    return re.sub(r"[^0-9a-z]+", " ", text.lower()).strip()


def _match_score(query, title):
    q, t = _norm(query), _norm(title)
    if t == q:
        return (0, 0)
    ov = len(set(q.split()) & set(t.split()))
    if q in t:
        return (1, -ov)
    return (2, -ov)


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
    desc = ld.get("description")
    if desc:
        out["description"] = _clean(desc)
    poster = None
    og = soup.select_one('meta[property="og:image"]')
    if og:
        poster = og.get("content")
    if not poster:
        thumb = ld.get("thumbnailUrl")
        if isinstance(thumb, list):
            thumb = thumb[0] if thumb else None
        poster = thumb
    if poster:
        out["posterF"] = poster
        out["covers"] = [poster]
    cats = _tags(soup)
    if cats:
        out["categories"] = out["catNames"] = cats
    creator = ld.get("creator")
    if isinstance(creator, list):
        creator = creator[0] if creator else None
    name = (creator.get("name") if isinstance(creator, dict) else creator) or ""
    name = _clean(str(name))
    if name:  # the store's owner is the performer on MV
        out["studioName"] = name
        out["performers"] = [name]
    if url:
        out["url"] = url
    return out


def _search(query):
    soup = BeautifulSoup(_get(_BASE + "/Vids?keywords=" + requests.utils.quote(query)),
                         "html.parser")
    return _search_cards(soup, query)


def _search_cards(soup, query=None):
    results, seen = [], set()
    for a in soup.select('a[href^="/Video/"]'):
        href = a.get("href") or ""
        m = re.match(r"^/Video/\d+/[^/]+", href)
        if not m or href in seen:
            continue
        seen.add(href)
        label = _clean(a.get("aria-label") or "")
        # "Title by Creator on ManyVids."
        tm = re.match(r"(.+) by (.+?) on ManyVids\.?$", label)
        title = _clean(tm.group(1)) if tm else ""
        if not title:
            # product page stores no title on the card anchor here
            img = a.select_one("img")
            title = _clean((img and (img.get("alt") or img.get("title"))) or "")
        if title:
            results.append({"title": title, "url": _BASE + m.group(0)})
    if query:
        results.sort(key=lambda r: _match_score(query, r["title"]))
    return results


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


def scene(title="", url="", html="", **kwargs):
    return _scrape(url, title)


def movie(title="", url="", html="", **kwargs):
    return _scrape(url, title)


def scrape(title="", url="", html="", kind="", domain="", **kwargs):
    return _scrape(url, title)
