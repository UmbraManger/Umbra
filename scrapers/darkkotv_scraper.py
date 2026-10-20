#!/usr/bin/env python3
"""DarkkoTV scraper — uses cloudscraper to bypass Cloudflare.
Based on stashapp/CommunityScrapers DarkkoTV.yml

Usage:
  python3 darkkotv_scraper.py search "title"
  python3 darkkotv_scraper.py scene-url "https://darkkotv.com/scenes/..."
  python3 darkkotv_scraper.py performer-url "https://darkkotv.com/models/..."
"""

import json
import re
import sys
from datetime import datetime
from urllib.parse import urljoin

import cloudscraper
from lxml import html as lxml_html

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)
# Set cookie to skip age/country gate
scraper.cookies.set('warn', 'true', domain='darkkotv.com', path='/')
scraper.headers.update({
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})

# Warm up session
try:
    scraper.get('https://darkkotv.com/', timeout=(10, 30))
except Exception:
    pass

BASE_URL = 'https://darkkotv.com'
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 30


def _fetch(url):
    """Fetch with retry on timeout."""
    for attempt in range(3):
        try:
            r = scraper.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == 2:
                raise
            import time
            time.sleep(2 * (attempt + 1))


def _parse_date(date_str):
    """Parse date strings and return ISO format. Handles MM-DD-YYYY, YYYY-MM-DD, and others."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # DarkkoTV uses MM-DD-YYYY (Go format 01-02-2006)
    for fmt in ('%m-%d-%Y', '%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y', '%d %B %Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str


def _format_display_date(iso_str):
    """Format ISO date as 'March 27, 2026'."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
        return f"{months[dt.month - 1]} {dt.day}, {dt.year}"
    except (ValueError, AttributeError):
        return iso_str


def search_scenes(query):
    """Search for scenes on DarkkoTV."""
    url = f"{BASE_URL}/search?query={query.replace(' ', '+')}"
    r = _fetch(url)
    tree = lxml_html.fromstring(r.text)

    results = []
    # Scene cards — look for links to /scenes/
    cards = tree.xpath('//a[contains(@href, "/scenes/")]')
    seen = set()
    for a in cards:
        href = a.get('href', '')
        if not href or href in seen:
            continue
        seen.add(href)
        full_url = urljoin(BASE_URL, href)

        # Title from card text or inner elements
        title = a.text_content().strip()
        if not title or len(title) < 3:
            continue

        # Thumbnail
        img = a.xpath('.//img/@src')
        thumbnail = img[0] if img else ''
        if thumbnail:
            thumbnail = urljoin(BASE_URL, thumbnail)

        results.append({
            'kind': 'scene',
            'title': title,
            'url': full_url,
            'thumbnail': thumbnail,
            'cardThumbnail': thumbnail,
            'cover_a': thumbnail,
            'cover_b': thumbnail,
            'site': 'darkkotv'
        })

    return results[:15] if results else {'notFound': True}


def scrape_scene(url):
    """Scrape scene details from a DarkkoTV URL."""
    r = _fetch(url)
    tree = lxml_html.fromstring(r.text)

    scene = {'kind': 'scene', 'sourceUrl': url, 'sourceSite': 'darkkotv'}

    # Title
    title_el = tree.xpath('//h4[@class="text_light"]')
    if title_el:
        scene['title'] = title_el[0].text_content().strip()

    # Description
    content = tree.xpath('//div[@class="vidImidWrap"]')
    if content:
        desc_parts = content[0].xpath('.//div[@class="vidImgContent text_light"]/p//text()')
        if desc_parts:
            scene['description'] = ' '.join(p.strip() for p in desc_parts if p.strip())

    # Release date — calendar icon sibling text (MM-DD-YYYY per Go format 01-02-2006)
    if content:
        date_text = content[0].xpath('.//i[contains(@class, "fa-calendar")]/../../text()')
        if date_text:
            raw_date = ''.join(date_text).strip()
            iso_date = _parse_date(raw_date)
            if iso_date:
                scene['date'] = iso_date
                scene['releaseDate'] = _format_display_date(iso_date)

    # Image (og:image fallback)
    og_image = tree.xpath('//meta[@property="og:image"]/@content')
    image = og_image[0] if og_image else None
    scene['image'] = image
    scene['thumbnail'] = image
    scene['cardThumbnail'] = image
    scene['cover_a'] = image
    scene['cover_b'] = image

    # Studio
    scene['studio'] = 'Darkko TV'

    # Tags
    tags = tree.xpath('//div[@class="blogTags"]/ul/li/a/text()')
    scene['tags'] = [t.strip() for t in tags if t.strip()]

    # Performers
    if content:
        perf_links = content[0].xpath('.//i[contains(@class, "fa-user")]/../a')
        scene['performers'] = [{
            'name': a.text_content().strip(),
            'url': urljoin(BASE_URL, a.get('href', ''))
        } for a in perf_links if a.text_content().strip()]

    if not scene.get('title'):
        return {'notFound': True}

    return scene


