"""West Coast Productions scraper (wcpclub.com) - Umbra-compatible.
Adult-Empire-platform storefront, same layout as the Elegant Angel client.

Supports: scene/movie by-url, scene/movie by-name
Sites: wcpclub.com

Age gate needs the ageConfirmed cookie. /en/search?q= is server-rendered
(/shop/<id>/<slug>.html product links); detail pages carry the ADE layout:
data-Label="Performer" cards, .release-date (Released/Length), .studio,
.director, a[data-Label="Tag"], .synopsis, og:image cover.
"""

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})
for d in ["wcpclub.com", ".wcpclub.com"]:
    _session.cookies.set("ageConfirmed", "true", domain=d, path="/")

_BASE = "https://www.wcpclub.com"


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _slug_of(href):
    m = re.search(r"/\d+/(?:west-coast-productions-)?([^/]+)\.html", (href or ""), re.I)
    return m.group(1) if m else ""


def _norm(text):
    return re.sub(r"[^0-9a-z]+", " ", text.lower()).strip()


def _match_score(query, slug):
    q = _norm(query).replace(" ", "-")
    if slug == q:
        return (0, 0)
    if q in slug or slug.replace("-", " ") in _norm(query):
        ov = -len(set(_norm(query).split()) & set(slug.split("-")))
        return (1, ov, len(slug))
    ov = -len(set(_norm(query).split()) & set(slug.split("-")))
    return (2, ov, len(slug))


def _search(query):
    soup = BeautifulSoup(_get(_BASE + "/en/search?q=" + requests.utils.quote(query)),
                         "html.parser")
    results = {}
    for a in soup.select('a[href*=".html"]'):
        href = a.get("href") or ""
        if not re.match(r"^/(?:shop/)?\d+/", href, re.I):
            continue
        slug = _slug_of(href)
        if not slug:
            continue
        rec = results.setdefault(slug, {"title": "", "url": _BASE + href.split("#")[0], "slug": slug})
        if rec["title"]:
            continue
        img = a.select_one("img")
        title = _clean((img and (img.get("alt") or img.get("title"))) or a.get_text())
        # the slug IS the normalized product title; card text can be UI junk
        if not title or title.lower() == "watch now" or title.lower().endswith(" image"):
            continue
        results[slug] = rec | {"title": title}
    out = list(results.values())
    for rec in out:
        if not rec["title"]:
            rec["title"] = _clean(re.sub(r"^west coast productions ", "", rec["slug"].replace("-", " "), flags=re.I))
            rec["title"] = _clean(re.sub(r"\s+streaming(?:\s+(?:scene|porn|video|movie))?\s+(?:video|videos|movie|movies)?\s*$", "", rec["title"], flags=re.I))
    out.sort(key=lambda r: _match_score(query, r["slug"]))
    return out


def _get(url):
    r = _session.get(url, timeout=25)
    r.raise_for_status()
    return r.text


def _date_min_max(raw):
    m = re.search(r"Released:\s*([A-Za-z]{3})\s+(\d{1,2}),?\s+(\d{4})", raw)
    if not m:
        return None
    try:
        return datetime.strptime(
            "{} {} {}".format(m.group(1), m.group(2), m.group(3)),
            "%b %d %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _duration_min(raw):
    m = re.search(r"Length:\s*(?:(\d+)\s*hrs?)?.*?(\d+)\s*mins?", raw, re.I)
    if m:
        h = int(m.group(1)) if m.group(1) else 0
        mn = int(m.group(2))
    else:
        m = re.search(r"Length:\s*(\d+)\s*min", raw, re.I)
        if not m:
            return None
        h, mn = 0, int(m.group(1))
    return h * 60 + mn


def _scrape_soup(soup):
    og = soup.select_one('meta[property="og:image"]')
    title_el = (soup.select_one("h1.description") or soup.select_one('meta[property="og:title"]'))
    out = {"url": ""}
    title = _clean(title_el.get("content") if (title_el and title_el.has_attr("content")) else title_el.get_text())
    title = _clean(re.sub(r"\s+(?:streaming|porn)\s+(?:video|videos).*$", "", title, flags=re.I))
    if title:
        out["title"] = out["originaltitle"] = title
    if og and og.get("content"):
        out["posterF"] = og.get("content")
        out["covers"] = [og.get("content")]
    performers, seen_p = [], set()
    for e in soup.select("a[data-Label='Performer']"):
        n = e.select_one(".performer-name")
        name = _clean((n or e).get_text())
        if name and name.lower() not in seen_p:
            seen_p.add(name.lower())
            performers.append(name)
    if performers:
        out["performers"] = performers
    tags = []
    for e in soup.select("a[data-Label='Tag']"):
        t = _clean(e.get_text())
        if t and t.lower() not in (x.lower() for x in tags):
            tags.append(t)
    if tags:
        out["categories"] = out["catNames"] = tags
    studio = soup.select_one(".studio")
    if studio:
        name = _clean(_clean(studio.get_text()).replace("Studio:", ""))
        if name:
            out["studioName"] = name
    director = soup.select_one(".director")
    if director:
        name = _clean(_clean(director.get_text()).replace("Director:", ""))
        if name:
            out["director"] = name
    for rd in soup.select(".release-date"):
        text = _clean(rd.get_text())
        if "Released:" in text and "date" not in out:
            parsed = _date_min_max(text)
            if parsed:
                out["date"] = parsed
        if "Length:" in text and "durationMin" not in out:
            mins = _duration_min(text)
            if mins:
                out["durationMin"] = mins
    syn = soup.select_one(".synopsis")
    if syn:
        desc = _clean(syn.get_text())
        if desc:
            out["description"] = desc
    return out


def _scrape_page(url):
    return _scrape_soup(BeautifulSoup(_get(url), "html.parser"))


def _scrape(url, title):
    if url:
        result = _scrape_page(url)
        if result.get("title"):
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
