#!/usr/bin/env python3
"""xEmpire Network scraper — uses cloudscraper + Algolia API.
Sites: allblackx, darkx, eroticax, hardx, lesbianx, xempire

Usage:
  python3 xempire_scraper.py algolia-creds <site>
  python3 xempire_scraper.py performer "Angela White" [site]
  python3 xempire_scraper.py performer-url "https://www.darkx.com/en/pornstar/..."
  python3 xempire_scraper.py scene-search "title" [site]
  python3 xempire_scraper.py scene-url "https://www.darkx.com/en/video/..."
"""

import json
import re
import socket
import struct
import sys
from urllib.parse import urlparse

import cloudscraper
import requests
from lxml import html as lxml_html

# Patch socket.getaddrinfo to resolve Algolia domains via DoH when local DNS fails
_orig_getaddrinfo = socket.getaddrinfo
_ALGOLIA_CACHE = {}  # hostname -> resolved IP

def _resolve_algolia_doh(hostname):
    """Resolve Algolia hostname via Google DNS-over-HTTPS as fallback."""
    if hostname in _ALGOLIA_CACHE:
        return _ALGOLIA_CACHE[hostname]
    try:
        r = requests.get(
            'https://dns.google/resolve',
            params={'name': hostname, 'type': 'A'},
            timeout=5,
            headers={'Accept': 'application/dns-json'},
        )
        data = r.json()
        for answer in data.get('Answer', []):
            if answer.get('type') == 1 and answer.get('data'):
                ip = answer['data']
                _ALGOLIA_CACHE[hostname] = ip
                print(f'[dns] Resolved {hostname} -> {ip} via DoH', file=sys.stderr)
                return ip
    except Exception as e:
        print(f'[dns] DoH failed for {hostname}: {e}', file=sys.stderr)
    return None

def _patched_getaddrinfo(host, port, *args, **kwargs):
    """Patched getaddrinfo that tries DoH for Algolia domains."""
    try:
        return _orig_getaddrinfo(host, port, *args, **kwargs)
    except socket.gaierror:
        if 'algolia.net' in (host or ''):
            ip = _resolve_algolia_doh(host)
            if ip:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]
        raise

socket.getaddrinfo = _patched_getaddrinfo

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

IMAGE_CDN = "https://images03-fame.gammacdn.com"
TRANSFORM_CDN = "https://transform.gammacdn.com"

XEMPIRE_SITES = ['allblackx', 'darkx', 'eroticax', 'hardx', 'lesbianx', 'xempire']


def get_algolia_creds(site):
    """Get Algolia API credentials from an xEmpire site homepage."""
    homepage = f'https://www.{site}.com'
    try:
        r = scraper.get(homepage, timeout=(5, 15))
        r.raise_for_status()
    except Exception as e:
        print(f'[xempire] Failed to fetch {homepage}: {e}', file=sys.stderr)
        return None

    # Try window.env pattern
    m = re.search(r'window\.env\s*=\s*(.+);', r.text)
    if m:
        try:
            data = json.loads(m.group(1))
            app_id = data.get('api', {}).get('algolia', {}).get('applicationID')
            api_key = data.get('api', {}).get('algolia', {}).get('apiKey')
            if app_id and api_key:
                return {'appId': app_id, 'apiKey': api_key}
        except json.JSONDecodeError:
            pass

    # Try algoliaObj pattern
    m = re.search(r'algoliaObj\s*=\s*(.+?);', r.text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            app_id = data.get('api', {}).get('appId')
            api_key = data.get('api', {}).get('searchKey')
            if app_id and api_key:
                return {'appId': app_id, 'apiKey': api_key}
        except json.JSONDecodeError:
            pass

    return None


def algolia_search(creds, site, query, index='all_scenes', filters='', hits_per_page=10):
    """Query the Algolia API using cloudscraper to bypass CDN blocks."""
    url = f"https://{creds['appId']}-dsn.algolia.net/1/indexes/{index}/query"
    homepage = f'https://www.{site}.com'
    try:
        r = scraper.post(url, json={
            'query': query,
            'filters': filters,
            'hitsPerPage': hits_per_page,
        }, headers={
            'X-Algolia-Application-Id': creds['appId'],
            'X-Algolia-API-Key': creds['apiKey'],
            'Content-Type': 'application/json',
            'Referer': homepage + '/',
            'Origin': homepage,
        }, timeout=15)
        if r.status_code != 200:
            print(f'[xempire] Algolia {r.status_code} for {site}: {r.text[:200]}', file=sys.stderr)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'[xempire] Algolia request failed for {site}: {type(e).__name__}: {e}', file=sys.stderr)
        raise


