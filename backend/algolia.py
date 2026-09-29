"""Shared Algolia API client for Gamma/EvilAngel network sites.

Used by: EvilAngel, DogfartNetwork, Wicked, etc.
API: Algolia search (all_scenes / all_actors indices)
Image CDN: https://images03-fame.gammacdn.com
"""
import re
from datetime import datetime
import requests

IMAGE_CDN = "https://images03-fame.gammacdn.com"

# Cache credentials per site
_creds_cache = {}


def get_algolia_creds(site_url):
    """Get Algolia API credentials from a site's video listing page."""
    if site_url in _creds_cache:
        return _creds_cache[site_url]
    try:
        r = requests.get(f'{site_url}/en/videos', timeout=(5, 15), headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        r.raise_for_status()
        app_id = re.search(r'"applicationID"\s*:\s*"([A-Z0-9]+)"', r.text)
        api_key = re.search(r'"apiKey"\s*:\s*"([A-Za-z0-9+/=]+)"', r.text)
        if app_id and api_key:
            creds = {'appId': app_id.group(1), 'apiKey': api_key.group(1)}
            _creds_cache[site_url] = creds
            return creds
    except Exception:
        pass
    _creds_cache[site_url] = None
    return None


def algolia_search(creds, query, index='all_scenes', filters='', hits_per_page=10, referer=None):
    """Query the Algolia API."""
    url = f"https://{creds['appId']}-dsn.algolia.net/1/indexes/{index}/query"
    r = requests.post(url, json={
        'query': query,
        'filters': filters,
        'hitsPerPage': hits_per_page,
    }, headers={
        'X-Algolia-Application-Id': creds['appId'],
        'X-Algolia-API-Key': creds['apiKey'],
        'Content-Type': 'application/json',
        'Referer': referer or 'https://www.evilangel.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0',
    }, timeout=15)
    r.raise_for_status()
    return r.json()


def parse_date(raw):
    """Parse date from various formats into YYYY-MM-DD. Returns None on garbage."""
    if not raw:
        return None
    # Unix timestamp
    if isinstance(raw, (int, float)):
        try:
            dt = datetime.utcfromtimestamp(raw)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return None
    raw = str(raw).strip()
    if not raw:
        return None
    # ISO-8601 first (covers '2021-05-04', '2021-05-04T12:00:00Z', offsets…)
    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%B %d, %Y', '%b %d, %Y',
                '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    # date prefix of a longer string ('2021-05-04 something')
    m = re.match(r'(\d{4}-\d{2}-\d{2})', raw)
    return m.group(1) if m else None


def parse_duration(raw):
    """Parse duration (HH:MM:SS, MM:SS, or seconds) to minutes."""
    if not raw:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw) // 60
    raw = str(raw).strip()
    m = re.match(r'(\d+):(\d+)(?::(\d+))?$', raw)
    if m:
        if m.group(3):
            return int(m.group(1)) * 60 + int(m.group(2))
        return int(m.group(1))
    if raw.isdigit():
        return int(raw) // 60
    return 0


def scene_image_from_hit(hit):
    """Extract scene thumbnail from Algolia hit."""
    movie_id = hit.get('movie_id')
    pictures = hit.get('pictures')

    # 1. pictures dict
    if pictures and isinstance(pictures, dict):
        for path in (
            (pictures.get('nsfw') or {}).get('top', {}).get('1920x1080'),
            pictures.get('1920x1080'),
            pictures.get('resized'),
        ):
            if path:
                return f"{IMAGE_CDN}/movies{path}"

    # 2. scrubbers
    scrubbers = hit.get('scrubbers') or {}
    scrub_full = scrubbers.get('full') or {}
    if scrub_full.get('url'):
        return scrub_full['url']

    # 3. construct from clip_path / movie_id
    clip_path = hit.get('clip_path')
    if clip_path and movie_id:
        return f"{IMAGE_CDN}/movies/{movie_id}/{clip_path}/previews/2/128/top_1_1920x1080/{clip_path}_01.jpg"

    # 4. fallback from movie_id
    if movie_id:
        return f"{IMAGE_CDN}/movies/{movie_id}/1.jpg"

    return None


def performer_from_hit(hit):
    """Convert Algolia actor hit to performer dict."""
    perf = {'kind': 'performer'}
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
    # URL
    if hit.get('url_name') and hit.get('actor_id'):
        perf['sourceUrl'] = f"/en/pornstar/view/{hit['url_name']}/{hit['actor_id']}"
    return perf


