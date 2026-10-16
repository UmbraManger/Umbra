"""DarkkoTV scraper — Umbra-compatible.

Supports: scene-by-url, scene-by-name
Sites: darkkotv.com
"""

import json
import re
import requests
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

try:
    import cloudscraper
    _session = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
except ImportError:
    _session = requests.Session()

_session.cookies.set("warn", "true", domain="darkkotv.com", path="/")
_session.headers.update({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
})

try:
    _session.get("https://darkkotv.com/", timeout=(10, 30))
except Exception:
    pass

BASE = "https://darkkotv.com"


def _fetch(url):
    for attempt in range(3):
        try:
            r = _session.get(url, timeout=(15, 30))
            r.raise_for_status()
            return r
        except Exception:
            if attempt == 2:
                return None
            import time
            time.sleep(2 * (attempt + 1))
    return None


def _parse_date(s):
    if not s:
        return ""
    s = s.strip()
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def _parse_duration(text):
    """Parse duration from text like '45 min', '1h 23m', '01:23:45', etc."""
    if not text:
        return 0
    text = text.strip().lower()
    # HH:MM:SS or MM:SS
    m = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', text)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2))
        s = int(m.group(3)) if m.group(3) else 0
        if m.group(3):  # HH:MM:SS
            return h * 60 + mi
        else:  # MM:SS
            return h * 60 + mi
    # "Xh Ym" or "X hr Y min"
    m = re.search(r'(\d+)\s*h(?:our)?s?\s*(\d+)\s*m(?:in)?', text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    # "X min" or "Xm"
    m = re.search(r'(\d+)\s*m(?:in)?', text)
    if m:
        return int(m.group(1))
    # Just a number (assume minutes)
    m = re.search(r'(\d+)', text)
    if m:
        val = int(m.group(1))
        if val > 5:  # probably minutes
            return val
    return 0


def _title_to_slug(title):
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _scrape_scene(url):
    r = _fetch(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    # Title
    title_el = soup.select_one("h4.text_light")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        return None

    result = {"title": title, "url": url, "studio": "Darkko TV"}

    # Description
    content = soup.select_one("div.vidImidWrap")
    if content:
        desc_el = content.select_one("div.vidImgContent.text_light")
        if desc_el:
            desc = " ".join(p.get_text(strip=True) for p in desc_el.find_all("p"))
            if desc:
                result["desc"] = desc

    # Date — find MM-DD-YYYY pattern in content area
    if content:
        text = content.get_text(" ", strip=True)
        dates = re.findall(r"(\d{2}-\d{2}-\d{4})", text)
        if dates:
            result["date"] = _parse_date(dates[0])

    # Cover/thumbnail image
    image = None
    # Try og:image first
    og = soup.select_one("meta[property='og:image']")
    if og:
        image = og.get("content", "")
    # Fallback: look for main video/player poster
    if not image:
        poster = soup.select_one("video[poster], .video-player img, .player img")
        if poster:
            image = poster.get("poster") or poster.get("src", "")
    if not image:
        img = soup.select_one("div.vidImidWrap img")
        if img:
            image = img.get("src", "")
    if image:
        if image.startswith("/"):
            image = BASE + image
        result["poster_f"] = image
        result["thumbnail"] = image
        result["cardThumbnail"] = image
        result["cover_a"] = image

    # Duration — search in multiple places
    duration_min = 0
    # Try JSON-LD
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            d = json.loads(script.get_text())
            if isinstance(d, dict):
                dur = d.get("duration") or d.get("runtime")
                if dur:
                    duration_min = _parse_duration(dur)
                    break
        except (json.JSONDecodeError, TypeError):
            continue
    # Try meta tags
    if not duration_min:
        for meta in soup.select("meta[property='video:duration'], meta[name='duration']"):
            val = meta.get("content", "")
            if val:
                duration_min = _parse_duration(val)
                break
    # Try page text — look for duration patterns near icons/labels
    if not duration_min and content:
        # Look for "duration" label or clock icon
        for el in content.select("i[class*='fa-clock'], i[class*='fa-time'], span.duration, div.duration"):
            parent = el.parent
            if parent:
                dur = _parse_duration(parent.get_text())
                if dur:
                    duration_min = dur
                    break
    # Fallback: search full text for common duration patterns
    if not duration_min:
        full_text = soup.get_text(" ", strip=True)
        # Look for patterns like "45 min" or "1h 23m"
        m = re.search(r'(\d{1,3})\s*(?:min|minutes?)\b', full_text, re.I)
        if m:
            duration_min = int(m.group(1))
        else:
            m = re.search(r'(\d{1,2})h\s*(\d{1,2})m', full_text, re.I)
            if m:
                duration_min = int(m.group(1)) * 60 + int(m.group(2))
    if duration_min:
        result["duration_min"] = duration_min

    # Tags
    tags = [a.get_text(strip=True) for a in soup.select("div.blogTags ul li a")]
    if tags:
        result["categories"] = tags

    # Performers
    performers = []
    seen = set()
    if content:
        for i_tag in content.select("i[class*='fa-user']"):
            parent = i_tag.parent
            if parent:
                for a in parent.select("a[href*='/models/']"):
                    name = a.get_text(strip=True)
                    if name and name not in seen:
                        seen.add(name)
                        performers.append(name)
    title_el = soup.select_one("h4.text_light")
    if title_el:
        current = title_el
        for _ in range(10):
            current = current.find_next_sibling()
            if not current:
                break
            if hasattr(current, "select"):
                for a in current.select("a[href*='/models/']"):
                    name = a.get_text(strip=True)
                    if name and name not in seen:
                        seen.add(name)
                        performers.append(name)
                if performers:
                    break
    if performers:
        result["performers"] = performers

    return result


def _search_scenes(query):
    url = f"{BASE}/search?query={requests.utils.quote(query)}"
    r = _fetch(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    seen = set()
    for a in soup.select("a[href*='/scenes/']"):
        href = a.get("href", "")
        if not href or href in seen:
            continue
        seen.add(href)
        full_url = urljoin(BASE, href)
        title = a.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        results.append({"title": title, "url": full_url})
    return results[:15]


def scrape(title="", url="", html="", **kwargs):
    if url:
        result = _scrape_scene(url)
        if result:
            return result

    if title:
        slug = _title_to_slug(title)
        direct_url = f"{BASE}/scenes/{slug}_vids.html"
        result = _scrape_scene(direct_url)
        if result:
            return result

        results = _search_scenes(title)
        if results:
            detail = _scrape_scene(results[0]["url"])
            if detail:
                return detail
            return results[0]

    return {}
