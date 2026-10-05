#!/usr/bin/env python3
"""IAFD scraper — uses cloudscraper to bypass Cloudflare.

Usage:
  python3 iafd_scraper.py search "Angela White"
  python3 iafd_scraper.py url "https://www.iafd.com/person.rme/id=..."
"""

import json
import re
import sys
import time
from urllib.parse import urljoin

import cloudscraper
from lxml import html as lxml_html

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

# Expose session for server.py to reuse for image downloads
iafd_session = scraper

MAX_RETRIES = 3
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 60


def _get_with_retry(url, retries=MAX_RETRIES):
    """GET with retry and exponential backoff."""
    for attempt in range(retries):
        try:
            r = scraper.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            r.raise_for_status()
            return r
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


# Warm up
try:
    scraper.get('https://www.iafd.com/', timeout=(15, 30))
except Exception:
    pass


def scrape_performer(url):
    """Scrape performer details from IAFD URL."""
    r = _get_with_retry(url)
    tree = lxml_html.fromstring(r.text)

    h1 = tree.xpath('//h1')
    name = h1[0].text_content().strip().split(' (')[0].strip() if h1 else 'Unknown'

    def get(label):
        for h in tree.xpath('//p[@class="bioheading"]'):
            heading = h.text_content().strip().lower()
            if heading == label.lower() or heading.startswith(label.lower()):
                d = h.getnext()
                if d is not None and 'biodata' in (d.get('class') or ''):
                    return d.text_content().strip().replace('\xa0', ' ').replace('  ', ' ')
        return None

    # Photo
    photo = None
    for sel in [
        '//img[contains(@src, "/headshots/")]',
        '//img[contains(@src, "headshots")]',
        '//div[@id="headshot"]//img',
        '//img[contains(@class, "headshot")]',
        '//div[contains(@class, "headshot")]//img',
        '//div[contains(@class, "photo")]/img',
        '//img[contains(@src, "photo")]',
        '//div[@id="photo"]//img',
    ]:
        for attr in ('src', 'data-src', 'data-original', 'data-lazy-src'):
            imgs = tree.xpath(f'{sel}/@{attr}')
            if imgs and imgs[0].strip():
                photo = imgs[0].strip()
                break
        if photo:
            break
    # Fallback: an <a> wrapping the headshot with the full-size image as its href
    if not photo:
        for sel in ['//div[@id="headshot"]//a/@href', '//div[contains(@class,"headshot")]//a/@href',
                    '//a[contains(@href, "headshots")]/@href']:
            hrefs = tree.xpath(sel)
            if hrefs and hrefs[0].strip():
                photo = hrefs[0].strip()
                break
    # Fallback: any image with iafd in src that isn't a favicon/icon
    if not photo:
        for img in tree.xpath('//img'):
            src = img.get('src') or img.get('data-src') or ''
            if src and 'headshots' in src:
                photo = src.strip()
                break
    if photo:
        if photo.startswith('//'):
            photo = 'https:' + photo
        elif photo.startswith('/'):
            photo = 'https://www.iafd.com' + photo
        # Download image through the scraper session (bypasses Cloudflare)
        try:
            img_resp = scraper.get(photo, timeout=15)
            img_resp.raise_for_status()
            import base64
            mime = img_resp.headers.get('content-type', 'image/jpeg').split(';')[0].strip()
            b64 = base64.b64encode(img_resp.content).decode('ascii')
            photo = f'data:{mime};base64,{b64}'
        except Exception as e:
            print(f'[iafd] Failed to download photo: {e}', file=sys.stderr)

    # Birthday
    bday_raw = get('birthday')
    birthday = None
    if bday_raw:
        m = re.search(r'(\w+ \d+, \d{4})', bday_raw)
        if m:
            birthday = m.group(1)

    # Height
    height_str = get('height')
    height = None
    if height_str:
        m = re.search(r'(\d+)\s*cm', height_str)
        if m:
            height = int(m.group(1))

    # Weight
    weight_str = get('weight')
    weight = None
    if weight_str:
        m = re.search(r'(\d+)\s*kg', weight_str)
        if m:
            weight = int(m.group(1))

    result = {
        'kind': 'performer',
        'name': name,
        'birthday': birthday,
        'nationality': get('nationality'),
        'ethnicity': get('ethnicity'),
        'hairColor': get('hair color') or get('hair colors'),
        'eyeColor': get('eye color'),
        'height': height,
        'weight': weight,
        'measurements': get('measurements'),
        'activeYears': get('years active as performer') or get('years active'),
        'tattoos': get('tattoos'),
        'piercings': get('piercings'),
        'photo': photo,
        'image': photo,
        'thumbnail': photo,
        'cardThumbnail': photo,
        'cover_a': photo,
        'cover_b': photo,
        'iafdUrl': url,
        'notFound': False,
    }
    # Social media links — try multiple strategies
    # Strategy 1: Match <a> tags by text content (stashapp approach — IAFD shows URLs as link text)
    for a in tree.xpath('//p[@class="biodata"]//a'):
        text = (a.text_content() or '').strip()
        low = text.lower()
        if 'twitter.com' in low or 'x.com' in low:
            handle = text.rstrip('/').split('/')[-1]
            if handle and handle not in ('twitter', 'x', 'com', 'status', 'intent'):
                result['twitter'] = '@' + handle
        elif 'instagram.com' in low:
            handle = text.rstrip('/').split('/')[-1]
            if handle and handle not in ('instagram', 'com', 'accounts', 'p', 'explore'):
                result['instagram'] = '@' + handle
        elif 'onlyfans.com' in low:
            handle = text.rstrip('/').split('/')[-1]
            if handle and handle not in ('onlyfans', 'com'):
                result['onlyfans'] = handle
    # Strategy 2: Bioheading "Social" → sibling biodata
    if not result.get('twitter') and not result.get('instagram') and not result.get('onlyfans'):
        social_els = tree.xpath('//p[@class="bioheading"][contains(text(),"Social")]/following-sibling::p[@class="biodata"][1]//a/@href')
        for href in social_els:
            low = href.lower()
            if 'twitter.com' in low or 'x.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('twitter', 'x', 'com', 'status', 'intent'):
                    result['twitter'] = '@' + handle
            elif 'instagram.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('instagram', 'com', 'accounts', 'p', 'explore'):
                    result['instagram'] = '@' + handle
            elif 'onlyfans.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('onlyfans', 'com'):
                    result['onlyfans'] = handle
    # Strategy 3: Any biodata link with social href
    if not result.get('twitter') and not result.get('instagram') and not result.get('onlyfans'):
        social_els = tree.xpath('//p[@class="biodata"]//a[contains(@href,"twitter.com") or contains(@href,"x.com") or contains(@href,"instagram.com") or contains(@href,"onlyfans.com")]/@href')
        for href in social_els:
            low = href.lower()
            if 'twitter.com' in low or 'x.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('twitter', 'x', 'com', 'status', 'intent'):
                    result['twitter'] = '@' + handle
            elif 'instagram.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('instagram', 'com', 'accounts', 'p', 'explore'):
                    result['instagram'] = '@' + handle
            elif 'onlyfans.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('onlyfans', 'com'):
                    result['onlyfans'] = handle
    # Strategy 4: Broadest — any link on the page with social domain
    if not result.get('twitter') and not result.get('instagram') and not result.get('onlyfans'):
        social_els = tree.xpath('//a[contains(@href,"twitter.com") or contains(@href,"x.com") or contains(@href,"instagram.com") or contains(@href,"onlyfans.com")]/@href')
        for href in social_els:
            low = href.lower()
            if 'twitter.com' in low or 'x.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('twitter', 'x', 'com', 'status', 'intent'):
                    result['twitter'] = '@' + handle
            elif 'instagram.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('instagram', 'com', 'accounts', 'p', 'explore'):
                    result['instagram'] = '@' + handle
            elif 'onlyfans.com' in low:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('onlyfans', 'com'):
                    result['onlyfans'] = handle
    if photo:
        result['image'] = photo
        result['thumbnail'] = photo
        result['cardThumbnail'] = photo
        result['cover_a'] = photo
        result['cover_b'] = photo
    return result