def scrape_performer(url):
    """Scrape performer details from a DarkkoTV URL."""
    r = _fetch(url)
    tree = lxml_html.fromstring(r.text)

    # Name
    h1 = tree.xpath('//h1/text()')
    if not h1:
        return {'notFound': True}
    name = h1[0].strip()
    perf = {'kind': 'performer', 'name': name, 'sourceUrl': url, 'sourceSite': 'darkkotv', 'notFound': False}

    # Vital stats container
    stats = tree.xpath('//div[@class="vitalStats"]/ul/li')

    def _get_stat(label):
        for li in stats:
            text = li.text_content().strip()
            if text.lower().startswith(label.lower()):
                return text.split(':', 1)[1].strip() if ':' in text else ''
        return None

    # Aliases
    aliases = _get_stat('Aliases')
    if aliases:
        perf['aliases'] = [a.strip() for a in aliases.split(',') if a.strip()]

    # Birthday
    dob = _get_stat('Date of Birth')
    if dob:
        iso = _parse_date(dob)
        if iso:
            perf['birthday'] = iso

    # Height (cm)
    height = _get_stat('Height')
    if height:
        m = re.search(r'(\d+)', height)
        if m:
            perf['height'] = int(m.group(1))

    # Weight
    weight = _get_stat('Weight')
    if weight:
        m = re.search(r'(\d+)', weight)
        if m:
            perf['weight'] = int(m.group(1))

    # Measurements
    measurements = _get_stat('Measurements')
    if measurements:
        perf['measurements'] = measurements

    # Piercings
    piercings = _get_stat('Piercings')
    if piercings:
        perf['piercings'] = piercings

    # Tattoos
    tattoos = _get_stat('Tattoos')
    if tattoos:
        perf['tattoos'] = tattoos

    # Photo
    img = tree.xpath('//div[contains(@class, "modelImg")]//img/@src | //div[contains(@class, "performer")]//img/@src | //img[contains(@class, "model")]/@src')
    if img:
        photo = urljoin(BASE_URL, img[0])
        perf['photo'] = photo
        perf['image'] = photo
        perf['thumbnail'] = photo
        perf['cardThumbnail'] = photo
        perf['cover_a'] = photo
        perf['cover_b'] = photo

    return perf


def search_performers(query):
    """Search DarkkoTV for model pages."""
    url = f"{BASE_URL}/search?query={query.replace(' ', '+')}"
    r = _fetch(url)
    tree = lxml_html.fromstring(r.text)

    results = []
    seen = set()
    for a in tree.xpath('//a[contains(@href, "/models/")]'):
        href = a.get('href', '')
        if not href or href in seen:
            continue
        seen.add(href)
        full_url = urljoin(BASE_URL, href)
        name = a.text_content().strip()
        if name and len(name) > 1:
            results.append({'kind': 'performer', 'name': name, 'url': full_url})
    return results


def scrape(title="", url="", html="", kind=""):
    """Unified entry point called by the backend."""
    if url:
        if '/models/' in url:
            return scrape_performer(url)
        return scrape_scene(url)
    if title:
        if kind == 'performer':
            hits = search_performers(title)
            if hits:
                return scrape_performer(hits[0]['url'])
            return {'notFound': True}
        results = search_scenes(title)
        if isinstance(results, list) and results:
            import titlematch
            return titlematch.best(results, title)
        return results
    return {'error': 'need url or title'}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: darkkotv_scraper.py <search|scene-url|performer-url> <query|url>'}))
        sys.exit(1)

    op = sys.argv[1]
    arg = sys.argv[2]

    try:
        if op == 'search':
            result = search_scenes(arg)
        elif op == 'scene-url':
            result = scrape_scene(arg)
        elif op == 'performer-url':
            result = scrape_performer(arg)
        else:
            result = {'error': f'Unknown operation: {op}'}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