def performer_from_hit(hit, site):
    """Convert Algolia actor hit to performer dict."""
    perf = {}
    if hit.get('name'):
        perf['name'] = hit['name'].strip()
    if hit.get('gender'):
        perf['gender'] = hit['gender'].strip()
    if hit.get('description'):
        perf['details'] = hit['description'].strip()
    attrs = hit.get('attributes', {})
    if attrs.get('eye_color'):
        perf['eyeColor'] = attrs['eye_color'].strip()
    if attrs.get('hair_color'):
        perf['hairColor'] = attrs['hair_color'].strip()
    if attrs.get('ethnicity'):
        perf['ethnicity'] = attrs['ethnicity'].strip()
    if attrs.get('alternate_names'):
        perf['aliases'] = attrs['alternate_names'].strip()
    if attrs.get('height'):
        h = attrs['height'].strip()
        m = re.match(r"(\d+)'(\d+)", h)
        if m:
            perf['height'] = int(round(int(m.group(1)) * 30.48 + int(m.group(2)) * 2.54))
        elif h.isdigit():
            perf['height'] = int(h)
    if attrs.get('weight'):
        w = attrs['weight'].strip()
        m = re.match(r'(\d+)\s*lb', w)
        if m:
            perf['weight'] = int(round(int(m.group(1)) * 0.4536))
        elif w.isdigit():
            perf['weight'] = int(w)
    # Photo
    if hit.get('has_pictures') and hit.get('pictures'):
        pics = hit['pictures']
        if pics:
            last_key = list(pics.keys())[-1]
            photo = f"{IMAGE_CDN}/actors{pics[last_key]}"
            perf['photo'] = photo
            perf['image'] = photo
            perf['thumbnail'] = photo
            perf['cardThumbnail'] = photo
            perf['cover_a'] = photo
            perf['cover_b'] = photo
    # URL
    if hit.get('url_name') and hit.get('actor_id'):
        perf['sourceUrl'] = f"https://www.{site}.com/en/pornstar/view/{hit['url_name']}/{hit['actor_id']}"
    perf['sourceSite'] = site
    perf['kind'] = 'performer'
    perf['notFound'] = False
    return perf


def scene_from_hit(hit, site):
    """Convert Algolia scene hit to scene dict."""
    scene = {}
    if hit.get('title'):
        scene['title'] = hit['title'].strip()
    if hit.get('description'):
        desc = hit['description'].replace('\\', '')
        desc = re.sub(r'<br\/?\s*>', '\n', desc)
        desc = re.sub(r'<[^>]+>', '', desc).strip()
        scene['description'] = desc
    if hit.get('clip_id'):
        scene['code'] = str(hit['clip_id'])
    if hit.get('directors'):
        scene['director'] = ', '.join(d.get('name', '') for d in hit['directors'])
    if hit.get('release_date'):
        scene['date'] = hit['release_date']
        # Format as "March 27, 2026"
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(hit['release_date'].replace('Z', '+00:00'))
            months = ['January','February','March','April','May','June','July','August','September','October','November','December']
            scene['releaseDate'] = f"{months[dt.month - 1]} {dt.day}, {dt.year}"
        except (ValueError, AttributeError):
            scene['releaseDate'] = hit['release_date']
    # Merge actors + female_actors + male_actors, deduplicate
    all_actors = (hit.get('actors') or []) + (hit.get('female_actors') or []) + (hit.get('male_actors') or [])
    seen = set()
    scene['performers'] = []
    for a in all_actors:
        n = (a.get('name') or '').strip()
        key = n.lower()
        if n and key not in seen:
            seen.add(key)
            scene['performers'].append(n)
    scene['tags'] = [c.get('name', '') for c in (hit.get('categories') or []) if c.get('name')]
    scene['tags'] += (hit.get('content_tags') or [])
    if hit.get('studio_name'):
        scene['studio'] = hit['studio_name']
    # Image — pictures structure: {"nsfw":{"top":{"960x544":"/path"}}, "960x544":"/path", ...}
    pics = hit.get('pictures', {})
    # Try nsfw/sfw top first
    img_set = pics.get('nsfw') or pics.get('sfw')
    if isinstance(img_set, dict):
        top = img_set.get('top', {})
        if isinstance(top, dict):
            # Pick largest by key (e.g. 960x544 > 638x360)
            best_path = None
            best_size = 0
            for size_key, path in top.items():
                if isinstance(path, str):
                    try:
                        w = int(size_key.split('x')[0])
                        if w > best_size:
                            best_size = w
                            best_path = path
                    except (ValueError, IndexError):
                        if not best_path:
                            best_path = path
            if best_path:
                scene['thumbnail'] = f"{IMAGE_CDN}/movies{best_path}"
    # Fallback: direct size key (e.g. pictures['960x544'])
    if not scene.get('thumbnail'):
        for size_key in ['960x544', '638x360', '307x224']:
            path = pics.get(size_key)
            if isinstance(path, str) and path:
                scene['thumbnail'] = f"{IMAGE_CDN}/movies{path}"
                break
    # Fallback: clip_path
    if not scene.get('thumbnail') and hit.get('clip_path'):
        scene['thumbnail'] = f"{IMAGE_CDN}/movies{hit['clip_path']}_front_1280x720.jpg"
    image = scene.get('thumbnail')
    if image:
        scene['image'] = image
        scene['thumbnail'] = image
        scene['cardThumbnail'] = image
        scene['cover_a'] = image
        scene['cover_b'] = image
    scene['kind'] = 'scene'
    # URL
    if hit.get('url_title') and hit.get('sitename') and hit.get('clip_id'):
        scene['sourceUrl'] = f"https://www.{site}.com/en/video/{hit['sitename'].lower()}/{hit['url_title']}/{hit['clip_id']}"
    scene['sourceSite'] = site
    return scene


