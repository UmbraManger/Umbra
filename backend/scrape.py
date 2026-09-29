"""FaKNetwork standalone scraper — Obscura-compatible.

Supports: scene-by-url, scene-by-name
API: https://api.faknetworks.com/v1/
Sites: fakings, putalocura, fakkmag, hotkinkyjo, theassfactory, momsinteens, milfclub
       and any other FaKNetwork site
"""

import re
from html import unescape
from urllib.parse import quote
import requests

_scraper = requests.Session()
_scraper.headers.update({"User-Agent": "Mozilla/5.0 (Obscura)"})

TAG_CACHE: dict = {}

SITES = [
    "fakings", "putalocura", "fakkmag", "hotkinkyjo",
    "theassfactory", "momsinteens", "milfclub",
]


def _clean(text):
    return re.sub(r"<[^>]+>", "", unescape(text)) if text else ""


def _tag_map(site, lang="en"):
    key = f"{site}:{lang}"
    if key in TAG_CACHE:
        return TAG_CACHE[key]
    url = f"https://api.faknetworks.com/v1/categories?product={site}&lang={lang}&page=1&take=1000"
    r = _scraper.get(url, timeout=15)
    if r.status_code != 200:
        TAG_CACHE[key] = {}
        return {}
    mapping = {str(c["id"]): c["title"] for c in r.json().get("results", [])}
    TAG_CACHE[key] = mapping
    return mapping


def _to_scene(data, lang="en"):
    site_name = data.get("product", "")
    tags_map = _tag_map(site_name, lang)

    performers = []
    for p in data.get("performers", []):
        perf = {"name": p["name"]}
        imgs = []
        if pp := p.get("profilePhoto"):
            imgs.append(f"https://almacen.fakings.com/almacen/actrices/{pp}")
        if imgs:
            perf["images"] = imgs
        perf_urls = []
        if sn := p.get("product"):
            perf_urls.append(f"https://{sn}.com/actrices-porno/{p.get('slug', '')}")
        if lf := p.get("loverfansUrl"):
            perf_urls.append(lf)
        if perf_urls:
            perf["urls"] = perf_urls
        performers.append(perf)

    tags = []
    for c in data.get("categories", []):
        cid = str(c.get("id", ""))
        tags.append({"name": tags_map.get(cid, c.get("title", ""))})

    scene = {
        "title": data.get("title", ""),
        "date": data.get("date", ""),
        "code": data.get("filename", ""),
        "details": _clean(data.get("description", "")),
        "tags": tags,
        "performers": performers,
    }

    slug = data.get("slug", "")
    scene["urls"] = [f"https://{site_name}.com/{lang}/video/{slug}"]

    if hp := data.get("horizontalProfile"):
        scene["image"] = f"https://player.faknetworks.com/almacen/videos/listado_horizontal_{hp}"

    serie = data.get("serie")
    if serie and isinstance(serie, dict):
        serie_name = serie.get("title", serie.get("name", ""))
        serie_slug = serie.get("slug", "")
        studio = {"name": serie_name}
        parent_name = site_name.replace(".com", "").title()
        studio["parent"] = {"name": parent_name}
        if serie_slug:
            studio["urls"] = [f"https://{site_name}.com/{lang}/serie/{serie_slug}"]
        scene["studio"] = studio
    else:
        scene["studio"] = {"name": site_name.replace(".com", "").title()}

    return scene


def _scene_by_url(url):
    pattern = r".+?(?:/(?P<lang>\w{2}))?/video/(?P<slug>[-\w]+)"
    m = re.search(pattern, url)
    if not m:
        return None
    lang = m.group("lang") or "en"
    slug = m.group("slug")
    api = f"https://api.faknetworks.com/v1/public/videos/{slug}?lang={lang}"
    r = _scraper.get(api, timeout=15)
    if r.status_code != 200:
        return None
    return _to_scene(r.json(), lang)


def _scene_search(query, site="fakings", lang="en"):
    api = f"https://api.faknetworks.com/v1/search?query={quote(query)}&product={site}&lang={lang}&limit=10"
    r = _scraper.get(api, timeout=15)
    if r.status_code != 200:
        return []
    data = r.json()
    results = []
    for s in data.get("videos", []):
        scene = _to_scene(s, lang)
        if scene:
            results.append(scene)
    return results


def scrape(title="", url="", html="", domain="", **kwargs):
    """Obscura scraper entry point."""
    if url:
        result = _scene_by_url(url)
        if result:
            return result
    if title:
        # Try to detect site from domain, fall back to fakings
        site = "fakings"
        if domain:
            for s in SITES:
                if s in domain:
                    site = s
                    break
        results = _scene_search(title, site=site)
        if results:
            return results[0]
    return {}
