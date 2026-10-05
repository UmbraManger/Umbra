#!/usr/bin/env python3
"""Bang.com scraper — uses cloudscraper to bypass Cloudflare.

Usage:
  python3 bang_scraper.py search "Angela White"
  python3 bang_scraper.py scene-url "https://www.bang.com/video/..."
  python3 bang_scraper.py performer-search "Angela White"
  python3 bang_scraper.py performer-url "https://www.bang.com/pornstar/..."
"""

import json
import re
import sys

import cloudscraper
from lxml import html as lxml_html
from urllib.parse import urljoin

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)
# Warm up session
try:
    scraper.get('https://www.bang.com/', timeout=(5, 10))
except Exception:
    pass


def search_scenes(query):
    """Search for scenes on Bang.com"""
    url = f"https://www.bang.com/videos?term={query.replace(' ', '+')}"
    r = scraper.get(url, timeout=(5, 15))
    r.raise_for_status()
    tree = lxml_html.fromstring(r.text)

    containers = tree.xpath('//div[contains(@class, "video_container")]')
    results = []
    for c in containers:
        links = c.xpath('.//a[contains(@href, "/video/")]')
        if not links:
            continue
        a = links[0]
        href = a.get('href', '')
        if not href or '/video?' in href:
            continue
        title_spans = a.xpath('.//span')
        title = title_spans[0].text_content().strip() if title_spans else ''
        if not title or len(title) < 3:
            continue

        img = c.xpath('.//img/@src')
        thumbnail = img[0] if img else ''

        # Performers
        perf_links = c.xpath('.//a[contains(@href, "/pornstar/")]')
        performers = [p.text_content().strip() for p in perf_links if p.text_content().strip()]

        full_url = urljoin("https://www.bang.com", href)
        results.append({
            'kind': 'scene',
            'title': title,
            'url': full_url,
            'thumbnail': thumbnail,
            'cardThumbnail': thumbnail,
            'cover_a': thumbnail,
            'cover_b': thumbnail,
            'performers': [{'name': p} for p in performers],
            'site': 'bang'
        })

    return results[:15] if results else {'notFound': True}