def _match_score(query, target):
    """Score how well query matches target. Lower is better. -1 = no match."""
    q = query.lower().strip()
    t = target.lower().strip()
    if not q or not t:
        return -1
    # Exact match
    if q == t:
        return 0
    # All query words found as whole words in target
    q_words = q.split()
    t_words = t.split()
    if all(w in t_words for w in q_words):
        return 1
    # Query matches start of name ("angela" -> "angela white")
    if t.startswith(q + ' '):
        return 2
    # Target first name matches query first name
    if t_words and q_words and t_words[0] == q_words[0]:
        return 3
    return -1


def search_performer(name, site=None):
    """Search for a performer across xEmpire sites."""
    sites = [site] if site and site in XEMPIRE_SITES else XEMPIRE_SITES

    for s in sites:
        try:
            creds = get_algolia_creds(s)
            if not creds:
                continue
            result = algolia_search(creds, s, name, index='all_actors', hits_per_page=10)
            hits = result.get('hits', [])
            if not hits:
                continue

            # Score all hits and pick the best match
            best = None
            best_score = 999
            for hit in hits:
                hit_name = (hit.get('name') or '').strip()
                score = _match_score(name, hit_name)
                if score >= 0 and score < best_score:
                    best_score = score
                    best = hit

            if best:
                print(f'[xempire] Matched "{name}" -> "{best.get("name")}" (score {best_score}) on {s}', file=sys.stderr)
                return performer_from_hit(best, s)
        except Exception:
            continue

    return {'notFound': True, 'name': name}


def search_scenes(query, site=None):
    """Search for scenes across xEmpire sites."""
    sites = [site] if site and site in XEMPIRE_SITES else XEMPIRE_SITES
    all_results = []
    seen_ids = set()

    for s in sites:
        try:
            creds = get_algolia_creds(s)
            if not creds:
                print(f'[xempire] No creds for {s}', file=sys.stderr)
                continue
            result = algolia_search(creds, s, query, hits_per_page=10)
            hits = result.get('hits', [])
            print(f'[xempire] Algolia returned {len(hits)} hits for {s}', file=sys.stderr)
            for hit in hits:
                clip_id = hit.get('clip_id')
                if clip_id and clip_id in seen_ids:
                    continue
                if clip_id:
                    seen_ids.add(clip_id)
                all_results.append(scene_from_hit(hit, s))
        except Exception as e:
            print(f'[xempire] Search failed for {s}: {type(e).__name__}: {e}', file=sys.stderr)
            continue

    return all_results if all_results else {'notFound': True}


def scrape_scene(url):
    """Scrape a scene by URL."""
    parsed = urlparse(url)
    site = parsed.hostname.replace('www.', '').replace('.com', '')
    if site not in XEMPIRE_SITES:
        return {'error': f'Not an xEmpire URL: {site}'}

    # Extract clip_id from URL
    m = re.search(r'/(\d+)(?:-\d+)*$', url)
    if not m:
        return {'error': 'Cannot extract scene ID from URL'}
    clip_id = m.group(1)

    creds = get_algolia_creds(site)
    if not creds:
        return {'error': f'Could not get Algolia credentials for {site}'}

    result = algolia_search(creds, site, '', filters=f'clip_id:{clip_id}', hits_per_page=1)
    hits = result.get('hits', [])
    if not hits:
        return {'notFound': True}

    return scene_from_hit(hits[0], site)


def performer_photo_url(actor_id):
    """Construct performer photo URL from actor ID using Gamma CDN."""
    return f'{TRANSFORM_CDN}/actors/{actor_id}/{actor_id}_500x750.jpg?width=350&height=525&format=webp'


