#!/usr/bin/env python3
"""Vixen Network scraper — uses cloudscraper to bypass Cloudflare.
Sites: blacked, blackedraw, deeper, milfy, tushy, tushyraw, slayed, vixen, wifey

Usage:
  python3 vixen_scraper.py scene "vixen" "lina-luxa"
  python3 vixen_scraper.py search "vixen" "Angela White"
  python3 vixen_scraper.py scene-url "https://www.vixen.com/videos/lina-luxa"
"""

import json
import re
import sys
from urllib.parse import urlparse

import cloudscraper
from lxml import html as lxml_html

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

VIXEN_SITES = {
    'blacked': 'Blacked',
    'blackedraw': 'Blacked Raw',
    'deeper': 'Deeper',
    'milfy': 'Milfy',
    'tushy': 'Tushy',
    'tushyraw': 'Tushy Raw',
    'slayed': 'Slayed',
    'vixen': 'Vixen',
    'wifey': 'Wifey',
}

SITE_DEFAULT_TAGS = {
    'blacked': ['Black Male'],
    'blackedraw': ['Black Male'],
    'tushy': ['Anal Sex'],
    'tushyraw': ['Anal Sex'],
    'slayed': ['Lesbian Sex'],
    'milfy': ['MILF'],
}

VIDEO_QUERY = """query getVideo($videoSlug: String, $site: Site) {
  findOneVideo(input: {slug: $videoSlug, site: $site}) {
    title description releaseDate
    models { name }
    videoId
    directors { name }
    images { poster { src width } }
    categories { name }
    runLength
  }
}"""

SEARCH_QUERY = """query getSearchResults($query: String!, $site: Site!, $first: Int) {
  searchVideos(input: { query: $query, site: $site, first: $first }) {
    edges {
      node {
        description title slug releaseDate videoId
        modelsSlugged: models { name slugged: slug }
        images { listing { src width } }
      }
    }
  }
}"""


def site_from_url(url):
    host = urlparse(url).hostname.replace('www.', '').replace('.com', '')
    return host


def slug_from_url(url):
    return url.lower().rstrip('/').split('/')[-1]


def graphql_query(site_key, query, variables):
    api = f'https://www.{site_key}.com/graphql'
    r = scraper.post(api, json={
        'query': query,
        'operationName': query.split('(')[0].split('{')[0].strip().split()[-1] if '(' in query else '',
        'variables': variables,
    }, headers={
        'Content-Type': 'application/json',
        'Referer': f'https://www.{site_key}.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0',
    }, timeout=15)
    r.raise_for_status()
    return r.json()


def parse_scene(data, site_key):
    if not data:
        return None
    scene = {
        'kind': 'scene',
        'title': data.get('title'),
        'description': data.get('description'),
        'details': data.get('description'),
        'studio': VIXEN_SITES.get(site_key, site_key),
        'code': str(data['videoId']) if data.get('videoId') else None,
        'director': ', '.join(d['name'] for d in data.get('directors', []) if d.get('name')) or None,
        'date': data.get('releaseDate', '').split('T')[0] or None,
        'performers': [{'name': m['name']} for m in data.get('models', []) if m.get('name')],
    }
    cats = [c['name'] for c in data.get('categories', []) if c.get('name')]
    default_tags = SITE_DEFAULT_TAGS.get(site_key, [])
    cats.extend(default_tags)
    scene['categories'] = list(set(cats))
    scene['tags'] = scene['categories']

    # Best poster image
    posters = data.get('images', {}).get('poster', [])
    if posters:
        best = max(posters, key=lambda p: p.get('width', 0))
        image = best.get('src')
        scene['image'] = image
        scene['thumbnail'] = image
        scene['cardThumbnail'] = image
        scene['cover_a'] = image

    if data.get('runLength'):
        try:
            raw = str(data['runLength']).strip()
            if ':' in raw:
                parts = raw.split(':')
                if len(parts) == 2:
                    scene['durationMin'] = int(parts[0]) + round(int(parts[1]) / 60)
                elif len(parts) == 3:
                    scene['durationMin'] = int(parts[0]) * 60 + int(parts[1]) + round(int(parts[2]) / 60)
            else:
                secs = int(raw)
                scene['durationMin'] = round(secs / 60) if secs > 120 else secs
        except (ValueError, TypeError):
            pass

    scene['sourceSite'] = site_key
    return scene


def scrape_scene(url):
    site_key = site_from_url(url)
    if site_key not in VIXEN_SITES:
        return {'error': f'Not a Vixen Network URL: {site_key}'}
    slug = slug_from_url(url)
    resp = graphql_query(site_key, VIDEO_QUERY, {'site': site_key.upper(), 'videoSlug': slug})
    data = resp.get('data', {}).get('findOneVideo')
    if not data:
        return {'notFound': True}
    scene = parse_scene(data, site_key)
    scene['sourceUrl'] = url
    return scene


def search_scenes(query, site_key=None):
    sites = [site_key] if site_key and site_key in VIXEN_SITES else list(VIXEN_SITES.keys())
    all_results = []
    for sk in sites:
        try:
            resp = graphql_query(sk, SEARCH_QUERY, {'site': sk.upper(), 'query': query, 'first': 6})
            edges = resp.get('data', {}).get('searchVideos', {}).get('edges', [])
            for edge in edges:
                node = edge.get('node', {})
                if not node.get('slug'):
                    continue
                posters = node.get('images', {}).get('listing', [])
                thumbnail = ''
                if posters:
                    best = max(posters, key=lambda p: p.get('width', 0))
                    thumbnail = best.get('src', '')
                all_results.append({
                    'kind': 'scene',
                    'title': node.get('title'),
                    'url': f'https://www.{sk}.com/videos/{node["slug"]}',
                    'date': (node.get('releaseDate') or '').split('T')[0] or None,
                    'performers': [{'name': m['name']} for m in node.get('modelsSlugged', []) if m.get('name')],
                    'thumbnail': thumbnail,
                    'cardThumbnail': thumbnail,
                    'cover_a': thumbnail,
                    'description': node.get('description'),
                    'studio': VIXEN_SITES.get(sk, sk),
                    'site': sk,
                })
        except Exception:
            continue
    return all_results if all_results else {'notFound': True}