def scrape_scene(url):
    """Scrape scene details from a Bang.com URL"""
    r = scraper.get(url, timeout=(5, 15))
    r.raise_for_status()
    tree = lxml_html.fromstring(r.text)

    scene = {'kind': 'scene', 'sourceUrl': url, 'sourceSite': 'bang'}

    # Title from og:title
    og_title = tree.xpath('//meta[@property="og:title"]/@content')
    scene['title'] = og_title[0].strip() if og_title else None

    # Description
    og_desc = tree.xpath('//meta[@name="description"]/@content')
    scene['details'] = og_desc[0].strip() if og_desc else None

    # Thumbnail
    og_image = tree.xpath('//meta[@property="og:image"]/@content')
    image = og_image[0] if og_image else None
    scene['thumbnail'] = image
    scene['cardThumbnail'] = image
    scene['cover_a'] = image
    scene['cover_b'] = image
    scene['image'] = image

    # Release date — try meta tag, then JSON-LD, then visible text
    release_date = tree.xpath('//meta[@property="video:release_date"]/@content')
    if not release_date:
        release_date = tree.xpath('//meta[@property="og:release_date"]/@content')
    if not release_date:
        # Try JSON-LD script block
        scripts = tree.xpath('//script[@type="application/ld+json"]/text()')
        for s in scripts:
            m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', s)
            if m:
                release_date = [m.group(1)]
                break
    if not release_date:
        # Try visible date text near "Release" label
        date_el = tree.xpath('//*[contains(text(),"Release")]/following-sibling::*[1]//text() | //*[contains(text(),"Date")]/following-sibling::*[1]//text()')
        if date_el:
            release_date = [date_el[0].strip()]
    scene['date'] = release_date[0] if release_date else None

    # Tags
    tag_els = tree.xpath('//a[@class="genres"]')
    scene['tags'] = [t.text_content().strip() for t in tag_els if t.text_content().strip()]

    # Performers
    perf_links = tree.xpath('//p[contains(@class, "capitalize")]//a[contains(@href, "/pornstar/")]')
    scene['performers'] = [{
        'name': p.text_content().strip(),
        'url': urljoin("https://www.bang.com", p.get('href', ''))
    } for p in perf_links if p.text_content().strip()]

    # Studio
    studio_link = tree.xpath('//a[contains(@href, "/originals/")]')
    if studio_link:
        studio_text = studio_link[0].text_content().strip()
        if studio_text.lower() == 'yngr.com':
            studio_text = 'YNGR'
        scene['studio'] = studio_text

    # Movie/DVD
    movie_link = tree.xpath('//a[contains(@href, "/dvd/")]//div[contains(@class, "name")]/span[1]')
    if movie_link:
        scene['movieName'] = movie_link[0].text_content().strip()
        movie_href = tree.xpath('//a[contains(@href, "/dvd/")]/@href')
        if movie_href:
            h = movie_href[0]
            scene['movieUrl'] = urljoin("https://www.bang.com", h)

    # Code from og:video
    og_video = tree.xpath('//meta[@property="og:video"]/@content')
    if og_video:
        m = re.search(r'/(\d+)/', og_video[0])
        if m:
            scene['code'] = m.group(1)

    # Duration — try JSON-LD, meta tags, or visible text
    duration_min = None
    for s in tree.xpath('//script[@type="application/ld+json"]/text()'):
        m = re.search(r'"duration"\s*:\s*"PT(\d+)M', s)
        if m:
            duration_min = int(m.group(1))
            break
        m = re.search(r'"duration"\s*:\s*"PT(?:(\d+)H)?(?:(\d+)M)?', s)
        if m:
            hours = int(m.group(1) or 0)
            mins = int(m.group(2) or 0)
            duration_min = hours * 60 + mins
            if duration_min:
                break
    if not duration_min:
        # Try meta tags
        dur_meta = tree.xpath('//meta[@property="video:duration"]/@content | //meta[@itemprop="duration"]/@content')
        if dur_meta:
            raw = dur_meta[0].strip()
            m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', raw)
            if m:
                duration_min = int(m.group(1) or 0) * 60 + int(m.group(2) or 0) + (1 if m.group(3) and int(m.group(3)) > 30 else 0)
    if not duration_min:
        # Try visible text patterns like "25 min" or "1h 25m"
        page_text = tree.text_content()
        m = re.search(r'(\d+)\s*min', page_text)
        if m:
            duration_min = int(m.group(1))
        else:
            m = re.search(r'(\d+)h\s*(\d+)m', page_text)
            if m:
                duration_min = int(m.group(1)) * 60 + int(m.group(2))
    if duration_min:
        scene['durationMin'] = duration_min

    if not scene.get('title'):
        return {'notFound': True}

    return scene


def search_performers(query):
    """Search for performers on Bang.com"""
    url = f"https://www.bang.com/pornstars?term={query.replace(' ', '+')}"
    r = scraper.get(url, timeout=(5, 15))
    r.raise_for_status()
    tree = lxml_html.fromstring(r.text)

    containers = tree.xpath('//div[contains(@class, "search_container")]')
    results = []
    for c in containers:
        a = c.xpath('.//a[contains(@href, "/pornstar/")]')
        span = c.xpath('.//a//span')
        if a and span:
            href = a[0].get('href', '')
            full_url = urljoin("https://www.bang.com", href)
            results.append({
                'kind': 'performer',
                'name': span[0].text_content().strip(),
                'url': full_url
            })

    return {'performers': results} if results else {'notFound': True}


