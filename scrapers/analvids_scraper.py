#!/usr/bin/env python3
"""AnalVids / PissVids scraper v2.

Root cause of "only cover is returned":
  scrape(title=...) returned the *search hit* (search_scenes entry) directly.
  Search entries only contain {title, url, site, thumbnail/image/cover_*} —
  the scene page is never parsed, so date/details/performers/tags/studio are
  always missing. v2 always finishes with scrape_scene() for full details.

Other fixes:
  - `html` argument is now honored: if the backend passes a saved page, it is
    parsed with the same extraction logic (v1 ignored it entirely).
  - Extraction factored into _extract_scene() so page fetch and html-string
    paths share one code path.
  - Title match scoring (difflib) for search-by-title instead of results[0].
  - Thumbnail enrichment in search_scenes limited to top 5 hits (v1 fetched up
    to 15 full pages per search) and failures no longer silent-swallowed.
  - _fetch checks Content-Type so Cloudflare/HTML interstitials fail loudly.
"""
import json
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import quote_plus, urljoin

import cloudscraper
from lxml import html as lxml_html

scraper = cloudscraper.create_scraper()
BASE_URL = 'https://www.analvids.com'
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 30


# ---------------------------------------------------------------- helpers
def _fetch(url, attempts=3):
    last_err = None
    for i in range(attempts):
        try:
            resp = scraper.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            resp.raise_for_status()
            ctype = resp.headers.get('Content-Type', '')
            # scene pages are HTML; autocomplete API is JSON — just reject
            # obvious bot-challenge / empty payloads here
            if 'text/html' in ctype and 'watch' not in resp.text and len(resp.text) < 2000:
                raise ValueError('got a short HTML page (bot challenge?)')
            return resp
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                import time
                time.sleep(1.5 * (i + 1))
    raise last_err