def scrape_performer_photo(site, name):
    """Search for a performer on an xEmpire site and return their photo."""
    creds = get_algolia_creds(site)
    if not creds:
        return {'error': f'Could not get credentials for {site}', 'notFound': True}

    # Search in actors index
    try:
        result = algolia_search(creds, site, name, index='all_actors', hits_per_page=10)
        hits = result.get('hits', [])
        best = None
        best_score = 999
        for hit in hits:
            hit_name = (hit.get('name') or '').strip()
            score = _match_score(name, hit_name)
            if score >= 0 and score < best_score:
                best_score = score
                best = hit
        if best:
            actor_id = best.get('actor_id')
            if actor_id:
                photo = performer_photo_url(actor_id)
                print(f'[xempire] Photo matched "{name}" -> "{best.get("name")}" (score {best_score}) on {site}', file=sys.stderr)
                return {
                    'kind': 'performer',
                    'photo': photo,
                    'image': photo,
                    'thumbnail': photo,
                    'cardThumbnail': photo,
                    'cover_a': photo,
                    'cover_b': photo,
                    'sourceUrl': f'https://www.{site}.com/en/pornstar/view/{best.get("url_name", "")}/{actor_id}',
                    'sourceSite': site,
                    'notFound': False,
                }
    except Exception:
        pass

    # Fallback: search scenes for actor_id
    try:
        result = algolia_search(creds, site, name, hits_per_page=5)
        for hit in result.get('hits', []):
            for actor in (hit.get('actors') or []):
                actor_name = (actor.get('name') or '').strip()
                if _match_score(name, actor_name) >= 0:
                    actor_id = actor.get('actor_id')
                    if actor_id:
                        photo = performer_photo_url(actor_id)
                        return {
                            'kind': 'performer',
                            'photo': photo,
                            'image': photo,
                            'thumbnail': photo,
                            'cardThumbnail': photo,
                            'cover_a': photo,
                            'cover_b': photo,
                            'sourceUrl': f'https://www.{site}.com/en/pornstar/view/{actor.get("url_name", "")}/{actor_id}',
                            'sourceSite': site,
                            'notFound': False,
                        }
    except Exception:
        pass

    return {'notFound': True, 'name': name}


def scrape(title="", url="", html=""):
    """Unified entry point called by the backend."""
    if url:
        if '/pornstar/' in url:
            parsed = urlparse(url)
            site = parsed.hostname.replace('www.', '').replace('.com', '')
            m = re.search(r'/([^/]+)/(\d+)$', url)
            if m:
                creds = get_algolia_creds(site)
                if creds:
                    r = algolia_search(creds, site, '', index='all_actors', filters=f'actor_id:{m.group(2)}', hits_per_page=1)
                    hits = r.get('hits', [])
                    if hits:
                        return performer_from_hit(hits[0], site)
            return {'notFound': True}
        return scrape_scene(url)
    if title:
        results = search_scenes(title)
        if isinstance(results, list) and results:
            import titlematch
            return titlematch.best(results, title)
        return results
    return {'error': 'need url or title'}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: xempire_scraper.py <algolia-creds|performer|performer-url|scene-search|scene-url> [args...]'}))
        sys.exit(1)

    op = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else ''
    arg2 = sys.argv[3] if len(sys.argv) > 3 else ''

    try:
        if op == 'algolia-creds':
            site = arg or 'darkx'
            creds = get_algolia_creds(site)
            result = creds if creds else {'error': f'Could not get credentials for {site}'}
        elif op == 'performer':
            result = search_performer(arg, site=arg2 or None)
        elif op == 'performer-url':
            parsed = urlparse(arg)
            site = parsed.hostname.replace('www.', '').replace('.com', '')
            m = re.search(r'/(\d+)$', arg)
            if m:
                creds = get_algolia_creds(site)
                if creds:
                    r = algolia_search(creds, site, '', index='all_actors', filters=f'actor_id:{m.group(1)}', hits_per_page=1)
                    hits = r.get('hits', [])
                    result = performer_from_hit(hits[0], site) if hits else {'notFound': True}
                else:
                    result = {'error': f'Could not get credentials for {site}'}
            else:
                result = {'error': 'Could not extract actor ID from URL'}
        elif op == 'scene-search':
            result = search_scenes(arg, site=arg2 or None)
        elif op == 'scene-url':
            result = scrape_scene(arg)
        elif op == 'performer-photo':
            # performer-photo <name> <site>
            result = scrape_performer_photo(arg2 or 'darkx', arg)
        else:
            result = {'error': f'Unknown operation: {op}'}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