def scrape_performer(url):
    """Scrape performer details from a Bang.com URL"""
    r = scraper.get(url, timeout=(5, 15))
    r.raise_for_status()
    tree = lxml_html.fromstring(r.text)

    # Find the main info container
    overlay = tree.xpath('//div[contains(@class, "flex") and contains(@class, "flex-col")]')
    if not overlay:
        return {'notFound': True}
    container = overlay[0]

    # Name from h2
    h2 = container.xpath('.//h2')
    name = h2[0].text_content().strip() if h2 else None
    if not name:
        return {'notFound': True}

    perf = {'name': name, 'bangUrl': url, 'notFound': False}

    # Aliases from h1 sibling
    h1 = container.xpath('.//h1')
    if h1:
        sibling = h1[0].getnext()
        if sibling is not None:
            alias_text = sibling.text_content().strip()
            if alias_text:
                perf['aliases'] = [a.strip() for a in alias_text.split(',') if a.strip()]

    # Info fields — look for text patterns
    all_text = container.text_content()

    # Birthday
    born_match = re.search(r'(\w+ \d+),?\s*(\d{4}).*?(\d+)\s*years?\s*old', all_text)
    if born_match:
        perf['birthday'] = f"{born_match.group(1)}, {born_match.group(2)}"

    # Hair Color
    hair = container.xpath('.//div[contains(text(), "Hair Color")]/following-sibling::span[1]/text()')
    if not hair:
        hair = container.xpath('.//span[contains(text(), "Hair Color")]/following-sibling::span[1]/text()')
    if hair:
        perf['hairColor'] = hair[0].strip()

    # Ethnicity
    eth = container.xpath('.//div[contains(text(), "Ethnicity")]/following-sibling::span[1]/text()')
    if not eth:
        eth = container.xpath('.//span[contains(text(), "Ethnicity")]/following-sibling::span[1]/text()')
    if eth:
        perf['ethnicity'] = eth[0].strip()

    # Eye Color
    eye = container.xpath('.//div[contains(text(), "Eye Color")]/following-sibling::span[1]/text()')
    if not eye:
        eye = container.xpath('.//span[contains(text(), "Eye Color")]/following-sibling::span[1]/text()')
    if eye:
        perf['eyeColor'] = eye[0].strip()

    # Photo
    img = tree.xpath('//div[contains(@class, "relative")]//img/@src')
    if img:
        photo = img[0]
        perf['photo'] = re.sub(r'\?.*$', '', photo)

    perf['kind'] = 'performer'
    perf['photo'] = perf.get('photo')
    perf['image'] = perf.get('photo')
    perf['thumbnail'] = perf.get('photo')
    perf['cardThumbnail'] = perf.get('photo')
    return perf


def scrape(title="", url="", html="", kind=""):
    """Unified entry point called by the backend."""
    if url:
        if '/pornstar/' in url:
            return scrape_performer(url)
        return scrape_scene(url)
    if title:
        if kind == 'performer':
            results = search_performers(title)
            hits = results.get('performers') if isinstance(results, dict) else None
            if hits:
                return scrape_performer(hits[0]['url'])
            return results
        results = search_scenes(title)
        if isinstance(results, list) and results:
            # Follow through to get full scene details from the scene page
            first = results[0]
            scene_url = first.get('url')
            if scene_url:
                try:
                    full = scrape_scene(scene_url)
                    if isinstance(full, dict) and not full.get('notFound'):
                        # Merge: prefer full page data, keep search extras as fallback
                        for k, v in first.items():
                            if k not in full or full[k] is None:
                                full[k] = v
                        return full
                except Exception:
                    pass
            return first
        return results
    return {'error': 'need url or title'}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: bang_scraper.py <search|scene-url|performer-search|performer-url> <query|url>'}))
        sys.exit(1)

    op = sys.argv[1]
    arg = sys.argv[2]

    try:
        if op == 'search':
            result = search_scenes(arg)
        elif op == 'scene-url':
            result = scrape_scene(arg)
        elif op == 'performer-search':
            result = search_performers(arg)
        elif op == 'performer-url':
            result = scrape_performer(arg)
        else:
            result = {'error': f'Unknown operation: {op}'}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