def _format_display_date(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        return f"{months[dt.month - 1]} {dt.day}, {dt.year}"
    except Exception:
        return iso_str


def _format_iso(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ('%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str


def _domain_studio(url):
    return 'PissVids' if 'pissvids' in str(url) else 'AnalVids'


def _title_score(a, b):
    norm = lambda s: re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


# ---------------------------------------------------------------- extract
def _extract_scene(tree, url):
    """All scene fields from a parsed page. Verified against live markup:
       title      -> <title> minus '- (Anal|Piss)Vids'
       date       -> <i class="bi-calendar3">  (' 2026-09-22')
       details    -> div.text-mob-more
       performers -> links inside h1.watch__title  (/model/<id>/<slug>)
       studio     -> div.genres-list a[href*="/studios/"]
       tags       -> div.genres-list a[href*="/genre/"]
       image      -> video[data-poster]   (fallback: og:image)
    """
    title = None
    t = tree.xpath('//title/text()')
    if t:
        title = re.sub(r'\s*-\s*(Piss|Anal)Vids\s*$', '', t[0].strip()).strip() or None

    iso_date = _format_iso((tree.xpath('//i[contains(@class, "bi-calendar3")]/text()') or [''])[0].strip() or None)
    display_date = _format_display_date(iso_date) if iso_date else None

    parts = tree.xpath('//div[contains(@class, "text-mob-more")]//text()')
    details = ' '.join(p.strip() for p in parts if p.strip()) or None

    code = None
    if title:
        m = re.search(r'\b([A-Z]{2,4}\d{3,5})\b', title)
        if m:
            code = m.group(1)

    performers = []
    for a in tree.xpath('//h1[contains(@class, "watch__title")]//a'):
        name = a.text_content().strip()
        if name:
            p = {'name': name}
            href = a.get('href', '')
            if href:
                p['url'] = urljoin(BASE_URL, href)
            performers.append(p)

    studio = None
    studio_links = tree.xpath('//div[contains(@class, "genres-list")]//a[contains(@href, "/studios/")]')
    if studio_links:
        studio = studio_links[0].text_content().strip()
    if not studio:
        studio = _domain_studio(url)

    tags = []
    for a in tree.xpath('//div[contains(@class, "genres-list")]//a[contains(@href, "/genre/")]'):
        t_ = a.text_content().strip()
        if t_:
            tags.append(t_)

    image = None
    img = tree.xpath('//video/@data-poster')
    if img:
        image = img[0]
    else:
        og = tree.xpath('//meta[@property="og:image"]/@content')
        if og:
            image = og[0]

    return {
        'kind': 'scene',
        'title': title,
        'date': iso_date,
        'releaseDate': display_date,
        'details': details,
        'code': code,
        'studio': studio,
        'performers': performers,
        'tags': tags,
        'image': image,
        'thumbnail': image,
        'cardThumbnail': image,
        'cover_a': image,
        'cover_b': image,
        'url': url,
    }


# ---------------------------------------------------------------- scene
def scrape_scene(url, html=None):
    """Scrape a scene page (fetched, or from provided html string)."""
    url = urljoin(BASE_URL, url)
    if html:
        tree = lxml_html.fromstring(html)
    else:
        tree = lxml_html.fromstring(_fetch(url).text)
    return _extract_scene(tree, url)


# ---------------------------------------------------------------- search
def search_scenes(query, enrich_top=5):
    """Autocomplete API search. Thumbnails enriched from top result pages only."""
    data = _fetch(f'{BASE_URL}/api/autocomplete/search?q={quote_plus(query)}').json()
    results = []
    for item in data.get('terms', []):
        if item.get('type') in ('scene', 'video'):
            scene_url = urljoin(BASE_URL, item.get('url', ''))
            entry = {
                'kind': 'scene',
                'title': item.get('name', ''),
                'url': scene_url,
                'site': _domain_studio(scene_url).lower(),
            }
            results.append(entry)

    for entry in results[:enrich_top]:
        try:
            tree = lxml_html.fromstring(_fetch(entry['url']).text)
            poster = tree.xpath('//video/@data-poster') or tree.xpath('//meta[@property="og:image"]/@content')
            if poster:
                for k in ('image', 'thumbnail', 'cardThumbnail', 'cover_a', 'cover_b'):
                    entry[k] = poster[0]
        except Exception as e:
            entry['thumbnailError'] = str(e)
    return results[:15] if results else []


def search_performers(query):
    data = _fetch(f'{BASE_URL}/api/autocomplete/search?q={quote_plus(query)}').json()
    results = []
    for item in data.get('terms', []):
        if item.get('type') in ('model', 'performer', 'pornstar', 'actor'):
            model_url = item.get('url', '')
            if model_url:
                model_url = urljoin(BASE_URL, model_url)
            results.append({'kind': 'performer', 'name': item.get('name', ''), 'url': model_url})
    return results


# ---------------------------------------------------------------- performer
def scrape_performer(url, html=None):
    url = urljoin(BASE_URL, url)
    tree = lxml_html.fromstring(html) if html else lxml_html.fromstring(_fetch(url).text)

    name = None
    h1 = tree.xpath('//h1//text()')
    if h1:
        name = h1[0].strip()

    country = None
    c = tree.xpath('//a[contains(@href, "nationality")]/text()')
    if c:
        country = c[0].strip()

    image = None
    img = tree.xpath('//div[contains(@class, "model__left")]//img/@src')
    if img:
        image = img[0]

    return {
        'kind': 'performer',
        'name': name,
        'country': country,
        'photo': image,
        'image': image,
        'thumbnail': image,
        'cardThumbnail': image,
        'url': url,
    }


# ---------------------------------------------------------------- entry
def scrape(title="", url="", html="", kind="", **kwargs):
    """Unified entry point called by the backend."""
    # 1) explicit URL
    if url:
        if '/model/' in url:
            return scrape_performer(url, html=html or None)
        return scrape_scene(url, html=html or None)

    # 2) provided page html (no url): parse it directly
    if html:
        tree = lxml_html.fromstring(html)
        return _extract_scene(tree, '')

    # 3) search by title/name -> FULL scene details, not the thin search hit
    query = (title or "").strip()
    if not query:
        return {'error': 'need url, html or title'}

    if kind == 'performer':
        hits = search_performers(query)
        return scrape_performer(hits[0]['url']) if hits else {'notFound': True, 'query': query}

    results = search_scenes(query)
    if not results:
        return {'notFound': True, 'query': query}

    best = max(results, key=lambda r: _title_score(query, r['title']))
    score = _title_score(query, best['title'])
    if score < 0.5:
        return {'notFound': True, 'query': query,
                'candidates': [{'title': r['title'], 'url': r['url']} for r in results[:5]]}

    # full details from the scene page
    try:
        detail = scrape_scene(best['url'])
    except Exception as e:
        # fall back to the thin search entry rather than failing outright
        best['scrapeError'] = str(e)
        return best
    detail['matchScore'] = round(score, 3)
    return detail


def main():
    if len(sys.argv) < 3:
        print('Usage: python analvids_scraper_fixed.py <search|scene-url|performer-url> <query_or_url>')
        sys.exit(1)
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'search':
        print(json.dumps(search_scenes(arg), indent=2))
    elif op == 'scene-url':
        print(json.dumps(scrape_scene(arg), indent=2))
    elif op == 'performer-url':
        print(json.dumps(scrape_performer(arg), indent=2))
    else:
        print(f'Unknown operation: {op}')
        sys.exit(1)


if __name__ == '__main__':
    main()