def scene_from_hit(hit):
    """Convert Algolia scene hit to Obscura scene dict."""
    scene = {'kind': 'scene'}

    if hit.get('title'):
        scene['title'] = hit['title'].strip()
    if hit.get('description'):
        scene['details'] = hit['description'].strip()

    # Date
    raw_date = hit.get('release_date') or hit.get('date')
    if raw_date:
        scene['date'] = parse_date(raw_date)

    # Duration
    dur = parse_duration(hit.get('clip_length'))
    if not dur and hit.get('length'):
        dur = parse_duration(hit['length'])
    if dur:
        scene['duration_min'] = dur

    # Code
    if hit.get('clip_id'):
        scene['code'] = str(hit['clip_id'])

    # Performers
    performers = []
    for actor in (hit.get('actors') or []):
        if isinstance(actor, dict):
            p = {}
            if actor.get('name'):
                p['name'] = actor['name'].strip()
            if actor.get('gender'):
                p['gender'] = actor['gender'].strip()
            if p.get('name'):
                performers.append(p)
        elif isinstance(actor, str) and actor.strip():
            performers.append({'name': actor.strip()})
    scene['performers'] = performers

    # Studio
    studio = hit.get('studio_name') or hit.get('sitename')
    if studio:
        scene['studio'] = studio.strip()

    # Groups (movie)
    if hit.get('movie_title'):
        scene['groups'] = [{'name': hit['movie_title'].strip()}]

    # Tags
    tags = []
    for cat in (hit.get('categories') or []):
        if isinstance(cat, dict) and cat.get('name'):
            tags.append(cat['name'].strip())
        elif isinstance(cat, str) and cat.strip():
            tags.append(cat.strip())
    if not tags:
        for c in (hit.get('master_categories') or []):
            if isinstance(c, str) and c.strip():
                tags.append(c.strip())
    scene['tags'] = tags

    # Image
    image = scene_image_from_hit(hit)
    if image:
        scene['image'] = image
        scene['thumbnail'] = image
        scene['cardThumbnail'] = image
        scene['cover_a'] = image
        scene['cover_b'] = image

    return scene


def title_match_score(query, title):
    """Score how well a title matches a query."""
    if not title or not query:
        return 0
    q = query.lower().strip()
    t = title.lower().strip()
    if q == t:
        return 100
    if q in t:
        return 90
    if t in q:
        return 80
    q_words = set(re.findall(r'\w+', q))
    t_words = set(re.findall(r'\w+', t))
    stop = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'is', 'it', 'to', 'for', 'with', 'scene'}
    overlap = (q_words & t_words) - stop
    q_meaningful = q_words - stop
    if not overlap or not q_meaningful:
        return 0
    return int((len(overlap) / len(q_meaningful)) * 70) + len(overlap)


def search_scenes(query, site_url, referer=None):
    """Search for scenes via Algolia."""
    creds = get_algolia_creds(site_url)
    if not creds:
        return {'error': 'Could not get Algolia credentials', 'notFound': True}
    try:
        result = algolia_search(creds, query, index='all_scenes', hits_per_page=10, referer=referer)
        hits = result.get('hits', [])
        if not hits:
            return {'notFound': True, 'query': query}
        scenes = [scene_from_hit(h) for h in hits]
        for s in scenes:
            s['_score'] = title_match_score(query, s.get('title', ''))
        scenes.sort(key=lambda s: s['_score'], reverse=True)
        return scenes
    except Exception as e:
        return {'error': str(e), 'notFound': True}


def search_performer(name, site_url, referer=None):
    """Search for a performer via Algolia."""
    creds = get_algolia_creds(site_url)
    if not creds:
        return {'error': 'Could not get Algolia credentials', 'notFound': True}
    try:
        result = algolia_search(creds, name, index='all_actors', hits_per_page=5, referer=referer)
        hits = result.get('hits', [])
        name_lower = name.lower()
        for hit in hits:
            hit_name = (hit.get('name') or '').strip().lower()
            if hit_name == name_lower or name_lower in hit_name:
                return performer_from_hit(hit)
        if hits:
            return performer_from_hit(hits[0])
    except Exception as e:
        return {'error': str(e), 'notFound': True}
    return {'notFound': True}


def get_scene_by_id(clip_id, site_url, referer=None):
    """Fetch single scene by clip_id."""
    creds = get_algolia_creds(site_url)
    if not creds:
        return {'error': 'Could not get Algolia credentials', 'notFound': True}
    try:
        result = algolia_search(creds, '', index='all_scenes',
                                filters=f'clip_id:{clip_id}', hits_per_page=1, referer=referer)
        hits = result.get('hits', [])
        if hits:
            return scene_from_hit(hits[0])
    except Exception as e:
        return {'error': str(e), 'notFound': True}
    return {'notFound': True}


def scene_by_url(url, site_url, referer=None):
    """Extract scene from URL."""
    m = re.search(r'/(\d+)(?:\?|$|#)', url)
    if not m:
        m = re.search(r'/(\d+)/?$', url)
    if m:
        return get_scene_by_id(m.group(1), site_url, referer)
    # Try slug
    m = re.search(r'/video/[^/]+/([^/]+)', url)
    if m:
        results = search_scenes(m.group(1).replace('-', ' '), site_url, referer)
        if isinstance(results, list) and results:
            return results[0]
    return {'error': 'Could not extract scene ID from URL', 'notFound': True}
