"""AdultEmpire scraper — Umbra-compatible.

Supports: scene/movie by-url, scene/movie by-name
Sites: adultempire.com, adultdvdempire.com
Handles age verification via cookie.
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

try:
    import cloudscraper
    _session = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
except ImportError:
    _session = requests.Session()

_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.adultdvdempire.com/",
})
for d in ["www.adultempire.com", ".adultempire.com",
          "www.adultdvdempire.com", ".adultdvdempire.com"]:
    _session.cookies.set("ageConfirmed", "true", domain=d, path="/")

# Phrases/words to strip from titles
_JUNK_RE = re.compile(
    r"\b(boxcover|box\s*cover|dvd\s*cover|cover|poster|front\s*cover|back\s*cover|"
    r"image|photo|picture|streaming\s*video\s*on\s*demand|on\s*demand|streaming|vod)\b",
    re.I,
)
# Title tag suffixes
_SUFFIX_RE = re.compile(
    r"\s*[|–\-:]+\s*(streaming\s*video\s*on\s*demand|adult\s*(dvd\s*)?empire|"
    r"on\s*demand|vod|adult\s*dvd|adultempire\.com|adultdvdempire\.com)\s*$",
    re.I,
)
# URL paths that are NOT movie/scene content
_NOT_CONTENT = re.compile(
    r"/(?:performer|category|genre|studio|series|list|tag|director|label|"
    r"blog|help|account|login|cart|checkout|faq|contact|terms|privacy|about)(?:/|$)",
    re.I,
)


def _clean(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _clean_title(t):
    if not t:
        return ""
    t = _SUFFIX_RE.sub("", t)
    t = _JUNK_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip(" -–|:,")
    return t


def _abs(base, url):
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return urljoin(base, url)


def _get(url):
    try:
        r = _session.get(url, timeout=20, allow_redirects=True)
    except Exception:
        return None, url
    if r.status_code != 200:
        return None, r.url
    soup = BeautifulSoup(r.text, "html.parser")
    body = soup.get_text(" ", strip=True).lower()
    if "confirm you are over 18" in body and len(body) < 2000:
        return None, r.url
    return soup, r.url


def _is_movie_url(href):
    """Check if URL looks like an actual movie/scene page."""
    if not re.search(r"/\d+/", href):
        return False
    if _NOT_CONTENT.search(href):
        return False
    # Must have a slug after the ID (like /12345/title-slug.html)
    if not re.search(r"/\d+/[^/]+", href):
        return False
    return True


def _title_from(soup):
    """Extract clean title from the page.

    Priority: h1 (direct text only) > og:title > <title> tag > other h1s.
    The h1 gives the cleanest title without year/studio suffixes.
    """
    # 1) h1 with class movie-page__heading__title — cleanest source
    for sel in [
        "h1.movie-page__heading__title",
        "div.title-rating-section h1",
        "div.clip-page__detail__title h1",
    ]:
        el = soup.select_one(sel)
        if el:
            # Get only direct text children (skip span with sale/promo text)
            raw = " ".join(el.find_all(string=True, recursive=False))
            t = _clean_title(_clean(raw))
            if t and len(t) > 2:
                return t

    # 2) og:title — strip year and studio suffix like "(2026) | Elegant Angel"
    og = soup.select_one("meta[property='og:title']")
    if og:
        t = _clean(og.get("content", ""))
        t = re.sub(r"\s*\(\d{4}\)\s*", " ", t)          # remove (2026)
        t = re.sub(r"\s*[|–-]+\s*[A-Z].*$", "", t)         # remove | Studio Name
        t = _clean_title(t)
        if t and len(t) > 2:
            return t

    # 3) <title> tag
    tag = soup.select_one("title")
    if tag:
        t = _clean(tag.get_text())
        t = re.sub(r"\s*\(\d{4}\)\s*", " ", t)
        t = re.sub(r"\s*[|–-]+\s*[A-Z].*$", "", t)
        t = _clean_title(t)
        if t and len(t) > 2:
            return t

    # 4) Fallback: any h1 not in nav/header
    for h1 in soup.find_all("h1"):
        parents = {p.name for p in h1.parents}
        if "nav" not in parents and "header" not in parents:
            raw = " ".join(h1.find_all(string=True, recursive=False))
            t = _clean_title(_clean(raw))
            if t and len(t) > 2 and "sale" not in t.lower():
                return t

    return ""


def _text_after(soup, label_text):
    for label in soup.find_all(["strong", "small", "span", "b", "th"]):
        if label_text.lower() in _clean(label.get_text()).lower():
            sib = label.next_sibling
            while sib:
                if isinstance(sib, str):
                    t = sib.strip().lstrip(":").strip()
                    if t:
                        return t
                elif hasattr(sib, "get_text"):
                    if sib.name == "a":
                        return _clean(sib.get_text())
                    t = _clean(sib.get_text())
                    if t and t != ":":
                        return t
                sib = sib.next_sibling
    return ""


def _scrape_page(url):
    soup, final_url = _get(url)
    if not soup:
        return None

    title = _title_from(soup)
    if not title:
        return None

    result = {"title": title, "url": final_url}

    # Year from <small>(2026)</small> near the h1 title
    year = ""
    h1 = soup.select_one("h1.movie-page__heading__title, div.title-rating-section h1")
    if h1:
        # Try direct sibling first
        small = h1.find_next_sibling("small")
        if not small:
            # Try inside the parent container
            parent = h1.parent
            if parent:
                small = parent.find("small")
        if small:
            m = re.search(r"(\d{4})", small.get_text())
            if m:
                year = m.group(1)
                result["year"] = year
    # Fallback: any <small> with a 4-digit year
    if not year:
        for sm in soup.find_all("small"):
            m = re.search(r"^\s*\(?\d{4}\)?\s*$", sm.get_text())
            if m:
                year = re.search(r"\d{4}", sm.get_text()).group()
                result["year"] = year
                break

    date = _text_after(soup, "Released") or _text_after(soup, "Release Date")
    if not date:
        meta = soup.select_one("meta[itemprop='datePublished']")
        if meta:
            date = (meta.get("content") or "")[:10]
    if date:
        result["date"] = date
    elif year:
        result["date"] = year

    for sel in ["div.synopsis-content", "[itemprop='description']", "div.synopsis"]:
        el = soup.select_one(sel)
        if el:
            desc = _clean(el.get_text(" "))
            desc = re.sub(r"Show (Less|More)$", "", desc).strip()
            if desc and len(desc) > 10:
                result["desc"] = desc
                break

    director_el = soup.select_one("a[label='Director']")
    if director_el:
        result["director"] = _clean(director_el.get_text())
    else:
        d = _text_after(soup, "Director")
        if d:
            result["director"] = d

    studio = ""
    studio_el = soup.select_one("a[label='Studio']")
    if studio_el:
        studio = _clean(studio_el.get_text())
    if not studio:
        studio = _text_after(soup, "Studio")
    if studio:
        result["studio"] = studio

    duration = _text_after(soup, "Length") or _text_after(soup, "Duration")
    if duration:
        result["durationMin"] = duration

    # Count scenes from <a name="scene_XXXXX"> anchors
    scene_anchors = soup.select("a[name^='scene_']")
    if scene_anchors:
        result["scenes"] = len(scene_anchors)

    poster = ""
    cover = soup.select_one("a#front-cover[data-href]")
    if cover:
        poster = _abs(final_url, cover.get("data-href", ""))
    if not poster:
        cover_img = soup.select_one("a#front-cover img")
        if cover_img:
            poster = _abs(final_url, cover_img.get("data-src") or cover_img.get("src", ""))
    if not poster:
        og = soup.select_one("meta[property='og:image']")
        if og:
            poster = og.get("content", "")
    if poster:
        result["posterF"] = poster

    back = soup.select_one("a#back-cover[href]")
    if back:
        result["posterB"] = _abs(final_url, back["href"])

    tags = []
    seen = set()
    for el in soup.select("a[label='Category']"):
        t = _clean(el.get_text())
        if t and t not in seen:
            seen.add(t)
            tags.append(t)
    if not tags:
        cat_section = soup.select_one("a[name='categories']")
        if cat_section:
            ul = cat_section.find_next("ul")
            if ul:
                for a in ul.select("a"):
                    t = _clean(a.get_text())
                    if t and t not in seen:
                        seen.add(t)
                        tags.append(t)
    if tags:
        result["categories"] = tags

    performers = []
    seen_p = set()
    for el in soup.select("a[label='Performer']"):
        name = _clean(el.get_text())
        if name and name not in seen_p:
            seen_p.add(name)
            performers.append(name)
    if performers:
        result["performers"] = performers

    return result


def _match_score(query_lower, query_words, title_lower, url):
    """Score how well a result matches the query. Lower = better match."""
    # Exact title match
    if title_lower == query_lower:
        return 0
    # Title contains full query
    if query_lower in title_lower:
        return 1
    # URL slug matches query (e.g., /12345/big-wet-asses-34.html)
    slug = re.search(r"/\d+/([^/?#]+)", url)
    if slug:
        slug_text = slug.group(1).replace("-", " ").replace(".html", "").lower()
        if slug_text == query_lower:
            return 2
        if query_lower in slug_text:
            return 3
        if slug_text in query_lower:
            return 4
    # Word overlap between query and title
    overlap = len(query_words & set(title_lower.split()))
    return 10 - overlap


def _search(query):
    """Search and return the best matching movie/scene."""
    query_lower = query.lower().strip()
    query_words = set(query_lower.split())

    for base in ["https://www.adultdvdempire.com", "https://www.adultempire.com"]:
        url = f"{base}/VOD/Search?q={quote(query)}"
        soup, _ = _get(url)
        if not soup:
            continue

        results = []
        seen_urls = set()
        for item in soup.select("a[href*='/']"):
            href = item.get("href", "")
            href = _abs(base, href)
            if href in seen_urls:
                continue
            if not _is_movie_url(href):
                continue
            seen_urls.add(href)

            img = item.select_one("img")
            title = ""
            image = ""
            if img:
                title = img.get("alt") or img.get("title") or ""
                image = img.get("data-src") or img.get("src") or ""
                ss = img.get("data-srcset") or img.get("srcset") or ""
                if ss:
                    parts = [p.strip().split(" ")[0] for p in ss.split(",") if p.strip()]
                    if parts:
                        image = parts[-1]
                image = _abs(base, image)

            title = _clean_title(title)
            if not title or len(title) < 3:
                continue

            r = {"title": title, "url": href}
            if image:
                r["posterF"] = image
                r["covers"] = [image]
            results.append(r)

        if not results:
            continue

        results.sort(key=lambda r: _match_score(
            query_lower, query_words, r["title"].lower(), r["url"]))
        return results

    return []


def _finalize(result):
    """Normalize keys for Umbra and make sure covers are present."""
    if not result:
        return {}
    if result.get("studio") and not result.get("studioName"):
        result["studioName"] = result["studio"]
    if result.get("categories") and not result.get("catNames"):
        result["catNames"] = result["categories"]
    covers = [u for u in (result.get("posterF"), result.get("posterB")) if u]
    if covers and not result.get("covers"):
        result["covers"] = covers
    return result


def scrape(title="", url="", html="", **kwargs):
    """Umbra scraper entry point."""
    if url:
        result = _scrape_page(url)
        if result:
            return _finalize(result)

    if title:
        search_results = _search(title)
        if search_results:
            first = search_results[0]
            if first.get("url"):
                detail = _scrape_page(first["url"])
                if detail:
                    return _finalize(detail)
            return _finalize(first)

    return {}
