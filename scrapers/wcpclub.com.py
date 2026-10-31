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
for d in ["wcpclub.com", ".wcpclub.com",
          "adultdvdempire.com", ".adultdvdempire.com"]:
    _session.cookies.set("ageConfirmed", "true", domain=d, path="/")

_BASE = "https://www.wcpclub.com"
_ADE_SEARCH = "https://www.adultdvdempire.com/VOD/Search?q="


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


def _looks_names(text):
    """True if a '-' head looks like a performer list ('Anna Claire Clouds, Angela White')."""
    parts = [p.strip() for p in text.split(",")]
    return (bool(text.strip()) and len(parts) <= 5 and
            all(p and not re.search(r"\d", p) and len(p.split()) <= 5 and
                re.match(r"^[A-Za-z .'\u2019-]+$", p) for p in parts))


def _split_perf_title(query):
    """'Performers, Performers - Title' naming: -> (performers, title)."""
    parts = re.split(r"\s+[-\u2013\u2014]\s+", (query or "").strip())
    if len(parts) >= 2 and _looks_names(parts[0]):
        return [p.strip() for p in parts[0].split(",") if p.strip()], " - ".join(parts[1:])
    return [], (query or "").strip()


def _member_scenes(query):
    """Storefront scene search (/Scene/MemberSearch) by performer name, title, or
    both. Server-rendered cards link to LIVE /<id>/<slug>.html scene pages."""
    try:
        html = _get(_BASE + "/Scene/MemberSearch?q=" + requests.utils.quote(query))
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out, seen = {}, set()
    for a in soup.select('a[href$=".html"]'):
        href = a.get("href") or ""
        if not re.match(r"^/\d+/[^/]+\.html$", href) or href in seen:
            continue
        slug = _slug_of(href)
        if not slug or slug in ("category", "pornstars"):
            continue
        seen.add(href)
        img = a.select_one("img")
        title = _clean((img and (img.get("alt") or img.get("title"))) or slug.replace("-", " "))
        out[slug] = {"title": _clean(re.sub(r"\s+image$", "", title, flags=re.I)),
                     "url": _BASE + href.split("#")[0], "slug": slug}
    return list(out.values())


def _ade_products(q):
    """Master ADE search: server-rendered with LIVE canonical /<id>/<slug>.html
    links (movie pages the scene search may miss)."""
    try:
        r = _session.get(_ADE_SEARCH + requests.utils.quote(q),
                         headers={"Referer": "https://www.adultdvdempire.com/"},
                         timeout=25)
        r.raise_for_status()
    except Exception:
        return []
    out, seen = [], set()
    for m in re.finditer(r'href="(/\d+/[^"]+\.html)"', r.text):
        href = m.group(1)
        if href in seen:
            continue
        seen.add(href)
        slug = _slug_of(href)
        if not slug or slug in ("category", "pornstars"):
            continue
        out.append({"title": _clean(slug.replace("-", " ")),
                    "url": "https://www.adultdvdempire.com" + href.split("#")[0],
                    "slug": slug})
    return out


def _search_page(query):
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
    return out


def _search(query):
    """'Performers, Performers - Title' naming: query the storefront scene search
    with names + title, then title, then each name; rank by the title part."""
    performers_named, title_q = _split_perf_title(query)
    rank_q = title_q or query
    # ponytail: first page of each result set only; the combined performer+title
    # query narrows hard enough that the needed scene lands on page 1.
    cands, seen = [], set()

    def add(items):
        for p in items:
            if p["url"] in seen:
                continue
            seen.add(p["url"])
            cands.append(p)

    if performers_named:
        add(_member_scenes(" ".join(performers_named) + " " + title_q))
    add(_member_scenes(rank_q))
    for name in performers_named:
        add(_member_scenes(name))
    if not cands:  # master catalog has movie pages the scene search may miss
        add(_ade_products(rank_q))
    if not cands:  # last resort: the storefront product search page
        add(_search_page(query))
    cands.sort(key=lambda r: _match_score(rank_q, r["slug"]))
    return cands


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
    out = {"url": ""}
    og = soup.select_one('meta[property="og:image"]')
    # Storefront (h1.description) and ADE master (movie-page heading) layouts
    title = ""
    for el in (soup.select_one("h1.description"),
               soup.select_one("h1.movie-page__heading__title"),
               soup.select_one('meta[property="og:title"]')):
        if el is None:
            continue
        title = _clean(el.get("content") if el.name == "meta" else el.get_text())
        if title:
            break
    if title:
        # storefront: "... streaming video Elegant Angel"; master: "Title (2026) | Studio"
        title = _clean(re.sub(r"\s*\(\d{4}\)\s*", " ", title))
        title = _clean(re.sub(r"\s+[|\u2013-]+\s+[A-Z].*$", "", title))
        title = _clean(re.sub(r"\s+(?:streaming|porn)\s+(?:video|videos).*$", "", title,
                              flags=re.I))
    if not title:
        return {}
    out["title"] = out["originaltitle"] = title
    cover = soup.select_one("a#front-cover[data-href]")
    cover_url = (cover.get("data-href") if cover else (og.get("content") if og else None))
    if cover_url:
        out["posterF"] = cover_url
        out["covers"] = [cover_url]
    back = soup.select_one("a#back-cover[href]")
    if back and back.get("href"):
        out["posterB"] = back.get("href")
    performers, seen_p = [], set()
    for e in soup.select("a[data-Label='Performer'], a[label='Performer']"):
        n = e.select_one(".performer-name")
        name = _clean((n or e).get_text())
        if name and name.lower() not in seen_p:
            seen_p.add(name.lower())
            performers.append(name)
    if performers:
        out["performers"] = performers
    tags = []
    for e in soup.select("a[data-Label='Tag'], a[label='Category']"):
        t = _clean(e.get_text())
        if t and t.lower() not in (x.lower() for x in tags):
            tags.append(t)
    if not tags:
        catsec = soup.select_one("a[name='categories']")
        if catsec:
            ul = catsec.find_next("ul")
            if ul:
                for a in ul.select("a"):
                    t = _clean(a.get_text())
                    if t and t.lower() not in (x.lower() for x in tags):
                        tags.append(t)
    if tags:
        out["categories"] = out["catNames"] = tags
    studio = soup.select_one(".studio") or soup.select_one("a[label='Studio']")
    if studio:
        name = _clean(_clean(studio.get_text()).replace("Studio:", ""))
        if name:
            out["studioName"] = name
    director = soup.select_one(".director") or soup.select_one("a[label='Director']")
    if director:
        name = _clean(_clean(director.get_text()).replace("Director:", ""))
        if name:
            out["director"] = name
    raw = ""
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
    if ("date" not in out or "durationMin" not in out):
        raw = _clean(soup.get_text())
    if "date" not in out:
        meta = soup.select_one("meta[itemprop='datePublished']")
        if meta and re.match(r"^\d{4}-\d{2}-\d{2}", (meta.get("content") or "")):
            out["date"] = meta.get("content")[:10]
        else:
            parsed = _date_min_max(raw)
            if parsed:
                out["date"] = parsed
    if "durationMin" not in out:
        mins = _duration_min(raw)
        if mins:
            out["durationMin"] = mins
    syn = (soup.select_one(".synopsis")
           or soup.select_one("div.synopsis-content")
           or soup.select_one("[itemprop='description']"))
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