def search_performer(name):
    """Search for a performer on IAFD."""
    r = _get_with_retry(
        f'https://www.iafd.com/ramesearch.asp?searchtype=comprehensive&searchstring={name.replace(" ", "+")}'
    )
    tree = lxml_html.fromstring(r.text)

    links = tree.xpath('//a[contains(@href, "/person.rme/")]')
    name_lower = name.lower()

    for priority in (1, 2):
        for a in links:
            text = a.text_content().strip().lower()
            if not text:
                continue
            if priority == 1 and text != name_lower:
                continue
            if priority == 2 and name_lower not in text and text not in name_lower:
                continue
            href = a.get('href', '')
            if href:
                full_url = urljoin('https://www.iafd.com', href)
                return scrape_performer(full_url)

    return {'notFound': True, 'name': name}




def scrape(title="", url="", html="", name="", **kwargs):
    """Unified entry point called by the backend."""
    if url:
        return scrape_performer(url)
    query = (title or name or "").strip()
    if query:
        return search_performer(query)
    return {"error": "need url or title", "notFound": True}

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: iafd_scraper.py <search|url> <name|url>'}))
        sys.exit(1)

    op = sys.argv[1]
    arg = sys.argv[2]

    try:
        if op == 'search':
            result = search_performer(arg)
        elif op == 'url':
            result = scrape_performer(arg)
        else:
            result = {'error': f'Unknown operation: {op}'}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