def scrape_performer_photo(site_key, performer_slug):
    """Scrape performer photo from a Vixen Network site."""
    url = f'https://www.{site_key}.com/performers/{performer_slug}'
    r = scraper.get(url, timeout=(5, 15))
    r.raise_for_status()

    # Extract CDN image URL (signed, from page source)
    # URL in HTML uses & instead of &
    m = re.search(r'(https://cdn\.[a-z]+\.com/scene/models/[^"\s]+)', r.text)
    if m:
        photo = m.group(1).replace('&', '&')
        return {'kind': 'performer', 'photo': photo, 'image': photo, 'thumbnail': photo, 'cardThumbnail': photo, 'cover_a': photo, 'cover_b': '', 'sourceUrl': url, 'notFound': False}

    # Fallback: og:image
    tree = lxml_html.fromstring(r.text)
    og_img = tree.xpath('//meta[@property="og:image"]/@content')
    if og_img:
        photo = og_img[0]
        return {'kind': 'performer', 'photo': photo, 'image': photo, 'thumbnail': photo, 'cardThumbnail': photo, 'cover_a': photo, 'cover_b': '', 'sourceUrl': url, 'notFound': False}

    return {'notFound': True}


def search_performer_on_site(site_key, name):
    """Search for a performer on a specific Vixen site and return their page URL + photo."""
    # Try direct URL pattern first
    slug = name.lower().replace(' ', '-').replace("'", '')
    try:
        result = scrape_performer_photo(site_key, slug)
        if not result.get('notFound') and result.get('photo'):
            result['kind'] = 'performer'
            return result
    except Exception:
        pass

    # Search via GraphQL
    try:
        resp = graphql_query(site_key, SEARCH_QUERY, {'site': site_key.upper(), 'query': name, 'first': 5})
        edges = resp.get('data', {}).get('searchVideos', {}).get('edges', [])
        name_lower = name.lower()
        for edge in edges:
            node = edge.get('node', {})
            for model in node.get('modelsSlugged', []) + node.get('models', []):
                model_name = (model.get('name') or '').lower()
                if name_lower in model_name or model_name in name_lower:
                    # Found a scene with this performer — get thumbnail from scene
                    posters = node.get('images', {}).get('listing', [])
                    if posters:
                        best = max(posters, key=lambda p: p.get('width', 0))
                        photo = best.get('src')
                        return {'kind': 'performer', 'photo': photo, 'image': photo, 'thumbnail': photo, 'cardThumbnail': photo, 'cover_a': photo, 'cover_b': '', 'sourceUrl': f'https://www.{site_key}.com/videos/{node.get("slug", "")}', 'notFound': False}
    except Exception:
        pass

    return {'notFound': True}


def scrape(title="", url="", html="", kind="", domain=""):
    """Unified entry point called by the backend."""
    if url:
        if '/performers/' in url:
            return scrape_performer_photo(site_from_url(url), slug_from_url(url))
        return scrape_scene(url)
    if title:
        # Detect target site from domain
        target_site = ''
        if domain:
            dom = domain.replace('www.', '').replace('.com', '').lower()
            if dom in VIXEN_SITES:
                target_site = dom

        if kind == 'performer':
            sites = [target_site] if target_site else list(VIXEN_SITES.keys())
            for site_key in sites:
                result = search_performer_on_site(site_key, title)
                if not result.get('notFound'):
                    return result
            return {'notFound': True}

        results = search_scenes(title, site_key=target_site or None)
        if isinstance(results, list) and results:
            query_lower = title.strip().lower()
            best = next((r for r in results if query_lower in (r.get('title') or '').lower()), results[0])
            scene_url = best.get('url')
            if scene_url:
                try:
                    full = scrape_scene(scene_url)
                    if isinstance(full, dict) and not full.get('notFound') and not full.get('error'):
                        for k, v in best.items():
                            if k not in full or full[k] is None:
                                full[k] = v
                        return full
                except Exception:
                    pass
            return best
        return results
    return {'error': 'need url or title'}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: vixen_scraper.py <scene|search|scene-url> [args...]'}))
        sys.exit(1)

    op = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ''
    arg2 = sys.argv[3] if len(sys.argv) > 3 else ''

    try:
        if op == 'scene-url':
            result = scrape_scene(arg)
        elif op == 'scene':
            # scene <site> <slug>
            site_key = arg
            slug = arg2
            if site_key not in VIXEN_SITES:
                result = {'error': f'Unknown site: {site_key}'}
            else:
                resp = graphql_query(site_key, VIDEO_QUERY, {'site': site_key.upper(), 'videoSlug': slug})
                data = resp.get('data', {}).get('findOneVideo')
                result = parse_scene(data, site_key) if data else {'notFound': True}
        elif op == 'search':
            site_key = arg2 if arg2 else None
            result = search_scenes(arg, site_key)
        elif op == 'performer-photo':
            # performer-photo <name> <site>
            site_key = arg2 if arg2 else 'vixen'
            result = search_performer_on_site(site_key, arg)
        else:
            result = {'error': f'Unknown operation: {op}'}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
